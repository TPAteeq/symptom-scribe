from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import uuid

from models import SessionStatusModel, SessionStatus
from services.storage_service import storage
from services.summary_service import summary_service

router = APIRouter()


@router.post("/start")
async def start_session(patient_id: str = Query(...), appointment_id: str = Query(...)):
    """Start a new symptom screening session."""
    appointment = storage.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    session_id = f"session_{uuid.uuid4().hex[:8]}"
    session = storage.create_session(session_id, patient_id, appointment_id)
    return {"session_id": session_id, "status": session.status.value}


@router.get("/{session_id}/status", response_model=SessionStatusModel)
async def get_session_status(session_id: str):
    """Get current session status."""
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStatusModel(
        state=session.status,
        exchange_count=len(session.conversation_history),
        last_activity=session.end_time or session.start_time,
    )


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """End a symptom screening session and generate summary."""
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = SessionStatus.COMPLETED
    session.end_time = datetime.now()
    storage.update_session(session)

    if len(session.conversation_history) > 0 and not session.summary_generated:
        summary = await summary_service.generate_summary(
            patient_id=session.patient_id,
            appointment_id=session.appointment_id,
            conversation_history=session.conversation_history,
            emergency_detected=session.emergency_detected,
        )
        storage.store_summary(summary)
        session.summary_generated = True
        storage.update_session(session)
        return {"message": "Session ended", "session_id": session_id, "summary_id": summary.summary_id}

    return {"message": "Session ended", "session_id": session_id}
