"""
Emergency detection service using hardcoded keyword matching.
SAFETY REQUIREMENT: This service MUST NOT use AI interpretation.
All detection is purely keyword-based against the predefined list.
"""

import logging
from typing import List, Optional

from config import EMERGENCY_KEYWORDS
from models import EmergencyResult

logger = logging.getLogger(__name__)


class EmergencyService:
    def __init__(self, keywords: Optional[List[str]] = None):
        self.keywords = keywords or EMERGENCY_KEYWORDS

    def check_for_emergency(self, text: str) -> EmergencyResult:
        """
        Check transcribed text for emergency keywords.
        Case-insensitive substring matching.
        """
        text_lower = text.lower()
        detected = [kw for kw in self.keywords if kw.lower() in text_lower]

        if detected:
            logger.warning(f"EMERGENCY DETECTED - Keywords: {detected}")
            return EmergencyResult(
                is_emergency=True,
                detected_keywords=detected,
                response_message=(
                    "This sounds urgent. Please call emergency services (911) "
                    "or go to the nearest hospital right away. "
                    "This screening session will now end."
                ),
            )

        return EmergencyResult(
            is_emergency=False,
            detected_keywords=[],
            response_message="",
        )

    def get_keywords(self) -> List[str]:
        return list(self.keywords)


# Global singleton
emergency_service = EmergencyService()
