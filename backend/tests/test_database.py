"""
Cognivex - Storage Layer Tests
Phase 3: Tests for SQLite event storage
"""

import pytest
import tempfile
import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reconciliation.models import CognitiveEvent, normalize_event
from storage.database import (
    initialize_database,
    save_event,
    get_event,
    get_events_for_user,
    get_all_events,
    delete_all_events
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    # Create a temporary file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Initialize the database
    initialize_database(db_path)
    
    yield db_path
    
    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sample_event():
    """Create a sample CognitiveEvent"""
    return normalize_event({
        "source": "camera_a",
        "user_id": "u123",
        "timestamp": "2024-07-01T10:00:00Z",
        "cognitive_state": "focused",
        "confidence": 0.85,
        "reliability": "high"
    })


class TestDatabaseInitialization:
    """Tests for database initialization"""
    
    def test_initialize_database_creates_file(self, temp_db):
        """Test that initialize_database creates the database file"""
        assert os.path.exists(temp_db)
    
    def test_initialize_database_creates_table(self, temp_db):
        """Test that initialize_database creates the events table"""
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        )
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        assert result[0] == 'events'
    
    def test_initialize_database_is_idempotent(self, temp_db):
        """Test that calling initialize_database multiple times is safe"""
        # Call it multiple times
        initialize_database(temp_db)
        initialize_database(temp_db)
        initialize_database(temp_db)
        
        # Should still work
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        )
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None


class TestSaveEvent:
    """Tests for saving events"""
    
    def test_save_one_event(self, temp_db, sample_event):
        """Test saving a single event"""
        result = save_event(sample_event, temp_db)
        
        assert result is True
        
        # Verify it was saved
        retrieved = get_event(sample_event.event_id, temp_db)
        assert retrieved is not None
        assert retrieved.event_id == sample_event.event_id
    
    def test_save_duplicate_event_returns_false(self, temp_db, sample_event):
        """Test that saving a duplicate event returns False"""
        result1 = save_event(sample_event, temp_db)
        result2 = save_event(sample_event, temp_db)
        
        assert result1 is True
        assert result2 is False
    
    def test_save_duplicate_event_no_duplicate_row(self, temp_db, sample_event):
        """Test that duplicate events don't create multiple rows"""
        save_event(sample_event, temp_db)
        save_event(sample_event, temp_db)
        save_event(sample_event, temp_db)
        
        all_events = get_all_events(temp_db)
        
        assert len(all_events) == 1


class TestGetEvent:
    """Tests for retrieving events"""
    
    def test_get_event_by_id(self, temp_db, sample_event):
        """Test retrieving an event by event_id"""
        save_event(sample_event, temp_db)
        
        retrieved = get_event(sample_event.event_id, temp_db)
        
        assert retrieved is not None
        assert retrieved.event_id == sample_event.event_id
        assert retrieved.source == sample_event.source
        assert retrieved.user_id == sample_event.user_id
        assert retrieved.timestamp == sample_event.timestamp
        assert retrieved.cognitive_state == sample_event.cognitive_state
        assert retrieved.confidence == sample_event.confidence
        assert retrieved.reliability == sample_event.reliability
    
    def test_get_nonexistent_event_returns_none(self, temp_db):
        """Test that getting a nonexistent event returns None"""
        retrieved = get_event("nonexistent_id", temp_db)
        
        assert retrieved is None
    
    def test_stored_event_converts_to_cognitive_event(self, temp_db, sample_event):
        """Test that stored events convert correctly to CognitiveEvent"""
        save_event(sample_event, temp_db)
        
        retrieved = get_event(sample_event.event_id, temp_db)
        
        assert isinstance(retrieved, CognitiveEvent)
        assert retrieved == sample_event


class TestGetEventsForUser:
    """Tests for retrieving events by user"""
    
    def test_get_events_for_user(self, temp_db):
        """Test retrieving all events for a specific user"""
        # Create events for different users
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        event2 = normalize_event({
            "source": "camera_b",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        })
        
        event3 = normalize_event({
            "source": "camera_a",
            "user_id": "u456",
            "timestamp": "2024-07-01T10:02:00Z",
            "cognitive_state": "distracted",
            "confidence": 0.65,
            "reliability": "low"
        })
        
        save_event(event1, temp_db)
        save_event(event2, temp_db)
        save_event(event3, temp_db)
        
        # Get events for u123
        user_events = get_events_for_user("u123", temp_db)
        
        assert len(user_events) == 2
        assert all(e.user_id == "u123" for e in user_events)
    
    def test_events_for_user_in_deterministic_order(self, temp_db):
        """Test that events are returned in deterministic timestamp order"""
        # Create events with different timestamps
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:02:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        event2 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        })
        
        event3 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "distracted",
            "confidence": 0.65,
            "reliability": "low"
        })
        
        save_event(event1, temp_db)
        save_event(event2, temp_db)
        save_event(event3, temp_db)
        
        user_events = get_events_for_user("u123", temp_db)
        
        # Should be ordered by timestamp
        assert user_events[0].timestamp == "2024-07-01T10:00:00.000Z"
        assert user_events[1].timestamp == "2024-07-01T10:01:00.000Z"
        assert user_events[2].timestamp == "2024-07-01T10:02:00.000Z"


class TestGetAllEvents:
    """Tests for retrieving all events"""
    
    def test_get_all_events(self, temp_db):
        """Test retrieving all events"""
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        event2 = normalize_event({
            "source": "camera_b",
            "user_id": "u456",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        })
        
        save_event(event1, temp_db)
        save_event(event2, temp_db)
        
        all_events = get_all_events(temp_db)
        
        assert len(all_events) == 2
    
    def test_all_events_in_deterministic_order(self, temp_db):
        """Test that all events are returned in deterministic order"""
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:02:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        event2 = normalize_event({
            "source": "camera_a",
            "user_id": "u456",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        })
        
        event3 = normalize_event({
            "source": "camera_a",
            "user_id": "u789",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "distracted",
            "confidence": 0.65,
            "reliability": "low"
        })
        
        save_event(event1, temp_db)
        save_event(event2, temp_db)
        save_event(event3, temp_db)
        
        all_events = get_all_events(temp_db)
        
        # Should be ordered by timestamp
        assert all_events[0].timestamp == "2024-07-01T10:00:00.000Z"
        assert all_events[1].timestamp == "2024-07-01T10:01:00.000Z"
        assert all_events[2].timestamp == "2024-07-01T10:02:00.000Z"


class TestDeleteAllEvents:
    """Tests for deleting all events"""
    
    def test_delete_all_events(self, temp_db):
        """Test deleting all events"""
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        event2 = normalize_event({
            "source": "camera_b",
            "user_id": "u456",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        })
        
        save_event(event1, temp_db)
        save_event(event2, temp_db)
        
        deleted_count = delete_all_events(temp_db)
        
        assert deleted_count == 2
        
        # Verify all events are deleted
        all_events = get_all_events(temp_db)
        assert len(all_events) == 0
    
    def test_delete_all_events_returns_correct_count(self, temp_db):
        """Test that delete_all_events returns the correct count"""
        # Delete from empty database
        deleted_count = delete_all_events(temp_db)
        assert deleted_count == 0


class TestUserIsolation:
    """Tests for user data isolation"""
    
    def test_different_users_are_isolated(self, temp_db):
        """Test that events from different users remain isolated"""
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        event2 = normalize_event({
            "source": "camera_a",
            "user_id": "u456",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        })
        
        save_event(event1, temp_db)
        save_event(event2, temp_db)
        
        # Get events for u123
        u123_events = get_events_for_user("u123", temp_db)
        assert len(u123_events) == 1
        assert u123_events[0].user_id == "u123"
        
        # Get events for u456
        u456_events = get_events_for_user("u456", temp_db)
        assert len(u456_events) == 1
        assert u456_events[0].user_id == "u456"


class TestDataIntegrity:
    """Tests for data integrity"""
    
    def test_event_id_is_unique(self, temp_db):
        """Test that event_id is unique (enforced by PRIMARY KEY)"""
        event1 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        # Save the same event again
        event2 = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        save_event(event1, temp_db)
        result = save_event(event2, temp_db)
        
        # Second save should return False (idempotent)
        assert result is False
        
        # Only one event should exist
        all_events = get_all_events(temp_db)
        assert len(all_events) == 1
    
    def test_required_fields_stored_correctly(self, temp_db, sample_event):
        """Test that all required fields are stored correctly"""
        save_event(sample_event, temp_db)
        
        retrieved = get_event(sample_event.event_id, temp_db)
        
        assert retrieved.event_id == sample_event.event_id
        assert retrieved.source == sample_event.source
        assert retrieved.user_id == sample_event.user_id
        assert retrieved.timestamp == sample_event.timestamp
        assert retrieved.cognitive_state == sample_event.cognitive_state
        assert retrieved.confidence == sample_event.confidence
        assert retrieved.reliability == sample_event.reliability
    
    def test_confidence_numerically_accurate(self, temp_db):
        """Test that confidence remains numerically accurate"""
        event = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.123456,
            "reliability": "high"
        })
        
        save_event(event, temp_db)
        
        retrieved = get_event(event.event_id, temp_db)
        
        # Confidence should be rounded to 2 decimal places
        assert retrieved.confidence == 0.12
    
    def test_timestamp_normalized_consistently(self, temp_db):
        """Test that timestamp remains normalized consistently"""
        event = normalize_event({
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        })
        
        save_event(event, temp_db)
        
        retrieved = get_event(event.event_id, temp_db)
        
        # Timestamp should be normalized
        assert retrieved.timestamp == "2024-07-01T10:00:00.000Z"
        assert retrieved.timestamp.endswith("Z")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
