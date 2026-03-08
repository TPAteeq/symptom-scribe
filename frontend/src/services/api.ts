/**
 * HTTP API client for SymptomScribe backend.
 * All requests go through the Vite proxy (/api -> localhost:8000).
 */

import type { PreVisitOption, ClinicalSummary, DoctorDashboard } from '../types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

// --- Appointments ---

export interface AppointmentDisplay {
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  appointment_time: string;
  appointment_type: string;
  status: string;
}

export async function listAppointments(): Promise<AppointmentDisplay[]> {
  return request<AppointmentDisplay[]>('/appointments/');
}

export async function createWalkIn(patientName: string): Promise<{ patient_id: string; appointment_id: string }> {
  return request('/appointments/walk-in', {
    method: 'POST',
    body: JSON.stringify({ patient_name: patientName }),
  });
}

export async function getPreVisitOption(appointmentId: string): Promise<PreVisitOption> {
  return request<PreVisitOption>(`/appointments/${appointmentId}/pre-visit-option`);
}

// --- Sessions ---

export interface StartSessionResponse {
  session_id: string;
  status: string;
}

export async function startSession(patientId: string, appointmentId: string): Promise<StartSessionResponse> {
  return request<StartSessionResponse>(
    `/sessions/start?patient_id=${encodeURIComponent(patientId)}&appointment_id=${encodeURIComponent(appointmentId)}`,
    { method: 'POST' }
  );
}

export async function endSession(sessionId: string): Promise<{ message: string; session_id: string; summary_id?: string }> {
  return request(`/sessions/${sessionId}/end`, { method: 'POST' });
}

// --- Summaries ---

export async function getSummary(summaryId: string): Promise<ClinicalSummary> {
  return request<ClinicalSummary>(`/summaries/${summaryId}`);
}

export async function getDoctorDashboard(doctorId: string): Promise<DoctorDashboard> {
  return request<DoctorDashboard>(`/summaries/doctor/${doctorId}/dashboard`);
}
