"""
Unit tests for the emergency detection service.
SAFETY-CRITICAL: These tests validate that emergency keywords are always detected.
"""

import pytest
from services.emergency_service import EmergencyService, emergency_service
from config import EMERGENCY_KEYWORDS


class TestEmergencyService:
    def setup_method(self):
        self.service = EmergencyService()

    def test_detects_chest_pain(self):
        result = self.service.check_for_emergency("I'm having chest pain")
        assert result.is_emergency is True
        assert "chest pain" in result.detected_keywords

    def test_detects_cant_breathe(self):
        result = self.service.check_for_emergency("I can't breathe")
        assert result.is_emergency is True

    def test_detects_unconscious(self):
        result = self.service.check_for_emergency("My friend is unconscious")
        assert result.is_emergency is True

    def test_detects_bleeding(self):
        result = self.service.check_for_emergency("I'm bleeding heavily")
        assert result.is_emergency is True

    def test_case_insensitive(self):
        result = self.service.check_for_emergency("I'm having CHEST PAIN")
        assert result.is_emergency is True
        assert "chest pain" in result.detected_keywords

    def test_no_false_positive_on_normal_text(self):
        result = self.service.check_for_emergency("I have a headache and runny nose")
        assert result.is_emergency is False
        assert result.detected_keywords == []

    def test_empty_text(self):
        result = self.service.check_for_emergency("")
        assert result.is_emergency is False

    def test_all_keywords_detected_individually(self):
        """Every keyword in the config list must trigger detection."""
        for keyword in EMERGENCY_KEYWORDS:
            result = self.service.check_for_emergency(f"I am experiencing {keyword}")
            assert result.is_emergency is True, f"Failed to detect: {keyword}"
            assert keyword in result.detected_keywords

    def test_multiple_keywords_in_one_text(self):
        result = self.service.check_for_emergency("chest pain and difficulty breathing")
        assert result.is_emergency is True
        assert len(result.detected_keywords) >= 2

    def test_response_message_present_on_emergency(self):
        result = self.service.check_for_emergency("I'm having a heart attack")
        assert "emergency services" in result.response_message.lower() or "911" in result.response_message

    def test_response_message_empty_on_no_emergency(self):
        result = self.service.check_for_emergency("mild headache")
        assert result.response_message == ""

    def test_custom_keywords(self):
        custom_service = EmergencyService(keywords=["test_emergency"])
        result = custom_service.check_for_emergency("this is a test_emergency")
        assert result.is_emergency is True

    def test_keyword_as_substring(self):
        result = self.service.check_for_emergency("experiencing severe pain in my back")
        assert result.is_emergency is True
        assert "severe pain" in result.detected_keywords


class TestGlobalEmergencyService:
    def test_global_instance_exists(self):
        assert emergency_service is not None
        assert isinstance(emergency_service, EmergencyService)

    def test_global_instance_uses_config_keywords(self):
        assert emergency_service.get_keywords() == EMERGENCY_KEYWORDS
