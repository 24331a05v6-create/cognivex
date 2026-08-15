"""
Cognivex - Event Schema Tests
Phase 2: Tests for event normalization and validation
"""

import pytest
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reconciliation.models import (
    CognitiveEvent,
    normalize_event,
    generate_event_id,
    normalize_timestamp,
    validate_event,
    ValidationError,
    VALID_SOURCES,
    VALID_COGNITIVE_STATES,
    VALID_RELIABILITY
)


class TestNormalizeEvent:
    """Tests for valid event normalization"""
    
    def test_valid_event_normalization(self):
        """Test normalizing a valid event"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        
        assert isinstance(event, CognitiveEvent)
        assert event.source == "camera_a"
        assert event.user_id == "u123"
        assert event.cognitive_state == "focused"
        assert event.confidence == 0.85
        assert event.reliability == "high"
        assert len(event.event_id) == 16  # SHA-256 truncated
    
    def test_whitespace_normalization(self):
        """Test that whitespace is stripped from strings"""
        raw_data = {
            "source": "  camera_a  ",
            "user_id": "  u123  ",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "  focused  ",
            "confidence": 0.85,
            "reliability": "  high  "
        }
        
        event = normalize_event(raw_data)
        
        assert event.source == "camera_a"
        assert event.user_id == "u123"
        assert event.cognitive_state == "focused"
        assert event.reliability == "high"
    
    def test_lowercase_normalization(self):
        """Test that source/state/reliability are normalized to lowercase"""
        raw_data = {
            "source": "CAMERA_A",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "FOCUSED",
            "confidence": 0.85,
            "reliability": "HIGH"
        }
        
        event = normalize_event(raw_data)
        
        assert event.source == "camera_a"
        assert event.cognitive_state == "focused"
        assert event.reliability == "high"
    
    def test_confidence_rounding(self):
        """Test that confidence is rounded to 2 decimal places"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.856789,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        
        assert event.confidence == 0.86


class TestInvalidSource:
    """Tests for invalid source validation"""
    
    def test_missing_source(self):
        """Test missing source field"""
        raw_data = {
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Missing required field: source" in str(excinfo.value)
    
    def test_empty_source(self):
        """Test empty source field"""
        raw_data = {
            "source": "",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Source cannot be empty" in str(excinfo.value)
    
    def test_unsupported_source(self):
        """Test unsupported source value"""
        raw_data = {
            "source": "camera_c",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Invalid source: camera_c" in str(excinfo.value)
        assert "Supported sources:" in str(excinfo.value)


class TestInvalidConfidence:
    """Tests for invalid confidence validation"""
    
    def test_missing_confidence(self):
        """Test missing confidence field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Missing required field: confidence" in str(excinfo.value)
    
    def test_confidence_below_zero(self):
        """Test confidence below 0.0"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": -0.1,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Confidence out of range: -0.1" in str(excinfo.value)
    
    def test_confidence_above_one(self):
        """Test confidence above 1.0"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 1.5,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Confidence out of range: 1.5" in str(excinfo.value)
    
    def test_invalid_confidence_type(self):
        """Test non-numeric confidence value"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": "high",
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Invalid confidence value: high" in str(excinfo.value)


class TestInvalidCognitiveState:
    """Tests for invalid cognitive state validation"""
    
    def test_missing_cognitive_state(self):
        """Test missing cognitive_state field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Missing required field: cognitive_state" in str(excinfo.value)
    
    def test_empty_cognitive_state(self):
        """Test empty cognitive_state field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "cognitive_state cannot be empty" in str(excinfo.value)
    
    def test_unsupported_cognitive_state(self):
        """Test unsupported cognitive_state value"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "sleepy",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Invalid cognitive_state: sleepy" in str(excinfo.value)
        assert "Supported states:" in str(excinfo.value)


class TestInvalidReliability:
    """Tests for invalid reliability validation"""
    
    def test_missing_reliability(self):
        """Test missing reliability field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Missing required field: reliability" in str(excinfo.value)
    
    def test_empty_reliability(self):
        """Test empty reliability field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": ""
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "reliability cannot be empty" in str(excinfo.value)
    
    def test_unsupported_reliability(self):
        """Test unsupported reliability value"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "very_high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Invalid reliability: very_high" in str(excinfo.value)
        assert "Supported values:" in str(excinfo.value)


class TestInvalidTimestamp:
    """Tests for invalid timestamp validation"""
    
    def test_missing_timestamp(self):
        """Test missing timestamp field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Missing required field: timestamp" in str(excinfo.value)
    
    def test_empty_timestamp(self):
        """Test empty timestamp field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "timestamp cannot be empty" in str(excinfo.value)
    
    def test_invalid_timestamp_format(self):
        """Test invalid timestamp format"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "not-a-date",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Invalid timestamp format" in str(excinfo.value)


class TestMissingRequiredFields:
    """Tests for missing required fields"""
    
    def test_missing_user_id(self):
        """Test missing user_id field"""
        raw_data = {
            "source": "camera_a",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "Missing required field: user_id" in str(excinfo.value)
    
    def test_empty_user_id(self):
        """Test empty user_id field"""
        raw_data = {
            "source": "camera_a",
            "user_id": "",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            normalize_event(raw_data)
        assert "user_id cannot be empty" in str(excinfo.value)


class TestDeterministicEventId:
    """Tests for deterministic event ID generation"""
    
    def test_same_input_produces_same_id(self):
        """Test that the same input always produces the same event_id"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event1 = normalize_event(raw_data)
        event2 = normalize_event(raw_data)
        
        assert event1.event_id == event2.event_id
    
    def test_different_inputs_produce_different_ids(self):
        """Test that different inputs produce different event_ids"""
        raw_data1 = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        raw_data2 = {
            "source": "camera_b",  # Different source
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event1 = normalize_event(raw_data1)
        event2 = normalize_event(raw_data2)
        
        assert event1.event_id != event2.event_id
    
    def test_event_id_is_string(self):
        """Test that event_id is a string"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        
        assert isinstance(event.event_id, str)
        assert len(event.event_id) == 16


class TestAllSources:
    """Tests for all supported sources"""
    
    @pytest.mark.parametrize("source", ["camera_a", "camera_b", "ui_log"])
    def test_valid_sources(self, source):
        """Test that all supported sources are accepted"""
        raw_data = {
            "source": source,
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        assert event.source == source


class TestAllCognitiveStates:
    """Tests for all supported cognitive states"""
    
    @pytest.mark.parametrize("state", ["focused", "confused", "distracted"])
    def test_valid_states(self, state):
        """Test that all supported cognitive states are accepted"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": state,
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        assert event.cognitive_state == state


class TestAllReliabilityLevels:
    """Tests for all supported reliability levels"""
    
    @pytest.mark.parametrize("reliability", ["high", "medium", "low"])
    def test_valid_reliability(self, reliability):
        """Test that all supported reliability levels are accepted"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": reliability
        }
        
        event = normalize_event(raw_data)
        assert event.reliability == reliability


class TestTimestampNormalization:
    """Tests for timestamp normalization"""
    
    def test_z_suffix_normalization(self):
        """Test timestamp with Z suffix"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        assert event.timestamp.endswith("Z")
        assert "2024-07-01T10:00:00" in event.timestamp
    
    def test_timezone_offset_normalization(self):
        """Test timestamp with timezone offset"""
        raw_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T12:00:00+02:00",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event = normalize_event(raw_data)
        # Should be normalized to UTC
        assert "10:00:00" in event.timestamp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
