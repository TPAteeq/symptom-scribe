"""
Clinical summary generation service.
Mock: generates structured summary from conversation keywords.
Real: uses NVIDIA NIM (OpenAI-compatible API) for AI-powered summary generation.
"""

import json
import logging
from typing import List
from datetime import datetime
from abc import ABC, abstractmethod

import httpx

from config import USE_MOCK_SERVICES, NVIDIA_API_KEY, NVIDIA_MODEL_ID, NVIDIA_BASE_URL
from models import (
    ClinicalSummary, ConversationExchange, SymptomDetail, SeverityFlag
)

logger = logging.getLogger(__name__)


class BaseSummaryService(ABC):
    @abstractmethod
    async def generate_summary(
        self,
        patient_id: str,
        appointment_id: str,
        conversation_history: List[ConversationExchange],
        emergency_detected: bool = False,
    ) -> ClinicalSummary:
        ...


class MockSummaryService(BaseSummaryService):
    """Generates a structured summary from conversation content using keyword extraction."""

    async def generate_summary(
        self,
        patient_id: str,
        appointment_id: str,
        conversation_history: List[ConversationExchange],
        emergency_detected: bool = False,
    ) -> ClinicalSummary:
        patient_messages = [e.content for e in conversation_history if e.type == "patient"]
        combined_text = " ".join(patient_messages).lower()

        chief_complaint = patient_messages[0] if patient_messages else "No complaint recorded"

        symptom_details = [
            SymptomDetail(
                symptom=chief_complaint[:100],
                duration=self._extract_duration(combined_text),
                severity=self._extract_severity_text(combined_text),
            )
        ]

        severity_flag = self._assess_severity(combined_text, emergency_detected)

        return ClinicalSummary(
            summary_id=f"summary_{appointment_id}",
            patient_id=patient_id,
            appointment_id=appointment_id,
            timestamp=datetime.now(),
            chief_complaint=chief_complaint,
            symptom_details=symptom_details,
            relevant_history=[],
            severity_flag=severity_flag,
            emergency_flag=emergency_detected,
            conversation_exchanges=len(conversation_history),
        )

    def _extract_duration(self, text: str) -> str:
        duration_keywords = {
            "days": "Several days",
            "weeks": "Several weeks",
            "hours": "Several hours",
            "month": "About a month",
        }
        for kw, label in duration_keywords.items():
            if kw in text:
                return label
        return "Not specified"

    def _extract_severity_text(self, text: str) -> str:
        for i in range(10, 6, -1):
            if str(i) in text:
                return f"{i}/10"
        for i in range(6, 0, -1):
            if str(i) in text:
                return f"{i}/10"
        return "Not specified"

    def _assess_severity(self, text: str, emergency: bool) -> SeverityFlag:
        if emergency:
            return SeverityFlag.HIGH
        high_indicators = ["severe", "worst", "unbearable", "10", "9", "8"]
        medium_indicators = ["moderate", "7", "6", "5", "getting worse", "spreading"]
        for indicator in high_indicators:
            if indicator in text:
                return SeverityFlag.HIGH
        for indicator in medium_indicators:
            if indicator in text:
                return SeverityFlag.MEDIUM
        return SeverityFlag.LOW


class NvidiaNimSummaryService(BaseSummaryService):
    """Uses NVIDIA NIM (OpenAI-compatible API) to generate clinical summaries."""

    def __init__(self):
        self.model_id = NVIDIA_MODEL_ID
        self.headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
        }

    async def generate_summary(
        self,
        patient_id: str,
        appointment_id: str,
        conversation_history: List[ConversationExchange],
        emergency_detected: bool = False,
    ) -> ClinicalSummary:
        transcript = "\n".join(
            f"{'Patient' if e.type == 'patient' else 'AI'}: {e.content}"
            for e in conversation_history
        )

        prompt = (
            "Analyze this pre-visit symptom screening conversation and generate a clinical summary.\n\n"
            f"Conversation transcript:\n{transcript}\n\n"
            "Respond with ONLY a JSON object, no markdown, no extra text:\n"
            '{"chief_complaint": "Brief 1-sentence chief complaint",'
            '"symptom_details": [{"symptom": "Primary symptom", "duration": "Duration if mentioned",'
            '"severity": "Severity if mentioned", "location": "Location if mentioned"}],'
            '"relevant_history": ["Any relevant history mentioned"],'
            '"severity_flag": "Low"}\n\n'
            'severity_flag must be exactly "Low", "Medium", or "High".'
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{NVIDIA_BASE_URL}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                result_text = response.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown code fences if present
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                result_text = result_text.rsplit("```", 1)[0].strip()

            data = json.loads(result_text)
            symptom_details = [SymptomDetail(**sd) for sd in data.get("symptom_details", [])]
            severity_flag = SeverityFlag(data.get("severity_flag", "Low"))

            return ClinicalSummary(
                summary_id=f"summary_{appointment_id}",
                patient_id=patient_id,
                appointment_id=appointment_id,
                timestamp=datetime.now(),
                chief_complaint=data.get("chief_complaint", "Not determined"),
                symptom_details=symptom_details,
                relevant_history=data.get("relevant_history", []),
                severity_flag=severity_flag,
                emergency_flag=emergency_detected,
                conversation_exchanges=len(conversation_history),
            )
        except Exception as e:
            logger.error(f"NVIDIA NIM summary error: {e}")
            fallback = MockSummaryService()
            return await fallback.generate_summary(
                patient_id, appointment_id, conversation_history, emergency_detected
            )


def get_summary_service() -> BaseSummaryService:
    if USE_MOCK_SERVICES:
        logger.info("Using mock summary service")
        return MockSummaryService()
    logger.info("Using NVIDIA NIM summary service")
    return NvidiaNimSummaryService()


# Global singleton
summary_service = get_summary_service()
