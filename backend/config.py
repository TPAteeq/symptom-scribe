import os
from dotenv import load_dotenv

load_dotenv()

# AWS Configuration (DynamoDB only — AI is now NVIDIA NIM)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# NVIDIA NIM
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL_ID = os.getenv("NVIDIA_MODEL_ID", "meta/llama-4-maverick-17b-128e-instruct")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# DynamoDB Table Names
TABLE_PATIENTS = os.getenv("TABLE_PATIENTS", "symptom_scribe_patients")
TABLE_APPOINTMENTS = os.getenv("TABLE_APPOINTMENTS", "symptom_scribe_appointments")
TABLE_SESSIONS = os.getenv("TABLE_SESSIONS", "symptom_scribe_sessions")
TABLE_SUMMARIES = os.getenv("TABLE_SUMMARIES", "symptom_scribe_summaries")

# Amazon Polly TTS
POLLY_VOICE_ID = os.getenv("POLLY_VOICE_ID", "Ruth") 

# Emergency Keywords (hardcoded — never use AI for this)
EMERGENCY_KEYWORDS = [
    "chest pain", "can't breathe", "unconscious", "bleeding",
    "heart attack", "stroke", "severe pain", "difficulty breathing",
    "choking", "suicide", "overdose", "seizure"
]

# Transcription Provider: "aws" | "deepgram" | "mock"
TRANSCRIPTION_PROVIDER = os.getenv("TRANSCRIPTION_PROVIDER", "aws")

# System Configuration
MAX_CONVERSATION_EXCHANGES = 8  # hard cap; MIN=4 then up to 4 more follow-ups
MIN_CONVERSATION_EXCHANGES = 4  # when to ask "is there anything else?"
RESPONSE_TIMEOUT_SECONDS = 3
SUMMARY_GENERATION_TIMEOUT = 5

# Service Mode Toggle
USE_MOCK_SERVICES = os.getenv("USE_MOCK_SERVICES", "false").lower() == "true"
