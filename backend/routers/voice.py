from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict
import asyncio
import json
import base64
import logging
from datetime import datetime

from models import TranscriptionResult, SessionStatus, ConversationExchange
from config import MIN_CONVERSATION_EXCHANGES
from services.transcription_service import transcription_manager, transcription_service
from services.emergency_service import emergency_service
from services.conversation_service import conversation_service
from services.summary_service import summary_service
from services.tts_service import tts_service
from services.storage_service import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections and their session info
active_connections: Dict[str, Dict] = {}


async def transcription_callback(session_id: str, result: TranscriptionResult):
    """Callback for transcription results — drives the conversation loop."""
    if session_id not in active_connections:
        return

    connection_info = active_connections[session_id]
    websocket = connection_info["websocket"]

    try:
        # Send transcription result to client
        await websocket.send_text(json.dumps({
            "type": "transcription_result",
            "text": result.text,
            "confidence": result.confidence,
            "is_final": result.is_final,
            "timestamp": result.timestamp.isoformat(),
        }))

        # Only process final transcriptions with content
        if not result.is_final or not result.text.strip():
            return

        symptom_session_id = connection_info.get("symptom_session_id")
        if not symptom_session_id:
            return

        # Store patient exchange
        exchange = ConversationExchange(
            timestamp=datetime.now(), type="patient", content=result.text
        )
        storage.add_exchange(symptom_session_id, exchange)

        # Emergency check (safety-critical, keyword-only)
        emergency_result = emergency_service.check_for_emergency(result.text)
        if emergency_result.is_emergency:
            await handle_emergency(session_id, emergency_result)
            return

        # Update summary in background (non-blocking) after each patient exchange
        asyncio.create_task(_update_summary_background(symptom_session_id))

        # Generate AI response
        await websocket.send_text(json.dumps({"type": "status_update", "status": "processing"}))

        session = storage.get_session(symptom_session_id)
        patient_name = active_connections.get(session_id, {}).get("patient_name", "")

        # After conclusion prompt, evaluate whether patient is done
        patient_count = len([e for e in session.conversation_history if e.type == "patient"])
        if patient_count > MIN_CONVERSATION_EXCHANGES:
            if await conversation_service.evaluate_patient_done(result.text):
                final_msg = conversation_service.get_final_message()
                storage.add_exchange(symptom_session_id, ConversationExchange(
                    timestamp=datetime.now(), type="ai", content=final_msg
                ))
                audio_data = await tts_service.synthesize(final_msg)
                await websocket.send_text(json.dumps({
                    "type": "ai_response",
                    "text": final_msg,
                    "audio_data": base64.b64encode(audio_data).decode() if audio_data else "",
                }))
                await handle_session_complete(session_id)
                return

        ai_text = await conversation_service.generate_response(session.conversation_history, patient_name)

        # Store AI exchange
        ai_exchange = ConversationExchange(
            timestamp=datetime.now(), type="ai", content=ai_text
        )
        storage.add_exchange(symptom_session_id, ai_exchange)

        # TTS
        audio_data = await tts_service.synthesize(ai_text)

        # Send AI response
        await websocket.send_text(json.dumps({
            "type": "ai_response",
            "text": ai_text,
            "audio_data": base64.b64encode(audio_data).decode() if audio_data else "",
        }))

        # Check if conversation should conclude
        patient_count = len([e for e in session.conversation_history if e.type == "patient"])
        if conversation_service.should_conclude(patient_count):
            await handle_session_complete(session_id)

    except Exception as e:
        logger.error(f"Error in transcription callback for {session_id}: {e}")


async def _update_summary_background(symptom_session_id: str):
    """Generate and store an updated summary after each patient exchange (fire-and-forget)."""
    try:
        session = storage.get_session(symptom_session_id)
        if not session:
            return
        clinical_summary = await summary_service.generate_summary(
            session.patient_id, session.appointment_id,
            session.conversation_history, emergency_detected=False,
        )
        storage.store_summary(clinical_summary)
        logger.info(f"Updated summary for appointment {session.appointment_id}")
    except Exception as e:
        logger.error(f"Background summary update failed: {e}")


async def handle_emergency(session_id: str, emergency_result):
    """Handle emergency detection: notify client, generate summary, end session."""
    connection_info = active_connections[session_id]
    websocket = connection_info["websocket"]
    symptom_session_id = connection_info["symptom_session_id"]

    session = storage.get_session(symptom_session_id)
    session.emergency_detected = True
    session.status = SessionStatus.EMERGENCY
    storage.update_session(session)

    # TTS for emergency message
    audio = await tts_service.synthesize(emergency_result.response_message)

    await websocket.send_text(json.dumps({
        "type": "emergency_detected",
        "keywords": emergency_result.detected_keywords,
        "message": emergency_result.response_message,
        "audio_data": base64.b64encode(audio).decode() if audio else "",
    }))

    # Generate and store emergency summary
    clinical_summary = await summary_service.generate_summary(
        session.patient_id, session.appointment_id,
        session.conversation_history, emergency_detected=True,
    )
    storage.store_summary(clinical_summary)

    session.summary_generated = True
    session.status = SessionStatus.COMPLETED
    session.end_time = datetime.now()
    storage.update_session(session)


async def handle_session_complete(session_id: str):
    """Handle normal session completion: generate summary, notify client."""
    connection_info = active_connections[session_id]
    websocket = connection_info["websocket"]
    symptom_session_id = connection_info["symptom_session_id"]

    session = storage.get_session(symptom_session_id)

    clinical_summary = await summary_service.generate_summary(
        session.patient_id, session.appointment_id,
        session.conversation_history, emergency_detected=False,
    )
    storage.store_summary(clinical_summary)

    session.summary_generated = True
    session.status = SessionStatus.COMPLETED
    session.end_time = datetime.now()
    storage.update_session(session)

    await websocket.send_text(json.dumps({
        "type": "session_complete",
        "summary_id": clinical_summary.summary_id,
        "severity_flag": clinical_summary.severity_flag.value,
        "message": "Your symptom summary has been prepared for your doctor.",
    }))


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time voice communication."""
    await websocket.accept()

    active_connections[session_id] = {
        "websocket": websocket,
        "connected_at": datetime.now(),
        "transcription_active": False,
        "symptom_session_id": None,
    }

    logger.info(f"WebSocket connected for session {session_id}")

    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "session_id": session_id,
            "status": "ready",
        }))

        while True:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                message_type = data.get("type")

                if message_type == "start_session":
                    await handle_start_session(session_id, data)

                elif message_type == "start_transcription":
                    await handle_start_transcription(session_id, data)

                elif message_type == "audio_chunk":
                    await handle_audio_chunk(session_id, data)

                elif message_type == "text_input":
                    await handle_text_input(session_id, data)

                elif message_type == "end_transcription":
                    await handle_end_transcription(session_id)

                elif message_type == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                    }))

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                await handle_binary_audio_data(session_id, message)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        await cleanup_session(session_id)


async def _session_timeout(session_id: str):
    """Force-complete the session after 10 minutes."""
    await asyncio.sleep(600)
    if session_id in active_connections:
        logger.info(f"Session {session_id} timed out after 10 minutes")
        await handle_session_complete(session_id)


async def handle_start_session(session_id: str, data: dict):
    """Link the WebSocket connection to a symptom session and send initial greeting."""
    symptom_session_id = data.get("symptom_session_id", session_id)
    patient_name = data.get("patient_name", "").strip()

    if session_id in active_connections:
        active_connections[session_id]["symptom_session_id"] = symptom_session_id
        active_connections[session_id]["patient_name"] = patient_name

    # 10-minute hard timeout
    asyncio.create_task(_session_timeout(session_id))

    # Update session status and reset conversation history for a fresh start
    session = storage.get_session(symptom_session_id)
    if session:
        session.status = SessionStatus.LISTENING
        session.conversation_history = []
        storage.update_session(session)

    # Send initial AI greeting
    greeting = conversation_service.get_initial_greeting(patient_name)
    greeting_exchange = ConversationExchange(
        timestamp=datetime.now(), type="ai", content=greeting
    )
    storage.add_exchange(symptom_session_id, greeting_exchange)

    # TTS for greeting
    audio_data = await tts_service.synthesize(greeting)

    websocket = active_connections[session_id]["websocket"]
    await websocket.send_text(json.dumps({
        "type": "ai_response",
        "text": greeting,
        "audio_data": base64.b64encode(audio_data).decode() if audio_data else "",
    }))
    # No status_update: listening here — onAIResponse on the frontend opens the mic
    # after the greeting audio finishes playing.


async def handle_text_input(session_id: str, data: dict):
    """Handle text input as an alternative to voice (for testing/accessibility)."""
    text = data.get("text", "").strip()
    if not text:
        return

    result = TranscriptionResult(
        text=text,
        confidence=1.0,
        is_final=True,
        timestamp=datetime.now(),
    )
    await transcription_callback(session_id, result)


async def handle_start_transcription(session_id: str, data: dict):
    """Handle start transcription request."""
    try:
        language_code = data.get("language_code", "en-US")
        sample_rate = data.get("sample_rate", 16000)
        media_format = data.get("media_format", "pcm")

        async def session_callback(result: TranscriptionResult):
            await transcription_callback(session_id, result)

        session_config = await transcription_manager.start_session(
            session_id=session_id,
            callback=session_callback,
            language_code=language_code,
            sample_rate=sample_rate,
            media_format=media_format,
        )

        if session_id in active_connections:
            active_connections[session_id]["transcription_active"] = True

        websocket = active_connections[session_id]["websocket"]
        await websocket.send_text(json.dumps({
            "type": "transcription_started",
            "session_id": session_id,
            "config": session_config,
        }))

        logger.info(f"Started transcription for session {session_id}")

    except Exception as e:
        logger.error(f"Failed to start transcription for session {session_id}: {e}")
        await send_error_message(session_id, "Failed to start transcription", str(e))


async def handle_audio_chunk(session_id: str, data: dict):
    """Handle audio chunk data.

    The frontend sends raw PCM (16-bit LE, 16 kHz) as base64.
    When is_final=True the chunk is the complete utterance — transcribe it
    then run the conversation pipeline.  Non-final chunks are accumulated in
    case the frontend ever switches to streaming mode.
    """
    try:
        audio_data_b64 = data.get("audio_data")
        if not audio_data_b64:
            return

        is_final = data.get("is_final", False)
        audio_bytes = base64.b64decode(audio_data_b64)

        if not is_final:
            # Accumulate streaming chunks (not currently sent by the frontend
            # but kept here so switching to streaming later requires no changes)
            if session_id in active_connections:
                buf = active_connections[session_id].get("audio_buffer", b"")
                active_connections[session_id]["audio_buffer"] = buf + audio_bytes
            return

        # Final utterance: concatenate any buffered chunks + this chunk
        buffered = b""
        if session_id in active_connections:
            buffered = active_connections[session_id].pop("audio_buffer", b"")
        complete_audio = buffered + audio_bytes

        if not complete_audio:
            return

        text = await transcription_service.transcribe(complete_audio)
        if not text.strip():
            logger.info(f"Empty transcription for session {session_id} — re-opening mic")
            if session_id in active_connections:
                ws = active_connections[session_id]["websocket"]
                await ws.send_text(json.dumps({"type": "status_update", "status": "listening"}))
            return

        result = TranscriptionResult(
            text=text, confidence=1.0, is_final=True, timestamp=datetime.now()
        )
        await transcription_callback(session_id, result)

    except Exception as e:
        logger.error(f"Failed to handle audio chunk for session {session_id}: {e}")
        await send_error_message(session_id, "Failed to process audio", str(e))


async def handle_binary_audio_data(session_id: str, audio_data):
    """Handle binary audio data directly."""
    try:
        if isinstance(audio_data, str):
            audio_data = audio_data.encode()
        await transcription_manager.process_audio_chunk(session_id, audio_data)
    except Exception as e:
        logger.error(f"Failed to handle binary audio data for session {session_id}: {e}")


async def handle_end_transcription(session_id: str):
    """Handle end transcription request."""
    try:
        success = await transcription_manager.end_session(session_id)

        if session_id in active_connections:
            active_connections[session_id]["transcription_active"] = False

        websocket = active_connections[session_id]["websocket"]
        await websocket.send_text(json.dumps({
            "type": "transcription_ended",
            "session_id": session_id,
            "success": success,
        }))

    except Exception as e:
        logger.error(f"Failed to end transcription for session {session_id}: {e}")
        await send_error_message(session_id, "Failed to end transcription", str(e))


async def send_error_message(session_id: str, error_type: str, error_message: str):
    """Send error message to client."""
    if session_id in active_connections:
        try:
            websocket = active_connections[session_id]["websocket"]
            await websocket.send_text(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat(),
            }))
        except Exception as e:
            logger.error(f"Failed to send error message to session {session_id}: {e}")


async def cleanup_session(session_id: str):
    """Clean up session resources."""
    try:
        if session_id in active_connections:
            connection_info = active_connections[session_id]
            if connection_info.get("transcription_active", False):
                await transcription_manager.end_session(session_id)

        if session_id in active_connections:
            del active_connections[session_id]

        logger.info(f"Cleaned up session {session_id}")
    except Exception as e:
        logger.error(f"Error during session cleanup for {session_id}: {e}")


@router.post("/test-connection")
async def test_voice_connection():
    """Test endpoint for voice service connectivity."""
    return {
        "status": "voice service ready",
        "active_websocket_connections": len(active_connections),
        "timestamp": datetime.now().isoformat(),
    }
