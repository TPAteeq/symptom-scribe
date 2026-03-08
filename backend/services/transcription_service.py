"""
Transcription service for speech-to-text.

Providers (set via TRANSCRIPTION_PROVIDER env var):
  aws      — AWS Transcribe Streaming (default)
  deepgram — Deepgram nova-2 (swap when ready)
  mock     — no-op, tests use text_input path

The active singleton is `transcription_service`.
`TranscriptionManager` is kept for test-suite backwards compatibility.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from models import TranscriptionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseTranscriptionService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM (16-bit LE) audio bytes to text."""
        ...


# ---------------------------------------------------------------------------
# AWS Transcribe Streaming
# ---------------------------------------------------------------------------

class AWSTranscribeService(BaseTranscriptionService):
    def __init__(self, region: str = "us-east-1"):
        self.region = region

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        try:
            # amazon-transcribe uses its own async streaming protocol
            from amazon_transcribe.client import TranscribeStreamingClient
            from amazon_transcribe.handlers import TranscriptResultStreamHandler
            from amazon_transcribe.model import TranscriptEvent as AWSTranscriptEvent

            client = TranscribeStreamingClient(region=self.region)
            stream = await client.start_stream_transcription(
                language_code="en-US",
                media_sample_rate_hz=sample_rate,
                media_encoding="pcm",
            )

            transcript_parts: list = []

            class _Handler(TranscriptResultStreamHandler):
                async def handle_transcript_event(self, event: AWSTranscriptEvent):  # type: ignore[override]
                    for result in event.transcript.results:
                        if not result.is_partial:
                            for alt in result.alternatives:
                                transcript_parts.append(alt.transcript)

            handler = _Handler(stream.output_stream)

            async def _send():
                chunk_size = 8192
                for i in range(0, len(audio_bytes), chunk_size):
                    await stream.input_stream.send_audio_event(
                        audio_chunk=audio_bytes[i : i + chunk_size]
                    )
                await stream.input_stream.end_stream()

            await asyncio.gather(_send(), handler.handle_events())
            return " ".join(transcript_parts).strip()

        except Exception as e:
            logger.error(f"AWS Transcribe error: {e}")
            return ""


# ---------------------------------------------------------------------------
# Deepgram (swap in by setting TRANSCRIPTION_PROVIDER=deepgram)
# ---------------------------------------------------------------------------

class DeepgramTranscriptionService(BaseTranscriptionService):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={"Authorization": f"Token {self.api_key}"},
                    params={
                        "model": "nova-2",
                        "encoding": "linear16",
                        "sample_rate": str(sample_rate),
                        "punctuate": "true",
                    },
                    content=audio_bytes,
                )
                response.raise_for_status()
                data = response.json()
                return data["results"]["channels"][0]["alternatives"][0]["transcript"]
        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            return ""


# ---------------------------------------------------------------------------
# Mock (used in tests — tests submit text directly via text_input)
# ---------------------------------------------------------------------------

class MockTranscriptionService(BaseTranscriptionService):
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        return ""


# ---------------------------------------------------------------------------
# Factory + singleton
# ---------------------------------------------------------------------------

def get_transcription_service() -> BaseTranscriptionService:
    from config import USE_MOCK_SERVICES, AWS_REGION

    provider = os.getenv("TRANSCRIPTION_PROVIDER", "aws")
    if USE_MOCK_SERVICES or provider == "mock":
        logger.info("Using mock transcription service")
        return MockTranscriptionService()
    if provider == "deepgram":
        api_key = os.getenv("DEEPGRAM_API_KEY", "")
        logger.info("Using Deepgram transcription service")
        return DeepgramTranscriptionService(api_key=api_key)
    logger.info("Using AWS Transcribe service (region=%s)", AWS_REGION)
    return AWSTranscribeService(region=AWS_REGION)


transcription_service = get_transcription_service()


# ---------------------------------------------------------------------------
# Legacy TranscriptionManager — kept so existing tests keep passing
# ---------------------------------------------------------------------------

class TranscribeStreamingService:
    """Legacy stub — active STT is now handled by transcription_service."""

    async def transcribe_audio_chunk(
        self,
        audio_data: bytes,
        language_code: str = "en-US",
        sample_rate: int = 16000,
        media_format: str = "pcm",
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text="", confidence=0.0, is_final=True, timestamp=datetime.now()
        )

    async def start_streaming_transcription(
        self, session_id: str, **kwargs: Any
    ) -> Dict[str, Any]:
        return {"session_id": session_id, "status": "active", "created_at": datetime.now()}

    def validate_audio_format(self, audio_data: bytes) -> bool:
        return bool(audio_data)


class TranscriptionManager:
    """Legacy manager — kept for test-suite compatibility."""

    def __init__(self) -> None:
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.transcribe_service = TranscribeStreamingService()

    async def start_session(
        self,
        session_id: str,
        callback: Optional[Callable] = None,
        language_code: str = "en-US",
        sample_rate: int = 16000,
        media_format: str = "pcm",
    ) -> Dict[str, Any]:
        config = await self.transcribe_service.start_streaming_transcription(
            session_id=session_id,
            language_code=language_code,
            sample_rate=sample_rate,
            media_format=media_format,
        )
        self.active_sessions[session_id] = {
            "config": config,
            "callback": callback,
            "active": True,
            "transcription_count": 0,
            "last_activity": datetime.now(),
        }
        return config

    async def process_audio_chunk(
        self, session_id: str, audio_data: bytes
    ) -> Optional[TranscriptionResult]:
        if session_id not in self.active_sessions:
            return None
        info = self.active_sessions[session_id]
        result = await self.transcribe_service.transcribe_audio_chunk(audio_data)
        info["transcription_count"] += 1
        info["last_activity"] = datetime.now()
        if info.get("callback") and result.text:
            await info["callback"](result)
        return result

    async def end_session(self, session_id: str) -> bool:
        if session_id not in self.active_sessions:
            return False
        self.active_sessions[session_id]["active"] = False
        del self.active_sessions[session_id]
        return True

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        return {
            sid: {
                "active": info["active"],
                "transcription_count": info["transcription_count"],
                "last_activity": info["last_activity"],
                "config": info["config"],
            }
            for sid, info in self.active_sessions.items()
            if info["active"]
        }

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.active_sessions.get(session_id)


transcription_manager = TranscriptionManager()
