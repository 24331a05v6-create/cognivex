"""
Cognivex - Flask API Tests
Phase 4: Tests for REST API endpoints
"""

import pytest
import tempfile
import os
import sys
import json

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from storage.database import initialize_database, save_event, get_all_events
from reconciliation.models import normalize_event


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Initialize the database
    initialize_database(db_path)
    
    yield db_path
    
    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(temp_db):
    """Create a Flask test client with a temporary database"""
    app = create_app(test_db_path=temp_db)
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_event_data():
    """Sample event data for testing"""
    return {
        "source": "camera_a",
        "user_id": "u123",
        "timestamp": "2024-07-01T10:00:00Z",
        "cognitive_state": "focused",
        "confidence": 0.85,
        "reliability": "high"
    }


class TestHomeEndpoint:
    """Tests for the home/health check endpoint"""
    
    def test_home_endpoint(self, client):
        """Test the home endpoint"""
        response = client.get('/')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Cognivex API is running'
        assert data['status'] == 'healthy'


class TestIngestEndpoint:
    """Tests for POST /ingest endpoint"""
    
    def test_ingest_valid_event(self, client, sample_event_data):
        """Test ingesting a valid event"""
        response = client.post('/ingest', 
                              data=json.dumps(sample_event_data),
                              content_type='application/json')
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['status'] == 'created'
        assert 'event_id' in data
        assert data['event']['source'] == 'camera_a'
        assert data['event']['user_id'] == 'u123'
    
    def test_ingest_duplicate_event(self, client, sample_event_data):
        """Test ingesting a duplicate event"""
        # First ingestion
        response1 = client.post('/ingest',
                               data=json.dumps(sample_event_data),
                               content_type='application/json')
        assert response1.status_code == 201
        
        # Second ingestion (duplicate)
        response2 = client.post('/ingest',
                               data=json.dumps(sample_event_data),
                               content_type='application/json')
        assert response2.status_code == 200
        data = response2.get_json()
        assert data['status'] == 'duplicate'
        assert data['message'] == 'Event already exists'
    
    def test_ingest_missing_json_body(self, client):
        """Test ingesting with missing JSON body"""
        response = client.post('/ingest')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Missing JSON body' in data['error']
    
    def test_ingest_invalid_json(self, client):
        """Test ingesting with invalid JSON"""
        response = client.post('/ingest',
                              data='not valid json',
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
    
    def test_ingest_missing_required_field(self, client):
        """Test ingesting with missing required field"""
        incomplete_data = {
            "source": "camera_a",
            "user_id": "u123"
            # Missing timestamp, cognitive_state, confidence, reliability
        }
        
        response = client.post('/ingest',
                              data=json.dumps(incomplete_data),
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Missing required field' in data['error']
    
    def test_ingest_invalid_source(self, client):
        """Test ingesting with invalid source"""
        invalid_data = {
            "source": "camera_invalid",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        response = client.post('/ingest',
                              data=json.dumps(invalid_data),
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Invalid source' in data['error']
    
    def test_ingest_invalid_confidence(self, client):
        """Test ingesting with invalid confidence"""
        invalid_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 1.5,  # Invalid: > 1.0
            "reliability": "high"
        }
        
        response = client.post('/ingest',
                              data=json.dumps(invalid_data),
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Confidence out of range' in data['error']
    
    def test_ingest_invalid_cognitive_state(self, client):
        """Test ingesting with invalid cognitive state"""
        invalid_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "sleepy",  # Invalid
            "confidence": 0.85,
            "reliability": "high"
        }
        
        response = client.post('/ingest',
                              data=json.dumps(invalid_data),
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Invalid cognitive_state' in data['error']
    
    def test_ingest_invalid_reliability(self, client):
        """Test ingesting with invalid reliability"""
        invalid_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "very_high"  # Invalid
        }
        
        response = client.post('/ingest',
                              data=json.dumps(invalid_data),
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Invalid reliability' in data['error']


class TestGetUserEventsEndpoint:
    """Tests for GET /events/<user_id> endpoint"""
    
    def test_get_user_events(self, client, sample_event_data):
        """Test getting events for a user"""
        # First, ingest an event
        client.post('/ingest',
                   data=json.dumps(sample_event_data),
                   content_type='application/json')
        
        # Now get the events
        response = client.get('/events/u123')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['user_id'] == 'u123'
        assert data['count'] == 1
        assert len(data['events']) == 1
        assert data['events'][0]['source'] == 'camera_a'
    
    def test_get_user_events_empty(self, client):
        """Test getting events for a user with no events"""
        response = client.get('/events/nonexistent_user')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['user_id'] == 'nonexistent_user'
        assert data['count'] == 0
        assert len(data['events']) == 0
    
    def test_get_user_events_multiple(self, client):
        """Test getting multiple events for a user"""
        # Ingest multiple events
        event1 = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event2 = {
            "source": "camera_b",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        }
        
        client.post('/ingest',
                   data=json.dumps(event1),
                   content_type='application/json')
        
        client.post('/ingest',
                   data=json.dumps(event2),
                   content_type='application/json')
        
        # Get events
        response = client.get('/events/u123')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 2
        # Should be ordered by timestamp
        assert data['events'][0]['timestamp'] < data['events'][1]['timestamp']


class TestUserIsolation:
    """Tests for user data isolation"""
    
    def test_different_users_are_isolated(self, client):
        """Test that events from different users are isolated"""
        # Ingest events for different users
        event1 = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event2 = {
            "source": "camera_a",
            "user_id": "u456",
            "timestamp": "2024-07-01T10:01:00Z",
            "cognitive_state": "confused",
            "confidence": 0.75,
            "reliability": "medium"
        }
        
        client.post('/ingest',
                   data=json.dumps(event1),
                   content_type='application/json')
        
        client.post('/ingest',
                   data=json.dumps(event2),
                   content_type='application/json')
        
        # Get events for u123
        response1 = client.get('/events/u123')
        data1 = response1.get_json()
        assert data1['count'] == 1
        assert data1['events'][0]['user_id'] == 'u123'
        
        # Get events for u456
        response2 = client.get('/events/u456')
        data2 = response2.get_json()
        assert data2['count'] == 1
        assert data2['events'][0]['user_id'] == 'u456'


class TestTimelineEndpoint:
    """Tests for GET /timeline/<user_id> endpoint"""
    
    def test_timeline_returns_success(self, client):
        """Test that timeline endpoint returns success"""
        response = client.get('/timeline/u123')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'timeline' in data
    
    def test_timeline_with_events(self, client):
        """Test timeline endpoint with events"""
        # Ingest an event
        event_data = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest',
                   data=json.dumps(event_data),
                   content_type='application/json')
        
        # Get timeline
        response = client.get('/timeline/u123')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert len(data['timeline']) == 1
        assert data['timeline'][0]['cognitive_state'] == 'focused'


class TestAuditEndpoint:
    """Tests for GET /audit/<user_id> endpoint"""

    def test_audit_returns_success(self, client):
        """Test that audit endpoint returns success for known user"""
        event = {
            "source": "camera_a",
            "user_id": "u123",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        client.post('/ingest', data=json.dumps(event), content_type='application/json')

        response = client.get('/audit/u123')

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['user_id'] == 'u123'


class TestReplayEndpoint:
    """Tests for POST /replay endpoint"""

    def test_replay_returns_success(self, client):
        """Test that replay endpoint returns success"""
        response = client.post('/replay')

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'


class TestErrorHandling:
    """Tests for error handling"""
    
    def test_404_error(self, client):
        """Test 404 error handling"""
        response = client.get('/nonexistent_endpoint')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'not found' in data['error'].lower()
    
    def test_405_error(self, client):
        """Test 405 error handling"""
        response = client.put('/ingest')
        
        assert response.status_code == 405
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'not allowed' in data['error'].lower()


class TestDatabaseIntegration:
    """Tests for database integration"""
    
    def test_event_persisted_in_database(self, client, temp_db, sample_event_data):
        """Test that ingested events are persisted in the database"""
        # Ingest an event
        client.post('/ingest',
                   data=json.dumps(sample_event_data),
                   content_type='application/json')
        
        # Check the database directly
        all_events = get_all_events(temp_db)
        assert len(all_events) == 1
        assert all_events[0].source == 'camera_a'
        assert all_events[0].user_id == 'u123'
    
    def test_duplicate_not_stored_in_database(self, client, temp_db, sample_event_data):
        """Test that duplicate events are not stored in the database"""
        # Ingest the same event twice
        client.post('/ingest',
                   data=json.dumps(sample_event_data),
                   content_type='application/json')
        
        client.post('/ingest',
                   data=json.dumps(sample_event_data),
                   content_type='application/json')
        
        # Check the database directly
        all_events = get_all_events(temp_db)
        assert len(all_events) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
