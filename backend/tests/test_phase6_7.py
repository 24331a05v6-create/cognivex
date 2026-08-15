"""
Cognivex - Phase 6+7 Tests
Comprehensive tests for audit, replay, idempotency, late events, and edge cases
"""

import pytest
import tempfile
import os
import sys
import json

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from reconciliation.models import normalize_event, CognitiveEvent
from reconciliation.engine import reconcile, reconcile_for_user
from storage.database import initialize_database, save_event, get_events_for_user, get_all_events


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    initialize_database(db_path)
    
    yield db_path
    
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def client(temp_db):
    """Create a Flask test client with a temporary database"""
    app = create_app(test_db_path=temp_db)
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client


class TestAuditGeneration:
    """Tests for audit trail generation"""
    
    def test_audit_exists_for_conflict_resolution(self, client):
        """Test that audit records are generated for conflict resolution"""
        # Ingest two conflicting events
        event1 = {
            "source": "camera_a",
            "user_id": "u_audit_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event2 = {
            "source": "camera_b",
            "user_id": "u_audit_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.70,
            "reliability": "medium"
        }
        
        client.post('/ingest', data=json.dumps(event1), content_type='application/json')
        client.post('/ingest', data=json.dumps(event2), content_type='application/json')
        
        # Get audit
        response = client.get('/audit/u_audit_1')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert data['audit_count'] > 0
        
        # Check that conflict resolution audit exists
        decisions = [r['decision'] for r in data['audit_records']]
        assert 'conflict_resolved' in decisions
    
    def test_audit_exists_for_conflict_resolution(self, client):
        """Test that audit records are generated for conflict resolution"""
        # Ingest two conflicting events at the same timestamp
        event_camera = {
            "source": "camera_a",
            "user_id": "u_audit_2",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        event_ui = {
            "source": "ui_log",
            "user_id": "u_audit_2",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.60,
            "reliability": "medium"
        }

        client.post('/ingest', data=json.dumps(event_camera), content_type='application/json')
        client.post('/ingest', data=json.dumps(event_ui), content_type='application/json')
        
        # Get audit
        response = client.get('/audit/u_audit_2')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['audit_count'] > 0
        
        # Check that conflict_resolved audit exists
        decisions = [r['decision'] for r in data['audit_records']]
        assert 'conflict_resolved' in decisions
    
    def test_audit_exists_for_rejected_dependency(self, client):
        """Test that audit records are generated for rejected dependency"""
        # Ingest confused without prior focused
        event = {
            "source": "camera_a",
            "user_id": "u_audit_3",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Get audit
        response = client.get('/audit/u_audit_3')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['audit_count'] > 0
        
        # Check that rejected audit exists
        decisions = [r['decision'] for r in data['audit_records']]
        assert 'rejected' in decisions
    
    def test_audit_contains_understandable_reasons(self, client):
        """Test that audit records contain human-readable reasons"""
        event = {
            "source": "camera_a",
            "user_id": "u_audit_4",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Get audit
        response = client.get('/audit/u_audit_4')
        data = response.get_json()
        
        assert response.status_code == 200
        
        # Check that reasons are present and non-empty
        for record in data['audit_records']:
            assert 'reason' in record
            assert len(record['reason']) > 0


class TestTimelineAPI:
    """Tests for timeline API endpoint"""
    
    def test_correct_timeline_returned(self, client):
        """Test that correct timeline is returned"""
        # Ingest events
        events = [
            {
                "source": "camera_a",
                "user_id": "u_timeline_1",
                "timestamp": "2024-07-01T10:00:00Z",
                "cognitive_state": "focused",
                "confidence": 0.85,
                "reliability": "high"
            },
            {
                "source": "camera_b",
                "user_id": "u_timeline_1",
                "timestamp": "2024-07-01T10:05:00Z",
                "cognitive_state": "confused",
                "confidence": 0.70,
                "reliability": "medium"
            }
        ]
        
        for event in events:
            client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Get timeline
        response = client.get('/timeline/u_timeline_1')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert len(data['timeline']) == 2
        assert data['timeline'][0]['cognitive_state'] == 'focused'
        assert data['timeline'][1]['cognitive_state'] == 'confused'
    
    def test_correct_user_isolation(self, client):
        """Test that user isolation is maintained in timeline"""
        # Ingest events for different users
        event1 = {
            "source": "camera_a",
            "user_id": "u_timeline_2a",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event2 = {
            "source": "camera_a",
            "user_id": "u_timeline_2b",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.80,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event1), content_type='application/json')
        client.post('/ingest', data=json.dumps(event2), content_type='application/json')
        
        # Get timelines
        response1 = client.get('/timeline/u_timeline_2a')
        response2 = client.get('/timeline/u_timeline_2b')
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        # u_timeline_2a should have focused
        assert data1['timeline'][0]['cognitive_state'] == 'focused'
        
        # u_timeline_2b should have rejected confused (no prior focused)
        assert len(data2['timeline']) == 0
    
    def test_timeline_is_deterministic(self, client):
        """Test that timeline is deterministic"""
        # Ingest events
        event = {
            "source": "camera_a",
            "user_id": "u_timeline_3",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Get timeline twice
        response1 = client.get('/timeline/u_timeline_3')
        response2 = client.get('/timeline/u_timeline_3')
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        assert data1['timeline'] == data2['timeline']


class TestAuditAPI:
    """Tests for audit API endpoint"""
    
    def test_correct_audit_returned(self, client):
        """Test that correct audit is returned"""
        # Ingest two conflicting events to produce an audit record
        event_camera = {
            "source": "camera_a",
            "user_id": "u_audit_api_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        event_ui = {
            "source": "ui_log",
            "user_id": "u_audit_api_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.60,
            "reliability": "medium"
        }

        client.post('/ingest', data=json.dumps(event_camera), content_type='application/json')
        client.post('/ingest', data=json.dumps(event_ui), content_type='application/json')
        
        # Get audit
        response = client.get('/audit/u_audit_api_1')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert data['audit_count'] > 0
        assert len(data['audit_records']) > 0
    
    def test_audit_is_deterministic(self, client):
        """Test that audit is deterministic"""
        # Ingest an event
        event = {
            "source": "camera_a",
            "user_id": "u_audit_api_2",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Get audit twice
        response1 = client.get('/audit/u_audit_api_2')
        response2 = client.get('/audit/u_audit_api_2')
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        assert data1['audit_records'] == data2['audit_records']


class TestReplay:
    """Tests for replay functionality"""
    
    def test_replay_endpoint_works(self, client):
        """Test that replay endpoint works"""
        # Ingest an event
        event = {
            "source": "camera_a",
            "user_id": "u_replay_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Replay
        response = client.post('/replay')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['status'] == 'success'
        assert data['deterministic'] == True
    
    def test_replay_produces_timeline(self, client):
        """Test that replay produces a timeline"""
        # Ingest an event
        event = {
            "source": "camera_a",
            "user_id": "u_replay_2",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Replay
        response = client.post('/replay')
        data = response.get_json()
        
        assert 'results' in data
        assert 'u_replay_2' in data['results']
        assert len(data['results']['u_replay_2']['timeline']) == 1
    
    def test_replay_produces_audit(self, client):
        """Test that replay produces an audit when conflicts exist"""
        # Ingest two conflicting events to produce audit records
        event_camera = {
            "source": "camera_a",
            "user_id": "u_replay_3",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        event_ui = {
            "source": "ui_log",
            "user_id": "u_replay_3",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.60,
            "reliability": "medium"
        }

        client.post('/ingest', data=json.dumps(event_camera), content_type='application/json')
        client.post('/ingest', data=json.dumps(event_ui), content_type='application/json')
        
        # Replay
        response = client.post('/replay')
        data = response.get_json()
        
        assert 'results' in data
        assert 'u_replay_3' in data['results']
        assert len(data['results']['u_replay_3']['audit']) > 0
    
    def test_replay_does_not_duplicate_stored_events(self, client, temp_db):
        """Test that replay does not duplicate stored events"""
        # Ingest an event
        event = {
            "source": "camera_a",
            "user_id": "u_replay_4",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Count events before replay
        events_before = get_all_events(temp_db)
        count_before = len(events_before)
        
        # Replay
        client.post('/replay')
        
        # Count events after replay
        events_after = get_all_events(temp_db)
        count_after = len(events_after)
        
        assert count_before == count_after


class TestReplayDeterminism:
    """Tests for replay determinism"""
    
    def test_replay_determinism(self, client):
        """Test that replay produces identical results when run twice"""
        # Ingest events
        events = [
            {
                "source": "camera_a",
                "user_id": "u_replay_det",
                "timestamp": "2024-07-01T10:00:00Z",
                "cognitive_state": "focused",
                "confidence": 0.85,
                "reliability": "high"
            },
            {
                "source": "camera_b",
                "user_id": "u_replay_det",
                "timestamp": "2024-07-01T10:05:00Z",
                "cognitive_state": "confused",
                "confidence": 0.70,
                "reliability": "medium"
            }
        ]
        
        for event in events:
            client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Replay twice
        response1 = client.post('/replay')
        response2 = client.post('/replay')
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        # Compare results
        assert data1['results']['u_replay_det']['timeline'] == data2['results']['u_replay_det']['timeline']
        assert data1['results']['u_replay_det']['audit'] == data2['results']['u_replay_det']['audit']


class TestIdempotency:
    """Tests for idempotent ingestion"""
    
    def test_idempotent_ingestion(self, client, temp_db):
        """Test that submitting the same event multiple times does not create duplicates"""
        event = {
            "source": "camera_a",
            "user_id": "u_idempotent",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        # Submit the same event 3 times
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Verify only one event exists
        events = get_events_for_user('u_idempotent', temp_db)
        assert len(events) == 1


class TestLateEvents:
    """Tests for late/out-of-order event handling"""
    
    def test_late_event_reconstruction(self, client):
        """Test that late events are properly integrated into timeline"""
        # First ingest events in chronological order
        event1 = {
            "source": "camera_a",
            "user_id": "u_late_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.90,
            "reliability": "high"
        }
        
        event2 = {
            "source": "camera_a",
            "user_id": "u_late_1",
            "timestamp": "2024-07-01T10:05:00Z",
            "cognitive_state": "distracted",
            "confidence": 0.75,
            "reliability": "medium"
        }
        
        client.post('/ingest', data=json.dumps(event1), content_type='application/json')
        client.post('/ingest', data=json.dumps(event2), content_type='application/json')
        
        # Get initial timeline
        response1 = client.get('/timeline/u_late_1')
        data1 = response1.get_json()
        
        assert len(data1['timeline']) == 2
        assert data1['timeline'][0]['timestamp'] == '2024-07-01T10:00:00.000Z'
        assert data1['timeline'][1]['timestamp'] == '2024-07-01T10:05:00.000Z'
        
        # Now ingest a late event
        late_event = {
            "source": "ui_log",
            "user_id": "u_late_1",
            "timestamp": "2024-07-01T10:02:00Z",
            "cognitive_state": "confused",
            "confidence": 0.65,
            "reliability": "low"
        }
        
        client.post('/ingest', data=json.dumps(late_event), content_type='application/json')
        
        # Get updated timeline
        response2 = client.get('/timeline/u_late_1')
        data2 = response2.get_json()
        
        # Timeline should be reconstructed with late event in correct position
        assert len(data2['timeline']) == 3
        assert data2['timeline'][0]['timestamp'] == '2024-07-01T10:00:00.000Z'
        assert data2['timeline'][1]['timestamp'] == '2024-07-01T10:02:00.000Z'
        assert data2['timeline'][2]['timestamp'] == '2024-07-01T10:05:00.000Z'


class TestOutOfOrderIngestion:
    """Tests for out-of-order event ingestion"""
    
    def test_out_of_order_produces_same_result(self, client):
        """Test that different arrival orders produce same final timeline"""
        # Create two temporary databases for comparison
        fd1, db1_path = tempfile.mkstemp(suffix='.db')
        fd2, db2_path = tempfile.mkstemp(suffix='.db')
        os.close(fd1)
        os.close(fd2)
        
        try:
            initialize_database(db1_path)
            initialize_database(db2_path)
            
            # Create test clients
            app1 = create_app(test_db_path=db1_path)
            app2 = create_app(test_db_path=db2_path)
            app1.config['TESTING'] = True
            app2.config['TESTING'] = True
            
            # Events in order A
            events_a = [
                {
                    "source": "camera_a",
                    "user_id": "u_ooodr",
                    "timestamp": "2024-07-01T10:00:00Z",
                    "cognitive_state": "focused",
                    "confidence": 0.85,
                    "reliability": "high"
                },
                {
                    "source": "camera_b",
                    "user_id": "u_ooodr",
                    "timestamp": "2024-07-01T10:02:00Z",
                    "cognitive_state": "confused",
                    "confidence": 0.70,
                    "reliability": "medium"
                },
                {
                    "source": "camera_a",
                    "user_id": "u_ooodr",
                    "timestamp": "2024-07-01T10:05:00Z",
                    "cognitive_state": "distracted",
                    "confidence": 0.65,
                    "reliability": "low"
                }
            ]
            
            # Events in order B (out of order)
            events_b = [
                events_a[2],  # 10:05
                events_a[0],  # 10:00
                events_a[1],  # 10:02
            ]
            
            # Ingest events in order A to db1
            with app1.test_client() as client1:
                for event in events_a:
                    client1.post('/ingest', data=json.dumps(event), content_type='application/json')
            
            # Ingest events in order B to db2
            with app2.test_client() as client2:
                for event in events_b:
                    client2.post('/ingest', data=json.dumps(event), content_type='application/json')
            
            # Get timelines from both
            with app1.test_client() as client1:
                response1 = client1.get('/timeline/u_ooodr')
                timeline1 = response1.get_json()['timeline']
            
            with app2.test_client() as client2:
                response2 = client2.get('/timeline/u_ooodr')
                timeline2 = response2.get_json()['timeline']
            
            # Timelines should be identical
            assert timeline1 == timeline2
            
        finally:
            if os.path.exists(db1_path):
                os.unlink(db1_path)
            if os.path.exists(db2_path):
                os.unlink(db2_path)


class TestEdgeCases:
    """Tests for the five required edge cases"""
    
    def test_case1_exact_duplicate(self, client, temp_db):
        """Test CASE 1: Exact duplicate from same source at same timestamp"""
        event = {
            "source": "camera_a",
            "user_id": "user_edge_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.90,
            "reliability": "high"
        }
        
        # Ingest twice
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        client.post('/ingest', data=json.dumps(event), content_type='application/json')
        
        # Verify only one event stored
        events = get_events_for_user('user_edge_1', temp_db)
        assert len(events) == 1
    
    def test_case2_same_source_duplicate(self, client):
        """Test CASE 2: Same source duplicate at different timestamp"""
        # Ingest old observation
        event_old = {
            "source": "camera_b",
            "user_id": "user_edge_2",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.75,
            "reliability": "medium"
        }
        
        client.post('/ingest', data=json.dumps(event_old), content_type='application/json')
        
        # Ingest newer observation from same source
        event_new = {
            "source": "camera_b",
            "user_id": "user_edge_2",
            "timestamp": "2024-07-01T10:05:00Z",
            "cognitive_state": "focused",
            "confidence": 0.80,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event_new), content_type='application/json')
        
        # Get timeline - should only have the newer observation
        response = client.get('/timeline/user_edge_2')
        data = response.get_json()
        
        assert len(data['timeline']) == 1
        assert data['timeline'][0]['confidence'] == 0.80
    
    def test_case3_camera_vs_ui_conflict(self, client):
        """Test CASE 3: Camera A vs UI Log conflict at same timestamp"""
        # Ingest conflicting events
        event_camera = {
            "source": "camera_a",
            "user_id": "user_edge_3",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        event_ui = {
            "source": "ui_log",
            "user_id": "user_edge_3",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.60,
            "reliability": "medium"
        }
        
        client.post('/ingest', data=json.dumps(event_camera), content_type='application/json')
        client.post('/ingest', data=json.dumps(event_ui), content_type='application/json')
        
        # Get timeline - camera should win with higher score
        response = client.get('/timeline/user_edge_3')
        data = response.get_json()
        
        assert len(data['timeline']) == 1
        assert data['timeline'][0]['cognitive_state'] == 'focused'
        assert data['timeline'][0]['source'] == 'camera_a'
    
    def test_case4_late_event(self, client):
        """Test CASE 4: Late/out-of-order event arriving after earlier reconciliation"""
        # Ingest first two events
        event1 = {
            "source": "camera_a",
            "user_id": "user_edge_4",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.90,
            "reliability": "high"
        }
        
        event2 = {
            "source": "camera_a",
            "user_id": "user_edge_4",
            "timestamp": "2024-07-01T10:05:00Z",
            "cognitive_state": "distracted",
            "confidence": 0.75,
            "reliability": "medium"
        }
        
        client.post('/ingest', data=json.dumps(event1), content_type='application/json')
        client.post('/ingest', data=json.dumps(event2), content_type='application/json')
        
        # Ingest late event
        late_event = {
            "source": "ui_log",
            "user_id": "user_edge_4",
            "timestamp": "2024-07-01T10:02:00Z",
            "cognitive_state": "confused",
            "confidence": 0.65,
            "reliability": "low"
        }
        
        client.post('/ingest', data=json.dumps(late_event), content_type='application/json')
        
        # Get timeline - should have all three events in correct order
        response = client.get('/timeline/user_edge_4')
        data = response.get_json()
        
        assert len(data['timeline']) == 3
        assert data['timeline'][0]['timestamp'] == '2024-07-01T10:00:00.000Z'
        assert data['timeline'][1]['timestamp'] == '2024-07-01T10:02:00.000Z'
        assert data['timeline'][2]['timestamp'] == '2024-07-01T10:05:00.000Z'
    
    def test_case5_invalid_dependency(self, client):
        """Test CASE 5: Invalid dependency - confused before any valid focused state"""
        # Ingest confused without prior focused
        event_confused = {
            "source": "camera_a",
            "user_id": "user_edge_5",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.80,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event_confused), content_type='application/json')
        
        # Get timeline - should be empty (confused rejected)
        response = client.get('/timeline/user_edge_5')
        data = response.get_json()
        
        assert len(data['timeline']) == 0
        
        # Get audit - should show rejected decision
        response_audit = client.get('/audit/user_edge_5')
        data_audit = response_audit.get_json()
        
        decisions = [r['decision'] for r in data_audit['audit_records']]
        assert 'rejected' in decisions


class TestMultipleUsers:
    """Tests for multiple user isolation"""
    
    def test_events_do_not_leak_between_users(self, client):
        """Test that events and state do not leak between users"""
        # User 1: focused first
        event1 = {
            "source": "camera_a",
            "user_id": "user_multi_1",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "focused",
            "confidence": 0.85,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event1), content_type='application/json')
        
        # User 2: confused first (should be rejected)
        event2 = {
            "source": "camera_a",
            "user_id": "user_multi_2",
            "timestamp": "2024-07-01T10:00:00Z",
            "cognitive_state": "confused",
            "confidence": 0.80,
            "reliability": "high"
        }
        
        client.post('/ingest', data=json.dumps(event2), content_type='application/json')
        
        # User 1: confused second (should be accepted)
        event3 = {
            "source": "camera_b",
            "user_id": "user_multi_1",
            "timestamp": "2024-07-01T10:05:00Z",
            "cognitive_state": "confused",
            "confidence": 0.70,
            "reliability": "medium"
        }
        
        client.post('/ingest', data=json.dumps(event3), content_type='application/json')
        
        # Get timelines
        response1 = client.get('/timeline/user_multi_1')
        response2 = client.get('/timeline/user_multi_2')
        
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        # User 1 should have both events
        assert len(data1['timeline']) == 2
        
        # User 2 should have no events (confused rejected)
        assert len(data2['timeline']) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
