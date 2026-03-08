import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models import AppointmentDetails, BookingConfirmation, PreVisitOption, SyntheticPatient
from services.storage_service import storage
from config import TABLE_PATIENTS

router = APIRouter()


@router.get("/")
async def list_appointments():
    """List all appointments (synthetic data)."""
    return [
        {
            "appointment_id": appt.appointment_id,
            "patient_id": appt.patient_id,
            "patient_name": storage.get_patient(appt.patient_id).name
            if storage.get_patient(appt.patient_id)
            else "Unknown",
            "doctor_id": appt.doctor_id,
            "appointment_time": appt.appointment_time.isoformat(),
            "appointment_type": appt.appointment_type,
            "status": appt.status,
        }
        for appt in storage.get_all_appointments()
    ]


class WalkInRequest(BaseModel):
    patient_name: str
    doctor_id: str = "doctor_001"


@router.post("/walk-in")
async def create_walk_in(body: WalkInRequest):
    """Create a new patient and appointment for a walk-in check-in."""
    uid = uuid.uuid4().hex[:8]
    patient_id = f"patient_{uid}"
    appointment_id = f"appt_{uid}"
    now = datetime.now()

    patient = SyntheticPatient(
        patient_id=patient_id,
        name=body.patient_name,
        age=0,
        gender="Unknown",
        appointment_id=appointment_id,
        appointment_time=now,
        doctor_id=body.doctor_id,
        medical_history=[],
    )
    storage.dynamodb.Table(TABLE_PATIENTS).put_item(
        Item=patient.model_dump(mode='json')
    )

    appointment = AppointmentDetails(
        appointment_id=appointment_id,
        patient_id=patient_id,
        doctor_id=body.doctor_id,
        appointment_time=now,
        appointment_type="Walk-in Pre-Visit Screening",
        status="scheduled",
    )
    storage.store_appointment(appointment)

    return {"patient_id": patient_id, "appointment_id": appointment_id}


@router.post("/confirm", response_model=BookingConfirmation)
async def confirm_appointment(appointment: AppointmentDetails):
    """Confirm appointment and return booking details."""
    stored = storage.get_appointment(appointment.appointment_id)
    if not stored:
        storage.store_appointment(appointment)

    return BookingConfirmation(
        appointment_id=appointment.appointment_id,
        appointment_time=appointment.appointment_time,
        doctor_name="Dr. Smith",
        pre_visit_screening_available=True,
    )


@router.get("/{appointment_id}/pre-visit-option", response_model=PreVisitOption)
async def get_pre_visit_option(appointment_id: str):
    """Get pre-visit screening option details."""
    appointment = storage.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return PreVisitOption(
        display_text="Complete a quick AI symptom check before your visit (takes 2-3 min)",
        time_estimate="2-3 minutes",
        disclaimers=[
            "Demonstration only, not a medical device",
            "Uses synthetic data for demonstration purposes only",
            "Not a substitute for professional medical advice",
        ],
        start_button_text="Start AI Pre-Visit Screen",
        decline_button_text="Skip for now",
    )
