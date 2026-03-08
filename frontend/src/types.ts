export interface ConversationExchange {
  timestamp: Date;
  type: 'patient' | 'ai';
  content: string;
  confidence?: number;
}

export interface EmergencyResult {
  is_emergency: boolean;
  detected_keywords: string[];
  response_message: string;
}

export interface TranscriptionResult {
  text: string;
  confidence: number;
  is_final: boolean;
  timestamp: Date;
}

export enum SessionStatus {
  INITIALIZING = 'initializing',
  LISTENING = 'listening',
  PROCESSING = 'processing',
  SPEAKING = 'speaking',
  COMPLETED = 'completed',
  EMERGENCY = 'emergency'
}

export interface SessionStatusModel {
  state: SessionStatus;
  exchange_count: number;
  last_activity: Date;
}

export enum SeverityFlag {
  LOW = 'Low',
  MEDIUM = 'Medium',
  HIGH = 'High'
}

export interface SymptomDetail {
  symptom: string;
  duration?: string;
  severity?: string;
  location?: string;
  aggravating_factors?: string[];
  relieving_factors?: string[];
}

export interface ClinicalSummary {
  summary_id: string;
  patient_id: string;
  appointment_id: string;
  timestamp: Date;
  chief_complaint: string;
  symptom_details: SymptomDetail[];
  relevant_history: string[];
  severity_flag: SeverityFlag;
  emergency_flag?: boolean;
  conversation_exchanges: number;
}

export interface AppointmentDetails {
  appointment_id: string;
  patient_id: string;
  doctor_id: string;
  appointment_time: Date;
  appointment_type: string;
  status: string;
}

export interface BookingConfirmation {
  appointment_id: string;
  appointment_time: Date;
  doctor_name: string;
  pre_visit_screening_available: boolean;
}

export interface PreVisitOption {
  display_text: string;
  time_estimate: string;
  disclaimers: string[];
  start_button_text: string;
  decline_button_text: string;
}

export interface AppointmentSummary {
  appointment_id: string;
  patient_name: string;
  appointment_time: Date;
  screening_completed: boolean;
  summary_available: boolean;
  severity_flag?: SeverityFlag;
}

export interface DoctorDashboard {
  doctor_id: string;
  upcoming_appointments: AppointmentSummary[];
  completed_screenings: ClinicalSummary[];
}