"""
Text-to-speech service.
Mock: returns empty bytes (frontend displays text instead).
Real: uses Amazon Polly for voice synthesis.
"""

import logging
from abc import ABC, abstractmethod

import boto3

from config import USE_MOCK_SERVICES, AWS_REGION, POLLY_VOICE_ID

logger = logging.getLogger(__name__)


class BaseTTSService(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert text to audio bytes (mp3 format)."""
        ...


class MockTTSService(BaseTTSService):
    """Returns empty bytes for mock mode. Frontend will display text instead."""

    async def synthesize(self, text: str) -> bytes:
        logger.info(f"Mock TTS: '{text[:50]}...'")
        return b""


class PollyTTSService(BaseTTSService):
    """Uses Amazon Polly neural TTS for voice synthesis."""

    def __init__(self):
        self.client = boto3.client("polly", region_name=AWS_REGION)
        self.voice_id = POLLY_VOICE_ID

    async def synthesize(self, text: str) -> bytes:
        try:
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=self.voice_id,
                Engine="neural",
            )
            return response["AudioStream"].read()
        except Exception as e:
            logger.error(f"Polly TTS error: {e}")
            return b""


def get_tts_service() -> BaseTTSService:
    if USE_MOCK_SERVICES:
        logger.info("Using mock TTS service")
        return MockTTSService()
    logger.info("Using Amazon Polly TTS service")
    return PollyTTSService()


# Global singleton
tts_service = get_tts_service()
