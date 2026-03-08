"""
Conversation management service.
Mock mode: returns scripted follow-up questions.
Real mode: uses NVIDIA NIM (OpenAI-compatible API) for contextual questions.
"""

import logging
from typing import List
from abc import ABC, abstractmethod

import httpx

from config import (
    USE_MOCK_SERVICES, NVIDIA_API_KEY, NVIDIA_MODEL_ID, NVIDIA_BASE_URL,
    MIN_CONVERSATION_EXCHANGES, MAX_CONVERSATION_EXCHANGES
)
from models import ConversationExchange

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_BASE = (
    "You are Scribe, a warm and caring pre-visit healthcare assistant. "
    "You are talking to a patient just before they see their doctor, "
    "the same way a nurse would check in before the doctor comes in.\n\n"
    "How to speak:\n"
    "- Be warm, human, and natural. Not clinical or robotic.\n"
    "- Acknowledge what the patient says with empathy before asking anything.\n"
    "- Ask ONE short follow-up question at a time.\n"
    "- Use natural phrases like: That sounds tough. Got it. "
    "How long has that been going on? Where exactly does it hurt?\n"
    "- Keep each response to 1 to 2 sentences.\n"
    "- Do not use dashes or em dashes in your responses. "
    "Use commas or short sentences instead.\n\n"
    "Critical rule about follow-up questions:\n"
    "- ALWAYS follow up on the most recent thing the patient just said.\n"
    "- If the patient mentions a NEW symptom or concern, ask about THAT immediately. "
    "Do not go back to an earlier topic until the new one is explored.\n"
    "- Only revisit earlier symptoms if the patient has nothing new to add.\n\n"
    "What to gently gather over the conversation:\n"
    "- When symptoms started\n"
    "- How severe on a scale of 1 to 10\n"
    "- Where on the body\n"
    "- What makes it better or worse\n"
    "- Any other symptoms\n\n"
    "Important:\n"
    "- Never diagnose or recommend treatment or medications.\n\n"
    "Respond naturally to what the patient just said."
)


def _build_system_prompt(patient_name: str = "") -> str:
    prefix = f"The patient's name is {patient_name}. Use their name warmly throughout.\n\n" if patient_name else ""
    return prefix + _SYSTEM_PROMPT_BASE


class BaseConversationService(ABC):
    @abstractmethod
    async def generate_response(self, conversation_history: List[ConversationExchange], patient_name: str = "") -> str:
        ...

    def should_conclude(self, exchange_count: int) -> bool:
        """True when the hard cap is reached."""
        return exchange_count >= MAX_CONVERSATION_EXCHANGES

    def get_initial_greeting(self, patient_name: str = "") -> str:
        if patient_name:
            return (
                f"Hi {patient_name}! I'm Scribe. I'm here to check in with you before your appointment. "
                "What's been going on?"
            )
        return "Hi! I'm Scribe. I'm here to check in with you before your appointment. What's been going on?"

    def get_conclusion_message(self) -> str:
        return (
            "Thank you for sharing that information. I now have a good understanding "
            "of your symptoms. I'll prepare a summary for your doctor. "
            "Is there anything else you'd like to add before we finish?"
        )

    def get_final_message(self) -> str:
        return (
            "Thank you. Your symptom summary is being prepared and will be "
            "available for your doctor before your appointment. Take care!"
        )

    async def evaluate_patient_done(self, text: str) -> bool:
        """Return True if patient indicated they have nothing more to add."""
        return False


class MockConversationService(BaseConversationService):
    """Returns scripted follow-up questions based on exchange count."""

    SCRIPTED_QUESTIONS = [
        "I see. Can you tell me more about when this started?",
        "How would you rate the severity on a scale of 1 to 10?",
        "Has anything made it better or worse?",
        "Have you experienced this before or is this new?",
    ]

    async def generate_response(self, conversation_history: List[ConversationExchange], patient_name: str = "") -> str:
        patient_exchanges = [e for e in conversation_history if e.type == "patient"]
        count = len(patient_exchanges)

        if count >= MAX_CONVERSATION_EXCHANGES:
            return self.get_final_message()
        if count == MIN_CONVERSATION_EXCHANGES:
            return self.get_conclusion_message()

        idx = count - 1
        if 0 <= idx < len(self.SCRIPTED_QUESTIONS):
            return self.SCRIPTED_QUESTIONS[idx]

        return "Got it, thank you for sharing that. Is there anything else on your mind?"


class NvidiaNimConversationService(BaseConversationService):
    """Uses NVIDIA NIM (OpenAI-compatible API) for contextual response generation."""

    def __init__(self):
        self.model_id = NVIDIA_MODEL_ID
        self.headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
        }

    async def generate_response(self, conversation_history: List[ConversationExchange], patient_name: str = "") -> str:
        patient_count = len([e for e in conversation_history if e.type == "patient"])

        # Hard cap reached — say goodbye
        if patient_count >= MAX_CONVERSATION_EXCHANGES:
            return self.get_final_message()

        # At MIN exchanges, ask if there's anything else to add
        if patient_count == MIN_CONVERSATION_EXCHANGES:
            return self.get_conclusion_message()

        # All other exchanges (including follow-ups after wrap-up): AI responds naturally
        messages = [{"role": "system", "content": _build_system_prompt(patient_name)}]
        for exchange in conversation_history:
            role = "user" if exchange.type == "patient" else "assistant"
            messages.append({"role": role, "content": exchange.content})

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{NVIDIA_BASE_URL}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model_id,
                        "messages": messages,
                        "max_tokens": 250,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"NVIDIA NIM conversation error: {e}")
            return "I appreciate you sharing that. Could you tell me a bit more?"

    async def evaluate_patient_done(self, text: str) -> bool:
        """Return True if patient indicated they have nothing more to add."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{NVIDIA_BASE_URL}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model_id,
                        "messages": [{
                            "role": "user",
                            "content": (
                                f'A patient was asked if they had anything else to add before finishing '
                                f'their pre-visit health screening. They replied: "{text}"\n\n'
                                f'Did they indicate they are done or have nothing more to add? '
                                f'Answer only YES or NO.'
                            ),
                        }],
                        "max_tokens": 5,
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                answer = response.json()["choices"][0]["message"]["content"].strip().upper()
                return answer.startswith("YES")
        except Exception as e:
            logger.error(f"evaluate_patient_done error: {e}")
            return False


def get_conversation_service() -> BaseConversationService:
    if USE_MOCK_SERVICES:
        logger.info("Using mock conversation service")
        return MockConversationService()
    logger.info("Using NVIDIA NIM conversation service")
    return NvidiaNimConversationService()


# Global singleton
conversation_service = get_conversation_service()
