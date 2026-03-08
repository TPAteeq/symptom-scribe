"""Unit tests for the DynamoDB-backed storage service."""

import os
import pytest
from datetime import datetime

import boto3
from moto import mock_aws

from services.storage_service import StorageService
from models import (
    SymptomSession, SessionStatus, ConversationExchange,
    ClinicalSummary, SeverityFlag, SymptomDetail
)


class TestStorageService:
    def setup_method(self):
        self.mock = mock_aws()
        self.mock.start()
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        self.storage = StorageService(dynamodb=ddb)

    def teardown_method(self):
        self.mock.stop()

    def test_synthetic_data_seeded(self):
        assert self.storage.get_patient("patient_001") is not None
        assert self.storage.get_patient("patient_002") is not None
        assert self.storage.get_patient("patient_003") is not None
        assert self.storage.get_appointment("appt_001") is not None
        assert self.storage.get_appointment("appt_002") is not None
        assert self.storage.get_appointment("appt_003") is not None

    def test_synthetic_patient_names(self):
        assert self.storage.get_patient("patient_001").name == "Sarah Johnson"
        assert self.storage.get_patient("patient_002").name == "Michael Chen"
        assert self.storage.get_patient("patient_003").name == "Emily Rodriguez"

    def test_create_and_get_session(self):
        session = self.storage.create_session("sess_1", "patient_001", "appt_001")
        assert session.session_id == "sess_1"
        assert session.patient_id == "patient_001"
        assert session.status == SessionStatus.INITIALIZING
        retrieved = self.storage.get_session("sess_1")
        assert retrieved is not None
        assert retrieved.session_id == "sess_1"

    def test_get_nonexistent_session(self):
        assert self.storage.get_session("nonexistent") is None

    def test_update_session(self):
        session = self.storage.create_session("sess_1", "patient_001", "appt_001")
        session.status = SessionStatus.LISTENING
        self.storage.update_session(session)
        retrieved = self.storage.get_session("sess_1")
        assert retrieved.status == SessionStatus.LISTENING

    def test_add_exchange(self):
        self.storage.create_session("sess_1", "patient_001", "appt_001")
        exchange = ConversationExchange(
            timestamp=datetime.now(), type="ai", content="What is bothering you?"
        )
        self.storage.add_exchange("sess_1", exchange)
        session = self.storage.get_session("sess_1")
        assert len(session.conversation_history) == 1
        assert session.conversation_history[0].content == "What is bothering you?"

    def test_add_multiple_exchanges(self):
        self.storage.create_session("sess_1", "patient_001", "appt_001")
        for i in range(3):
            exchange = ConversationExchange(
                timestamp=datetime.now(), type="patient", content=f"Message {i}"
            )
            self.storage.add_exchange("sess_1", exchange)
        session = self.storage.get_session("sess_1")
        assert len(session.conversation_history) == 3

    def test_get_appointment(self):
        appt = self.storage.get_appointment("appt_001")
        assert appt is not None
        assert appt.patient_id == "patient_001"

    def test_get_nonexistent_appointment(self):
        assert self.storage.get_appointment("nonexistent") is None

    def test_get_appointments_by_doctor(self):
        appts = self.storage.get_appointments_by_doctor("doctor_001")
        assert len(appts) == 3

    def test_get_appointments_by_unknown_doctor(self):
        appts = self.storage.get_appointments_by_doctor("unknown")
        assert len(appts) == 0

    def test_get_patient(self):
        patient = self.storage.get_patient("patient_001")
        assert patient is not None
        assert patient.name == "Sarah Johnson"
        assert patient.age == 34

    def test_store_and_retrieve_summary(self):
        summary = ClinicalSummary(
            summary_id="sum_1",
            patient_id="patient_001",
            appointment_id="appt_001",
            timestamp=datetime.now(),
            chief_complaint="Headache",
            symptom_details=[SymptomDetail(symptom="Headache")],
            relevant_history=["Seasonal allergies"],
            severity_flag=SeverityFlag.LOW,
            conversation_exchanges=4,
        )
        self.storage.store_summary(summary)
        retrieved = self.storage.get_summary("sum_1")
        assert retrieved is not None
        assert retrieved.chief_complaint == "Headache"

    def test_get_summary_by_appointment(self):
        summary = ClinicalSummary(
            summary_id="sum_1",
            patient_id="patient_001",
            appointment_id="appt_001",
            timestamp=datetime.now(),
            chief_complaint="Headache",
            symptom_details=[],
            relevant_history=[],
            severity_flag=SeverityFlag.LOW,
            conversation_exchanges=4,
        )
        self.storage.store_summary(summary)
        retrieved = self.storage.get_summary_by_appointment("appt_001")
        assert retrieved is not None
        assert retrieved.summary_id == "sum_1"

    def test_get_appointment_summaries_for_doctor(self):
        summaries = self.storage.get_appointment_summaries_for_doctor("doctor_001")
        assert len(summaries) == 3
        assert all(s.screening_completed is False for s in summaries)

    def test_get_appointment_summaries_after_screening(self):
        summary = ClinicalSummary(
            summary_id="sum_1",
            patient_id="patient_001",
            appointment_id="appt_001",
            timestamp=datetime.now(),
            chief_complaint="Headache",
            symptom_details=[],
            relevant_history=[],
            severity_flag=SeverityFlag.MEDIUM,
            conversation_exchanges=4,
        )
        self.storage.store_summary(summary)
        summaries = self.storage.get_appointment_summaries_for_doctor("doctor_001")
        completed = [s for s in summaries if s.screening_completed]
        assert len(completed) == 1
        assert completed[0].severity_flag == SeverityFlag.MEDIUM
