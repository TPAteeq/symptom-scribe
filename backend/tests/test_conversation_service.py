"""Unit tests for the conversation service."""

import pytest
from datetime import datetime

from services.conversation_service import MockConversationService, INITIAL_GREETING
from models import ConversationExchange
from config import MIN_CONVERSATION_EXCHANGES, MAX_CONVERSATION_EXCHANGES


class TestMockConversationService:
    def setup_method(self):
        self.service = MockConversationService()

    def test_initial_greeting(self):
        greeting = self.service.get_initial_greeting()
        assert "bothering you" in greeting.lower()

    def test_conclusion_message(self):
        msg = self.service.get_conclusion_message()
        assert len(msg) > 0
        assert "summary" in msg.lower() or "doctor" in msg.lower()

    def test_final_message(self):
        msg = self.service.get_final_message()
        assert len(msg) > 0

    @pytest.mark.asyncio
    async def test_first_response(self):
        history = [
            ConversationExchange(timestamp=datetime.now(), type="ai", content=INITIAL_GREETING),
            ConversationExchange(timestamp=datetime.now(), type="patient", content="I have a headache"),
        ]
        response = await self.service.generate_response(history)
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_scripted_questions_are_different(self):
        """Each follow-up should be a different question."""
        responses = []
        history = [
            ConversationExchange(timestamp=datetime.now(), type="ai", content=INITIAL_GREETING),
        ]
        for i in range(3):
            history.append(ConversationExchange(
                timestamp=datetime.now(), type="patient", content=f"Response {i}"
            ))
            resp = await self.service.generate_response(history)
            responses.append(resp)
            history.append(ConversationExchange(
                timestamp=datetime.now(), type="ai", content=resp
            ))
        assert len(set(responses)) >= 2

    @pytest.mark.asyncio
    async def test_wraps_up_at_min_exchanges(self):
        """After MIN_CONVERSATION_EXCHANGES patient messages, should start wrapping up."""
        history = [
            ConversationExchange(timestamp=datetime.now(), type="ai", content=INITIAL_GREETING),
        ]
        for i in range(MIN_CONVERSATION_EXCHANGES):
            history.append(ConversationExchange(
                timestamp=datetime.now(), type="patient", content=f"Response {i}"
            ))
            history.append(ConversationExchange(
                timestamp=datetime.now(), type="ai", content=f"Question {i}"
            ))

        history.append(ConversationExchange(
            timestamp=datetime.now(), type="patient", content="Final response"
        ))
        response = await self.service.generate_response(history)
        conclusion = self.service.get_conclusion_message()
        assert response == conclusion

    def test_should_conclude_at_max(self):
        assert self.service.should_conclude(MAX_CONVERSATION_EXCHANGES) is True
        assert self.service.should_conclude(MAX_CONVERSATION_EXCHANGES - 1) is False

    def test_should_wrap_up_at_min(self):
        assert self.service.should_start_wrapping_up(MIN_CONVERSATION_EXCHANGES) is True
        assert self.service.should_start_wrapping_up(MIN_CONVERSATION_EXCHANGES - 1) is False
