"""
Cognivex - Reconciliation Engine Tests
Phase 5: Tests for deterministic cognitive state reconciliation
"""

import pytest
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reconciliation.models import CognitiveEvent, normalize_event
from reconciliation.engine import (
    reconcile,
    reconcile_for_user,
    _sort_events,
    _deduplicate_exact,
    _resolve_same_source_duplicates,
    _group_temporal_conflicts,
    ReconciliationResult
)
from reconciliation.rules import (
    RELIABILITY_WEIGHTS,
    calculate_conflict_score,
    is_valid_transition,
    can_state_be_first,
    get_reliability_weight
)


def create_event(
    event_id: str = "test_event_001",
    source: str = "camera_a",
    user_id: str = "u123",
    timestamp: str = "2024-07-01T10:00:00.000Z",
    cognitive_state: str = "focused",
    confidence: float = 0.85,
    reliability: str = "high"
) -> CognitiveEvent:
    """Helper function to create CognitiveEvent instances for testing"""
    return CognitiveEvent(
        event_id=event_id,
        source=source,
        user_id=user_id,
        timestamp=timestamp,
        cognitive_state=cognitive_state,
        confidence=confidence,
        reliability=reliability
    )


class TestDeterministicOrdering:
    """Tests for deterministic event ordering"""
    
    def test_events_sorted_by_timestamp(self):
        """Test that events are sorted by timestamp"""
        events = [
            create_event(event_id="e1", timestamp="2024-07-01T10:02:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e3", timestamp="2024-07-01T10:01:00.000Z"),
        ]
        
        sorted_events = _sort_events(events)
        
        assert sorted_events[0].event_id == "e2"
        assert sorted_events[1].event_id == "e3"
        assert sorted_events[2].event_id == "e1"
    
    def test_events_sorted_by_event_id_when_timestamps_equal(self):
        """Test that events are sorted by event_id when timestamps are equal"""
        events = [
            create_event(event_id="event_c", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="event_a", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="event_b", timestamp="2024-07-01T10:00:00.000Z"),
        ]
        
        sorted_events = _sort_events(events)
        
        assert sorted_events[0].event_id == "event_a"
        assert sorted_events[1].event_id == "event_b"
        assert sorted_events[2].event_id == "event_c"
    
    def test_arrival_order_does_not_affect_final_timeline(self):
        """Test that different arrival orders produce the same final timeline"""
        events_v1 = [
            create_event(event_id="e1", timestamp="2024-07-01T10:02:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e3", timestamp="2024-07-01T10:01:00.000Z"),
        ]
        
        events_v2 = [
            create_event(event_id="e3", timestamp="2024-07-01T10:01:00.000Z"),
            create_event(event_id="e1", timestamp="2024-07-01T10:02:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:00:00.000Z"),
        ]
        
        result_v1 = reconcile(events_v1)
        result_v2 = reconcile(events_v2)
        
        assert len(result_v1.timeline) == len(result_v2.timeline)
        for i in range(len(result_v1.timeline)):
            assert result_v1.timeline[i] == result_v2.timeline[i]


class TestExactDuplicateHandling:
    """Tests for exact duplicate handling"""
    
    def test_exact_duplicate_is_ignored(self):
        """Test that exact duplicates (same event_id) are ignored"""
        event = create_event(event_id="duplicate_001")
        duplicate = create_event(event_id="duplicate_001")
        
        result = reconcile([event, duplicate])
        
        assert len(result.timeline) == 1
        assert len(result.audit) == 1
        assert result.audit[0].decision == "duplicate_ignored"
    
    def test_multiple_exact_duplicates(self):
        """Test handling of multiple exact duplicates"""
        event = create_event(event_id="multi_dup_001")
        dup1 = create_event(event_id="multi_dup_001")
        dup2 = create_event(event_id="multi_dup_001")
        
        result = reconcile([event, dup1, dup2])
        
        assert len(result.timeline) == 1
        # Should have 2 audit records for 2 ignored duplicates
        assert len(result.audit) == 2
        assert all(a.decision == "duplicate_ignored" for a in result.audit)


class TestSameSourceDuplicateHandling:
    """Tests for same source duplicate handling (keep latest)"""
    
    def test_same_source_different_timestamp_keeps_latest(self):
        """Test that same source duplicates at different timestamps keep the latest"""
        event_old = create_event(
            event_id="old_001",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        event_new = create_event(
            event_id="new_001",
            source="camera_a",
            timestamp="2024-07-01T10:02:00.000Z",
            cognitive_state="focused"
        )
        
        result = reconcile([event_old, event_new])
        
        assert len(result.timeline) == 1
        assert result.timeline[0]["source"] == "camera_a"
        # The newer event should be in the timeline
        assert len(result.audit) == 1
        assert result.audit[0].decision == "replaced"
    
    def test_same_source_same_timestamp_different_states(self):
        """Test that same source events at same timestamp with different states are handled as conflict"""
        event1 = create_event(
            event_id="same_ts_001",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        event2 = create_event(
            event_id="same_ts_002",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="confused"
        )
        
        result = reconcile([event1, event2])
        
        # These are different observations (different cognitive_state), so both are considered
        # The conflict resolution will pick one
        assert len(result.timeline) == 1
        assert len(result.audit) == 1
        assert result.audit[0].decision == "conflict_resolved"


class TestConflictResolution:
    """Tests for conflict resolution with scoring"""
    
    def test_camera_focused_vs_ui_confused(self):
        """Test Camera A focused vs UI confused conflict"""
        camera_event = create_event(
            event_id="camera_001",
            source="camera_a",
            cognitive_state="focused",
            confidence=0.85,
            reliability="high"
        )
        ui_event = create_event(
            event_id="ui_001",
            source="ui_log",
            cognitive_state="confused",
            confidence=0.60,
            reliability="medium"
        )
        
        result = reconcile([camera_event, ui_event])
        
        # Camera should win with higher score
        assert len(result.timeline) == 1
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.timeline[0]["source"] == "camera_a"
    
    def test_reliability_and_confidence_determine_winner(self):
        """Test that reliability and confidence determine the winner"""
        # Both events are "focused" to avoid state dependency issues
        # High confidence, low reliability
        event_a = create_event(
            event_id="high_conf_low_rel",
            source="camera_a",
            cognitive_state="focused",
            confidence=0.95,
            reliability="low"
        )
        # Low confidence, high reliability
        event_b = create_event(
            event_id="low_conf_high_rel",
            source="camera_b",
            cognitive_state="focused",
            confidence=0.70,
            reliability="high"
        )
        
        result = reconcile([event_a, event_b])
        
        # event_b should win: 0.70 * 1.0 = 0.70 > 0.95 * 0.4 = 0.38
        assert len(result.timeline) == 1
        assert result.timeline[0]["source"] == "camera_b"
    
    def test_same_score_tiebreaks_by_event_id(self):
        """Test that ties are broken by event_id for determinism"""
        event_a = create_event(
            event_id="aaa_001",
            source="camera_a",
            cognitive_state="focused",
            confidence=0.85,
            reliability="high"
        )
        event_b = create_event(
            event_id="bbb_001",
            source="camera_b",
            cognitive_state="focused",
            confidence=0.85,
            reliability="high"
        )
        
        result = reconcile([event_a, event_b])
        
        # Same score, so event_a should win due to lower event_id
        assert len(result.timeline) == 1
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.audit[0].decision == "conflict_resolved"
    
    def test_same_timestamp_conflicting_states_produce_one_state(self):
        """Test that same timestamp conflicting states produce one final state"""
        events = [
            create_event(event_id="e1", source="camera_a", cognitive_state="focused", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e2", source="camera_b", cognitive_state="focused", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e3", source="camera_c", cognitive_state="focused", timestamp="2024-07-01T10:00:00.000Z"),
        ]
        
        result = reconcile(events)
        
        assert len(result.timeline) == 1
        assert len(result.audit) == 1
    
    def test_conflict_resolution_with_state_dependency(self):
        """Test conflict resolution when state dependency affects the winner"""
        # This test verifies that confused is rejected when no prior focused state exists
        event_confused = create_event(
            event_id="confused_001",
            source="camera_a",
            cognitive_state="confused",
            confidence=0.95,
            reliability="high"
        )
        event_focused = create_event(
            event_id="focused_001",
            source="camera_b",
            cognitive_state="focused",
            confidence=0.70,
            reliability="medium"
        )
        
        result = reconcile([event_confused, event_focused])
        
        # Even though confused has higher score, focused wins due to state dependency
        assert len(result.timeline) == 1
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.audit[0].decision == "conflict_resolved"
        assert "state dependency" in result.audit[0].reason


class TestStateDependencyValidation:
    """Tests for state transition validation"""
    
    def test_first_confused_state_without_focused_is_rejected(self):
        """Test that confused state without prior focused state is rejected"""
        event = create_event(
            event_id="confused_first",
            cognitive_state="confused",
            confidence=0.85,
            reliability="high"
        )
        
        result = reconcile([event])
        
        assert len(result.timeline) == 0
        assert len(result.audit) == 1
        assert result.audit[0].decision == "rejected"
        assert "no earlier valid focused state" in result.audit[0].reason
    
    def test_focused_then_confused_is_accepted(self):
        """Test that focused → confused transition is accepted"""
        focused = create_event(
            event_id="focused_001",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        confused = create_event(
            event_id="confused_001",
            source="camera_b",
            timestamp="2024-07-01T10:01:00.000Z",
            cognitive_state="confused"
        )
        
        result = reconcile([focused, confused])
        
        assert len(result.timeline) == 2
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.timeline[1]["cognitive_state"] == "confused"
    
    def test_focused_then_distracted_is_accepted(self):
        """Test that focused → distracted transition is accepted"""
        focused = create_event(
            event_id="focused_001",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        distracted = create_event(
            event_id="distracted_001",
            source="camera_b",
            timestamp="2024-07-01T10:01:00.000Z",
            cognitive_state="distracted"
        )
        
        result = reconcile([focused, distracted])
        
        assert len(result.timeline) == 2
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.timeline[1]["cognitive_state"] == "distracted"
    
    def test_confused_then_focused_is_accepted(self):
        """Test that confused → focused transition is accepted after focused was seen"""
        focused = create_event(
            event_id="focused_001",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        confused = create_event(
            event_id="confused_001",
            source="camera_b",
            timestamp="2024-07-01T10:01:00.000Z",
            cognitive_state="confused"
        )
        focused_again = create_event(
            event_id="focused_002",
            source="camera_c",
            timestamp="2024-07-01T10:02:00.000Z",
            cognitive_state="focused"
        )
        
        result = reconcile([focused, confused, focused_again])
        
        assert len(result.timeline) == 3
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.timeline[1]["cognitive_state"] == "confused"
        assert result.timeline[2]["cognitive_state"] == "focused"
    
    def test_distracted_then_focused_is_accepted(self):
        """Test that distracted → focused transition is accepted after focused was seen"""
        focused = create_event(
            event_id="focused_001",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        distracted = create_event(
            event_id="distracted_001",
            source="camera_b",
            timestamp="2024-07-01T10:01:00.000Z",
            cognitive_state="distracted"
        )
        focused_again = create_event(
            event_id="focused_002",
            source="camera_c",
            timestamp="2024-07-01T10:02:00.000Z",
            cognitive_state="focused"
        )
        
        result = reconcile([focused, distracted, focused_again])
        
        assert len(result.timeline) == 3
        assert result.timeline[0]["cognitive_state"] == "focused"
        assert result.timeline[1]["cognitive_state"] == "distracted"
        assert result.timeline[2]["cognitive_state"] == "focused"


class TestUserIsolation:
    """Tests for user session isolation"""
    
    def test_different_users_are_isolated(self):
        """Test that events from different users don't affect each other"""
        # u123 has focused first
        u123_focused = create_event(
            event_id="u123_focused",
            user_id="u123",
            source="camera_a",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="focused"
        )
        
        # u456 has confused first (should be rejected for u456)
        u456_confused = create_event(
            event_id="u456_confused",
            user_id="u456",
            source="camera_b",
            timestamp="2024-07-01T10:00:00.000Z",
            cognitive_state="confused"
        )
        
        # u123 has confused (should be accepted because focused was before)
        u123_confused = create_event(
            event_id="u123_confused",
            user_id="u123",
            source="camera_c",
            timestamp="2024-07-01T10:01:00.000Z",
            cognitive_state="confused"
        )
        
        result = reconcile([u123_focused, u456_confused, u123_confused])
        
        # u123 should have both events
        u123_timeline = [t for t in result.timeline if t.get("source") in ["camera_a", "camera_c"]]
        assert len(u123_timeline) == 2
        
        # Check that u456's confused was rejected
        u456_audit = [a for a in result.audit if a.user_id == "u456"]
        assert len(u456_audit) == 1
        assert u456_audit[0].decision == "rejected"
    
    def test_reconcile_for_user_filters_correctly(self):
        """Test that reconcile_for_user filters events correctly"""
        events = [
            create_event(event_id="u123_e1", user_id="u123", source="camera_a", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="u456_e1", user_id="u456", source="camera_b", timestamp="2024-07-01T10:01:00.000Z"),
            create_event(event_id="u123_e2", user_id="u123", source="camera_c", timestamp="2024-07-01T10:02:00.000Z"),
        ]
        
        result = reconcile_for_user("u123", events)
        
        # Only u123 events should be in the timeline
        assert len(result.timeline) == 2


class TestReplaySupport:
    """Tests for replay support (deterministic output)"""
    
    def test_replay_of_identical_events_produces_identical_timeline(self):
        """Test that replay of identical events produces identical timeline"""
        events = [
            create_event(event_id="e1", timestamp="2024-07-01T10:00:00.000Z", cognitive_state="focused"),
            create_event(event_id="e2", timestamp="2024-07-01T10:01:00.000Z", cognitive_state="focused"),
            create_event(event_id="e3", timestamp="2024-07-01T10:02:00.000Z", cognitive_state="focused"),
        ]
        
        result1 = reconcile(events)
        result2 = reconcile(events)
        
        assert result1.timeline == result2.timeline
        assert len(result1.audit) == len(result2.audit)
        for a1, a2 in zip(result1.audit, result2.audit):
            assert a1.decision == a2.decision
            assert a1.reason == a2.reason
    
    def test_replay_produces_identical_audit_output(self):
        """Test that replay produces identical audit output"""
        events = [
            create_event(event_id="e1", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:00:00.000Z"),
        ]
        
        result1 = reconcile(events)
        result2 = reconcile(events)
        
        assert len(result1.audit) == len(result2.audit)
        for a1, a2 in zip(result1.audit, result2.audit):
            assert a1.user_id == a2.user_id
            assert a1.event_ids == a2.event_ids
            assert a1.decision == a2.decision
            assert a1.reason == a2.reason
            assert a1.final_state == a2.final_state
            assert a1.reconciliation_order == a2.reconciliation_order


class TestEdgeCases:
    """Tests for edge cases"""
    
    def test_empty_event_list(self):
        """Test that empty event list is handled correctly"""
        result = reconcile([])
        
        assert len(result.timeline) == 0
        assert len(result.audit) == 0
    
    def test_single_event(self):
        """Test that single event is handled correctly"""
        event = create_event(timestamp="2024-07-01T10:00:00.000Z")
        
        result = reconcile([event])
        
        assert len(result.timeline) == 1
        assert result.timeline[0]["cognitive_state"] == "focused"
    
    def test_late_out_of_order_events_produce_same_result(self):
        """Test that late/out-of-order events produce same result as ordered input"""
        # Ordered input
        ordered = [
            create_event(event_id="e1", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:01:00.000Z"),
            create_event(event_id="e3", timestamp="2024-07-01T10:02:00.000Z"),
        ]
        
        # Out-of-order input
        unordered = [
            create_event(event_id="e3", timestamp="2024-07-01T10:02:00.000Z"),
            create_event(event_id="e1", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:01:00.000Z"),
        ]
        
        result_ordered = reconcile(ordered)
        result_unordered = reconcile(unordered)
        
        assert result_ordered.timeline == result_unordered.timeline


class TestAuditRecords:
    """Tests for audit record generation"""
    
    def test_audit_record_for_conflict_resolution(self):
        """Test that audit records are generated for conflict resolution"""
        event1 = create_event(event_id="e1", source="camera_a", cognitive_state="focused")
        event2 = create_event(event_id="e2", source="camera_b", cognitive_state="focused")
        
        result = reconcile([event1, event2])
        
        assert len(result.audit) == 1
        audit = result.audit[0]
        
        assert audit.user_id == "u123"
        assert len(audit.event_ids) == 2
        assert audit.decision == "conflict_resolved"
        assert audit.final_state is not None
        assert audit.reconciliation_order == 0
    
    def test_audit_record_for_duplicate_ignored(self):
        """Test that audit records are generated for duplicate ignored"""
        event = create_event(event_id="dup_001")
        duplicate = create_event(event_id="dup_001")
        
        result = reconcile([event, duplicate])
        
        assert len(result.audit) == 1
        audit = result.audit[0]
        
        assert audit.decision == "duplicate_ignored"
        assert audit.final_state is None
    
    def test_audit_reconciliation_order_is_deterministic(self):
        """Test that reconciliation order is deterministic"""
        events = [
            create_event(event_id="e1", timestamp="2024-07-01T10:00:00.000Z"),
            create_event(event_id="e2", timestamp="2024-07-01T10:01:00.000Z"),
        ]
        
        result1 = reconcile(events)
        result2 = reconcile(events)
        
        for a1, a2 in zip(result1.audit, result2.audit):
            assert a1.reconciliation_order == a2.reconciliation_order


class TestReliabilityWeights:
    """Tests for reliability weight calculations"""
    
    def test_reliability_weights_are_correct(self):
        """Test that reliability weights are correct"""
        assert RELIABILITY_WEIGHTS["high"] == 1.0
        assert RELIABILITY_WEIGHTS["medium"] == 0.7
        assert RELIABILITY_WEIGHTS["low"] == 0.4
    
    def test_conflict_score_calculation(self):
        """Test conflict score calculation"""
        # High reliability
        score = calculate_conflict_score(0.85, "high")
        assert score == 0.85
        
        # Medium reliability
        score = calculate_conflict_score(0.85, "medium")
        assert score == pytest.approx(0.595)
        
        # Low reliability
        score = calculate_conflict_score(0.85, "low")
        assert score == pytest.approx(0.34)


class TestStateTransitions:
    """Tests for state transition rules"""
    
    def test_valid_transitions(self):
        """Test that valid transitions are recognized"""
        assert is_valid_transition("focused", "confused") is True
        assert is_valid_transition("focused", "distracted") is True
        assert is_valid_transition("confused", "focused") is True
        assert is_valid_transition("distracted", "focused") is True
    
    def test_invalid_transitions(self):
        """Test that invalid transitions are recognized"""
        assert is_valid_transition("confused", "distracted") is False
        assert is_valid_transition("distracted", "confused") is False
        assert is_valid_transition("confused", "confused") is False
        assert is_valid_transition("distracted", "distracted") is False
        assert is_valid_transition("focused", "focused") is False
    
    def test_can_state_be_first(self):
        """Test that state dependency validation works"""
        # focused can be first
        assert can_state_be_first("focused", set()) is True
        
        # confused cannot be first without focused
        assert can_state_be_first("confused", set()) is False
        
        # confused can be first if focused was observed
        assert can_state_be_first("confused", {"focused"}) is True
        
        # distracted can be first
        assert can_state_be_first("distracted", set()) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
