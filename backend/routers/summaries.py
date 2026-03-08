from fastapi import APIRouter, HTTPException
from models import ClinicalSummary, DoctorDashboard
from services.storage_service import storage

router = APIRouter()


@router.get("/doctor/{doctor_id}/dashboard", response_model=DoctorDashboard)
async def get_doctor_dashboard(doctor_id: str):
    """Get doctor dashboard with appointments and summaries."""
    appointment_summaries = storage.get_appointment_summaries_for_doctor(doctor_id)
    completed_summaries = storage.get_summaries_by_doctor(doctor_id)

    return DoctorDashboard(
        doctor_id=doctor_id,
        upcoming_appointments=appointment_summaries,
        completed_screenings=completed_summaries,
    )


@router.get("/{summary_id}", response_model=ClinicalSummary)
async def get_summary(summary_id: str):
    """Get clinical summary by ID."""
    summary = storage.get_summary(summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary
