"""
Integration tests for the complete SymptomScribe flow.
Tests the full path: appointments -> sessions -> voice -> summaries -> dashboard
"""

import pytest
import boto3
from moto import mock_aws
from fastapi.testclient import TestClient
from main import app
from services.storage_service import StorageService


@pytest.fixture(autouse=True)
def reset_storage():
    """Reset storage for each test using moto in-memory DynamoDB."""
    with mock_aws():
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        new_storage = StorageService(dynamodb=ddb)

        import services.storage_service as mod
        mod.storage = new_storage
        import routers.appointments as appt_mod
        import routers.sessions as sess_mod
        import routers.summaries as summ_mod
        import routers.voice as voice_mod
        appt_mod.storage = new_storage
        sess_mod.storage = new_storage
        summ_mod.storage = new_storage
        voice_mod.storage = new_storage
        yield


class TestListAppointments:
    def setup_method(self):
        self.client = TestClient(app)

    def test_list_appointments(self):
        response = self.client.get("/api/appointments/")
        assert response.status_code == 200
        appointments = response.json()
        assert len(appointments) == 3
        names = [a["patient_name"] for a in appointments]
        assert "Sarah Johnson" in names
        assert "Michael Chen" in names
        assert "Emily Rodriguez" in names

    def test_get_pre_visit_option(self):
        response = self.client.get("/api/appointments/appt_001/pre-visit-option")
        assert response.status_code == 200
        data = response.json()
        assert "symptom check" in data["display_text"].lower()
        assert len(data["disclaimers"]) >= 3

    def test_pre_visit_option_not_found(self):
        response = self.client.get("/api/appointments/nonexistent/pre-visit-option")
        assert response.status_code == 404


class TestSessionFlow:
    def setup_method(self):
        self.client = TestClient(app)

    def test_start_session(self):
        response = self.client.post(
            "/api/sessions/start?patient_id=patient_001&appointment_id=appt_001"
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "initializing"

    def test_start_session_invalid_appointment(self):
        response = self.client.post(
            "/api/sessions/start?patient_id=patient_001&appointment_id=nonexistent"
        )
        assert response.status_code == 404

    def test_get_session_status(self):
        start_resp = self.client.post(
            "/api/sessions/start?patient_id=patient_001&appointment_id=appt_001"
        )
        session_id = start_resp.json()["session_id"]

        response = self.client.get(f"/api/sessions/{session_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "initializing"
        assert data["exchange_count"] == 0

    def test_end_session(self):
        start_resp = self.client.post(
            "/api/sessions/start?patient_id=patient_001&appointment_id=appt_001"
        )
        session_id = start_resp.json()["session_id"]

        response = self.client.post(f"/api/sessions/{session_id}/end")
        assert response.status_code == 200
        assert response.json()["message"] == "Session ended"


class TestDoctorDashboard:
    def setup_method(self):
        self.client = TestClient(app)

    def test_empty_dashboard(self):
        response = self.client.get("/api/summaries/doctor/doctor_001/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["doctor_id"] == "doctor_001"
        assert len(data["upcoming_appointments"]) == 3
        assert len(data["completed_screenings"]) == 0
        assert all(a["screening_completed"] is False for a in data["upcoming_appointments"])

    def test_unknown_doctor(self):
        response = self.client.get("/api/summaries/doctor/unknown/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data["upcoming_appointments"]) == 0


class TestWebSocket:
    def setup_method(self):
        self.client = TestClient(app)

    def test_websocket_connection(self):
        with self.client.websocket_connect("/api/voice/ws/test_session") as ws:
            data = ws.receive_json()
            assert data["type"] == "connection_established"
            assert data["session_id"] == "test_session"

    def test_websocket_ping_pong(self):
        with self.client.websocket_connect("/api/voice/ws/test_session") as ws:
            ws.receive_json()  # connection_established
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_websocket_start_session_and_text_input(self):
        """Test the full conversation flow using text input."""
        start_resp = self.client.post(
            "/api/sessions/start?patient_id=patient_001&appointment_id=appt_001"
        )
        session_id = start_resp.json()["session_id"]

        with self.client.websocket_connect(f"/api/voice/ws/{session_id}") as ws:
            data = ws.receive_json()
            assert data["type"] == "connection_established"

            ws.send_json({"type": "start_session", "symptom_session_id": session_id})

            data = ws.receive_json()
            assert data["type"] == "ai_response"
            assert "bothering you" in data["text"].lower()

            data = ws.receive_json()
            assert data["type"] == "status_update"
            assert data["status"] == "listening"

            ws.send_json({"type": "text_input", "text": "I have a headache"})

            data = ws.receive_json()
            assert data["type"] == "transcription_result"
            assert data["is_final"] is True

            data = ws.receive_json()
            assert data["type"] == "status_update"
            assert data["status"] == "processing"

            data = ws.receive_json()
            assert data["type"] == "ai_response"
            assert len(data["text"]) > 0

    def test_websocket_emergency_detection(self):
        """Test that emergency keywords trigger emergency response."""
        start_resp = self.client.post(
            "/api/sessions/start?patient_id=patient_001&appointment_id=appt_001"
        )
        session_id = start_resp.json()["session_id"]

        with self.client.websocket_connect(f"/api/voice/ws/{session_id}") as ws:
            ws.receive_json()  # connection_established
            ws.send_json({"type": "start_session", "symptom_session_id": session_id})
            ws.receive_json()  # ai_response (greeting)
            ws.receive_json()  # status_update (listening)

            ws.send_json({"type": "text_input", "text": "I have severe chest pain"})

            ws.receive_json()  # transcription_result

            data = ws.receive_json()
            assert data["type"] == "emergency_detected"
            assert "chest pain" in data["keywords"]
            assert "emergency services" in data["message"].lower() or "911" in data["message"]


class TestVoiceService:
    def setup_method(self):
        self.client = TestClient(app)

    def test_voice_connection_test(self):
        response = self.client.post("/api/voice/test-connection")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "voice service ready"

    def test_health_check(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
