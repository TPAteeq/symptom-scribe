from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    INITIALIZING = "initializing"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    EMERGENCY = "emergency"

class SeverityFlag(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class ConversationExchange(BaseModel):
    timestamp: datetime
    type: str  # 'patient' or 'ai'
    content: str
    confidence: Optional[float] = None

class EmergencyResult(BaseModel):
    is_emergency: bool
    detected_keywords: List[str]
    response_message: str

class TranscriptionResult(BaseModel):
    text: str
    confidence: float
    is_final: bool
    timestamp: datetime

class SessionStatusModel(BaseModel):
    state: SessionStatus
    exchange_count: int
    last_activity: datetime

class SymptomDetail(BaseModel):
    symptom: str
    duration: Optional[str] = None
    severity: Optional[str] = None
    location: Optional[str] = None
    aggravating_factors: Optional[List[str]] = None
    relieving_factors: Optional[List[str]] = None

class ClinicalSummary(BaseModel):
    summary_id: str
    patient_id: str
    appointment_id: str
    timestamp: datetime
    chief_complaint: str
    symptom_details: List[SymptomDetail]
    relevant_history: List[str]
    severity_flag: SeverityFlag
    emergency_flag: Optional[bool] = False
    conversation_exchanges: int

class SymptomSession(BaseModel):
    session_id: str
    patient_id: str
    appointment_id: str
    status: SessionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    conversation_history: List[ConversationExchange]
    emergency_detected: bool = False
    summary_generated: bool = False

class AppointmentDetails(BaseModel):
    appointment_id: str
    patient_id: str
    doctor_id: str
    appointment_time: datetime
    appointment_type: str
    status: str = "scheduled"

class SyntheticPatient(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: str
    appointment_id: str
    appointment_time: datetime
    doctor_id: str
    medical_history: Optional[List[str]] = None

class BookingConfirmation(BaseModel):
    appointment_id: str
    appointment_time: datetime
    doctor_name: str
    pre_visit_screening_available: bool

class PreVisitOption(BaseModel):
    display_text: str
    time_estimate: str
    disclaimers: List[str]
    start_button_text: str
    decline_button_text: str

class AppointmentSummary(BaseModel):
    appointment_id: str
    patient_name: str
    appointment_time: datetime
    screening_completed: bool
    summary_available: bool
    severity_flag: Optional[SeverityFlag] = None

class DoctorDashboard(BaseModel):
    doctor_id: str
    upcoming_appointments: List[AppointmentSummary]
    completed_screenings: List[ClinicalSummary]