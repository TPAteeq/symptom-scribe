"""
Unit tests for the AWS Transcribe streaming service
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from services.transcription_service import (
    TranscribeStreamingService,
    TranscriptionManager,
    transcription_manager
)
from models import TranscriptionResult


class TestTranscribeStreamingService:
    """Test cases for TranscribeStreamingService"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = TranscribeStreamingService()
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_chunk_success(self):
        """Test successful audio chunk transcription"""
        # Arrange
        audio_data = b"fake_audio_data"
        
        # Act
        result = await self.service.transcribe_audio_chunk(audio_data)
        
        # Assert
        assert isinstance(result, TranscriptionResult)
        assert result.text == f"[Transcribed audio chunk of {len(audio_data)} bytes]"
        assert result.confidence == 0.95
        assert result.is_final is True
        assert isinstance(result.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_transcribe_empty_audio_chunk(self):
        """Test transcription with empty audio data"""
        # Arrange
        audio_data = b""
        
        # Act
        result = await self.service.transcribe_audio_chunk(audio_data)
        
        # Assert
        assert isinstance(result, TranscriptionResult)
        assert result.text == "[Transcribed audio chunk of 0 bytes]"
        assert result.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_start_streaming_transcription(self):
        """Test starting a streaming transcription session"""
        # Arrange
        session_id = "test_session_123"
        
        # Act
        config = await self.service.start_streaming_transcription(session_id)
        
        # Assert
        assert config['session_id'] == session_id
        assert config['language_code'] == 'en-US'
        assert config['sample_rate'] == 16000
        assert config['media_format'] == 'pcm'
        assert config['status'] == 'active'
        assert 'created_at' in config
    
    def test_validate_audio_format_valid(self):
        """Test audio format validation with valid data"""
        # Arrange
        audio_data = b"valid_audio_data"
        
        # Act
        is_valid = self.service.validate_audio_format(audio_data)
        
        # Assert
        assert is_valid is True
    
    def test_validate_audio_format_empty(self):
        """Test audio format validation with empty data"""
        # Arrange
        audio_data = b""
        
        # Act
        is_valid = self.service.validate_audio_format(audio_data)
        
        # Assert
        assert is_valid is False
    
    def test_validate_audio_format_none(self):
        """Test audio format validation with None data"""
        # Arrange
        audio_data = None
        
        # Act
        is_valid = self.service.validate_audio_format(audio_data)
        
        # Assert
        assert is_valid is False


class TestTranscriptionManager:
    """Test cases for TranscriptionManager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = TranscriptionManager()
    
    @pytest.mark.asyncio
    async def test_start_session_success(self):
        """Test successful session start"""
        # Arrange
        session_id = "test_session_456"
        callback = AsyncMock()
        
        # Act
        config = await self.manager.start_session(session_id, callback)
        
        # Assert
        assert config['session_id'] == session_id
        assert session_id in self.manager.active_sessions
        assert self.manager.active_sessions[session_id]['active'] is True
        assert self.manager.active_sessions[session_id]['callback'] == callback
        assert self.manager.active_sessions[session_id]['transcription_count'] == 0
    
    @pytest.mark.asyncio
    async def test_start_session_duplicate(self):
        """Test starting a session that already exists"""
        # Arrange
        session_id = "test_session_duplicate"
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        
        # Act
        config1 = await self.manager.start_session(session_id, callback1)
        config2 = await self.manager.start_session(session_id, callback2)
        
        # Assert
        assert config1 == config2
        assert len(self.manager.active_sessions) == 1
    
    @pytest.mark.asyncio
    async def test_process_audio_chunk_success(self):
        """Test successful audio chunk processing"""
        # Arrange
        session_id = "test_session_audio"
        callback = AsyncMock()
        audio_data = b"test_audio_data"
        
        await self.manager.start_session(session_id, callback)
        
        # Act
        result = await self.manager.process_audio_chunk(session_id, audio_data)
        
        # Assert
        assert isinstance(result, TranscriptionResult)
        assert result.text == f"[Transcribed audio chunk of {len(audio_data)} bytes]"
        assert self.manager.active_sessions[session_id]['transcription_count'] == 1
        
        # Verify callback was called
        callback.assert_called_once_with(result)
    
    @pytest.mark.asyncio
    async def test_process_audio_chunk_no_session(self):
        """Test processing audio chunk for non-existent session"""
        # Arrange
        session_id = "non_existent_session"
        audio_data = b"test_audio_data"
        
        # Act
        result = await self.manager.process_audio_chunk(session_id, audio_data)
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_process_audio_chunk_invalid_audio(self):
        """Test processing invalid audio data"""
        # Arrange
        session_id = "test_session_invalid_audio"
        callback = AsyncMock()
        audio_data = b""  # Empty audio data
        
        await self.manager.start_session(session_id, callback)
        
        # Act
        result = await self.manager.process_audio_chunk(session_id, audio_data)
        
        # Assert
        assert result is None
        assert self.manager.active_sessions[session_id]['transcription_count'] == 0
    
    @pytest.mark.asyncio
    async def test_end_session_success(self):
        """Test successful session termination"""
        # Arrange
        session_id = "test_session_end"
        callback = AsyncMock()
        
        await self.manager.start_session(session_id, callback)
        
        # Act
        success = await self.manager.end_session(session_id)
        
        # Assert
        assert success is True
        assert session_id not in self.manager.active_sessions
    
    @pytest.mark.asyncio
    async def test_end_session_not_found(self):
        """Test ending a non-existent session"""
        # Arrange
        session_id = "non_existent_session"
        
        # Act
        success = await self.manager.end_session(session_id)
        
        # Assert
        assert success is False
    
    def test_get_active_sessions(self):
        """Test getting active sessions"""
        # Arrange - start multiple sessions
        session_ids = ["session1", "session2", "session3"]
        
        # Act
        for session_id in session_ids:
            asyncio.run(self.manager.start_session(session_id))
        
        active_sessions = self.manager.get_active_sessions()
        
        # Assert
        assert len(active_sessions) == 3
        for session_id in session_ids:
            assert session_id in active_sessions
            assert active_sessions[session_id]['active'] is True
    
    def test_get_session_info(self):
        """Test getting session information"""
        # Arrange
        session_id = "test_session_info"
        
        # Act
        asyncio.run(self.manager.start_session(session_id))
        session_info = self.manager.get_session_info(session_id)
        
        # Assert
        assert session_info is not None
        assert session_info['active'] is True
        assert session_info['transcription_count'] == 0
        assert 'last_activity' in session_info
    
    def test_get_session_info_not_found(self):
        """Test getting info for non-existent session"""
        # Arrange
        session_id = "non_existent_session"
        
        # Act
        session_info = self.manager.get_session_info(session_id)
        
        # Assert
        assert session_info is None


class TestGlobalTranscriptionManager:
    """Test cases for the global transcription manager instance"""
    
    def test_global_instance_exists(self):
        """Test that the global transcription manager instance exists"""
        assert transcription_manager is not None
        assert isinstance(transcription_manager, TranscriptionManager)
    
    @pytest.mark.asyncio
    async def test_global_instance_functionality(self):
        """Test that the global instance works correctly"""
        # Arrange
        session_id = "global_test_session"
        
        # Act
        config = await transcription_manager.start_session(session_id)
        active_sessions = transcription_manager.get_active_sessions()
        success = await transcription_manager.end_session(session_id)
        
        # Assert
        assert config['session_id'] == session_id
        assert session_id in active_sessions
        assert success is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])