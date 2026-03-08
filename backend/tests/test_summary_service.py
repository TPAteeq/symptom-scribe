"""Unit tests for the summary generation service."""

import pytest
from datetime import datetime

from services.summary_service import MockSummaryService
from models import ConversationExchange, ClinicalSummary, SeverityFlag


class TestMockSummaryService:
    def setup_method(self):
        self.service = MockSummaryService()

    @pytest.mark.asyncio
    async def test_generates_valid_summary(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="ai", content="What is bothering you?"),
            ConversationExchange(timestamp=datetime.now(), type="patient", content="I have a bad headache for 3 days"),
            ConversationExchange(timestamp=datetime.now(), type="ai", content="How severe is it?"),
            ConversationExchange(timestamp=datetime.now(), type="patient", content="About a 6 out of 10"),
        ]
        summary = await self.service.generate_summary("p1", "a1", history)
        assert isinstance(summary, ClinicalSummary)
        assert summary.patient_id == "p1"
        assert summary.appointment_id == "a1"
        assert summary.chief_complaint != ""
        assert len(summary.symptom_details) > 0
        assert summary.severity_flag in [SeverityFlag.LOW, SeverityFlag.MEDIUM, SeverityFlag.HIGH]

    @pytest.mark.asyncio
    async def test_emergency_flag_sets_high_severity(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="patient", content="chest pain"),
        ]
        summary = await self.service.generate_summary("p1", "a1", history, emergency_detected=True)
        assert summary.emergency_flag is True
        assert summary.severity_flag == SeverityFlag.HIGH

    @pytest.mark.asyncio
    async def test_summary_has_required_fields(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="patient", content="headache"),
        ]
        summary = await self.service.generate_summary("p1", "a1", history)
        assert summary.summary_id is not None
        assert summary.timestamp is not None
        assert summary.conversation_exchanges == len(history)
        assert isinstance(summary.symptom_details, list)
        assert isinstance(summary.relevant_history, list)

    @pytest.mark.asyncio
    async def test_duration_extraction(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="patient", content="pain for several days now"),
        ]
        summary = await self.service.generate_summary("p1", "a1", history)
        assert summary.symptom_details[0].duration == "Several days"

    @pytest.mark.asyncio
    async def test_high_severity_keywords(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="patient", content="severe unbearable pain"),
        ]
        summary = await self.service.generate_summary("p1", "a1", history)
        assert summary.severity_flag == SeverityFlag.HIGH

    @pytest.mark.asyncio
    async def test_low_severity_default(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="patient", content="mild discomfort"),
        ]
        summary = await self.service.generate_summary("p1", "a1", history)
        assert summary.severity_flag == SeverityFlag.LOW

    @pytest.mark.asyncio
    async def test_empty_conversation(self):
        summary = await self.service.generate_summary("p1", "a1", [])
        assert summary.chief_complaint == "No complaint recorded"
        assert summary.conversation_exchanges == 0
