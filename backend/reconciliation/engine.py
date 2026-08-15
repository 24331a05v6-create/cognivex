"""
Cognivex - Reconciliation Engine
Phase 5: Deterministic cognitive state reconciliation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from .models import CognitiveEvent
from .rules import (
    RELIABILITY_WEIGHTS,
    VALID_TRANSITIONS,
    STATE_DEPENDENCIES,
    INTERACTION_SOURCES,
    DUPLICATE_IDENTITY_FIELDS,
    calculate_conflict_score,
    is_valid_transition,
    can_state_be_first,
    get_duplicate_identity_key
)


@dataclass(frozen=True)
class AuditRecord:
    """
    Immutable audit record for reconciliation decisions.
    
    All fields are deterministic - no timestamps from system clock.
    """
    user_id: str
    event_ids: Tuple[str, ...]  # Events considered in this decision
    decision: str               # accepted, duplicate_ignored, replaced, conflict_resolved, rejected
    reason: str
    final_state: Optional[str]  # The resulting cognitive state (None if rejected)
    reconciliation_order: int   # Deterministic order of this decision


@dataclass
class ReconciliationResult:
    """
    Result of reconciliation containing timeline and audit records.
    """
    timeline: List[Dict] = field(default_factory=list)
    audit: List[AuditRecord] = field(default_factory=list)


def _sort_events(events: List[CognitiveEvent]) -> List[CognitiveEvent]:
    """
    Sort events deterministically.
    
    Primary: timestamp ascending
    Secondary: event_id ascending
    
    Args:
        events: List of CognitiveEvent objects
        
    Returns:
        Sorted list of events
    """
    return sorted(events, key=lambda e: (e.timestamp, e.event_id))


def _deduplicate_exact(events: List[CognitiveEvent]) -> Tuple[List[CognitiveEvent], List[AuditRecord]]:
    """
    Remove exact duplicates (same event_id).
    
    Args:
        events: List of CognitiveEvent objects (already sorted)
        
    Returns:
        Tuple of (deduplicated events, audit records)
    """
    seen_ids = set()
    unique_events = []
    audit_records = []
    order_counter = 0
    
    for event in events:
        if event.event_id in seen_ids:
            # Exact duplicate - create audit record
            audit_records.append(AuditRecord(
                user_id=event.user_id,
                event_ids=(event.event_id,),
                decision="duplicate_ignored",
                reason="Duplicate event with identical deterministic event_id",
                final_state=None,
                reconciliation_order=order_counter
            ))
            order_counter += 1
        else:
            seen_ids.add(event.event_id)
            unique_events.append(event)
    
    return unique_events, audit_records


def _resolve_same_source_duplicates(events: List[CognitiveEvent]) -> Tuple[List[CognitiveEvent], List[AuditRecord]]:
    """
    Handle duplicate events from same source at different timestamps.
    
    Rule: Keep the latest observation.
    
    Args:
        events: List of CognitiveEvent objects (already sorted by timestamp)
        
    Returns:
        Tuple of (resolved events, audit records)
    """
    # Group by duplicate identity (source, user_id, cognitive_state)
    groups = defaultdict(list)
    for event in events:
        key = get_duplicate_identity_key(event)
        groups[key].append(event)
    
    resolved_events = []
    audit_records = []
    order_counter = 0
    
    for key, group_events in groups.items():
        if len(group_events) == 1:
            resolved_events.append(group_events[0])
        else:
            # Multiple events from same source for same observation
            # Keep the latest (last in sorted order since sorted by timestamp)
            latest_event = group_events[-1]
            replaced_events = group_events[:-1]
            
            # Create audit record for replacement
            replaced_event_ids = tuple(e.event_id for e in replaced_events)
            audit_records.append(AuditRecord(
                user_id=latest_event.user_id,
                event_ids=(latest_event.event_id,) + replaced_event_ids,
                decision="replaced",
                reason=f"Event replaced by newer observation from same source",
                final_state=latest_event.cognitive_state,
                reconciliation_order=order_counter
            ))
            order_counter += 1
            
            resolved_events.append(latest_event)
    
    # Sort again after resolution to maintain deterministic order
    resolved_events.sort(key=lambda e: (e.timestamp, e.event_id))
    
    return resolved_events, audit_records


def _group_temporal_conflicts(events: List[CognitiveEvent]) -> List[List[CognitiveEvent]]:
    """
    Group events with the same timestamp as temporal conflict groups.
    
    Args:
        events: List of CognitiveEvent objects (already sorted)
        
    Returns:
        List of conflict groups (each group is a list of events at the same timestamp)
    """
    if not events:
        return []
    
    groups = []
    current_group = [events[0]]
    
    for i in range(1, len(events)):
        if events[i].timestamp == events[i-1].timestamp:
            current_group.append(events[i])
        else:
            groups.append(current_group)
            current_group = [events[i]]
    
    groups.append(current_group)
    return groups


def _resolve_conflict_group(
    group: List[CognitiveEvent],
    observed_states: set,
    order_counter: int
) -> Tuple[Optional[CognitiveEvent], List[AuditRecord]]:
    """
    Resolve a conflict group (events at the same timestamp).
    
    Args:
        group: List of events at the same timestamp
        observed_states: Set of states already observed in this user's session
        order_counter: Current reconciliation order counter
        
    Returns:
        Tuple of (winning event or None if rejected, audit records)
    """
    if len(group) == 1:
        event = group[0]
        # Check state dependency
        if not can_state_be_first(event.cognitive_state, observed_states):
            return None, [AuditRecord(
                user_id=event.user_id,
                event_ids=(event.event_id,),
                decision="rejected",
                reason=f"Rejected {event.cognitive_state} state because no earlier valid focused state exists",
                final_state=None,
                reconciliation_order=order_counter
            )]
        return event, []
    
    # Multiple events at same timestamp - need conflict resolution
    # Calculate scores for each event
    scored_events = []
    for event in group:
        score = calculate_conflict_score(event.confidence, event.reliability)
        scored_events.append((score, event))
    
    # Sort by score descending, then by event_id for determinism
    scored_events.sort(key=lambda x: (-x[0], x[1].event_id))
    
    winning_score, winning_event = scored_events[0]
    
    # Check state dependency for winner
    if not can_state_be_first(winning_event.cognitive_state, observed_states):
        # Winner is rejected, try next best
        for score, event in scored_events[1:]:
            if can_state_be_first(event.cognitive_state, observed_states):
                # Found a valid alternative
                all_event_ids = tuple(e.event_id for e in group)
                audit_records = [AuditRecord(
                    user_id=winning_event.user_id,
                    event_ids=all_event_ids,
                    decision="conflict_resolved",
                    reason=f"Conflict resolved: {event.cognitive_state} accepted over {winning_event.cognitive_state} due to state dependency",
                    final_state=event.cognitive_state,
                    reconciliation_order=order_counter
                )]
                return event, audit_records
        
        # No valid alternative found - reject all
        all_event_ids = tuple(e.event_id for e in group)
        audit_records = [AuditRecord(
            user_id=winning_event.user_id,
            event_ids=all_event_ids,
            decision="rejected",
            reason=f"Rejected all events at timestamp {winning_event.timestamp} due to state dependency violations",
            final_state=None,
            reconciliation_order=order_counter
        )]
        return None, audit_records
    
    # Winner is valid
    all_event_ids = tuple(e.event_id for e in group)
    audit_records = [AuditRecord(
        user_id=winning_event.user_id,
        event_ids=all_event_ids,
        decision="conflict_resolved",
        reason=f"Conflict resolved: {winning_event.cognitive_state} won with score {winning_score:.2f}",
        final_state=winning_event.cognitive_state,
        reconciliation_order=order_counter
    )]
    
    return winning_event, audit_records


def _group_temporal_conflicts_by_user(events: List[CognitiveEvent]) -> List[Tuple[str, List[CognitiveEvent]]]:
    """
    Group events by user and then by timestamp as temporal conflict groups.
    
    This ensures user isolation - events from different users are processed independently.
    
    Args:
        events: List of CognitiveEvent objects (already sorted)
        
    Returns:
        List of (user_id, conflict_group) tuples
    """
    if not events:
        return []
    
    # Group by user first
    user_groups = defaultdict(list)
    for event in events:
        user_groups[event.user_id].append(event)
    
    # Then group by timestamp within each user
    all_groups = []
    for user_id in sorted(user_groups.keys()):
        user_events = user_groups[user_id]
        current_group = [user_events[0]]
        
        for i in range(1, len(user_events)):
            if user_events[i].timestamp == user_events[i-1].timestamp:
                current_group.append(user_events[i])
            else:
                all_groups.append((user_id, current_group))
                current_group = [user_events[i]]
        
        all_groups.append((user_id, current_group))
    
    return all_groups


def reconcile(events: List[CognitiveEvent]) -> ReconciliationResult:
    """
    Main reconciliation function.
    
    Takes a collection of normalized CognitiveEvents and produces:
    1. A deterministic cognitive timeline
    2. Audit records describing every reconciliation decision
    
    This function is pure - it does not depend on database or Flask.
    Same input always produces same output regardless of arrival order.
    
    Args:
        events: List of CognitiveEvent objects
        
    Returns:
        ReconciliationResult with timeline and audit records
    """
    result = ReconciliationResult()
    
    if not events:
        return result
    
    # Step 1: Deterministic ordering
    sorted_events = _sort_events(events)
    
    # Step 2: Exact duplicate removal
    deduplicated, exact_dup_audits = _deduplicate_exact(sorted_events)
    result.audit.extend(exact_dup_audits)
    
    # Step 3: Same source duplicate handling
    resolved, source_dup_audits = _resolve_same_source_duplicates(deduplicated)
    result.audit.extend(source_dup_audits)
    
    # Step 4: Group temporal conflicts (with user isolation)
    conflict_groups = _group_temporal_conflicts_by_user(resolved)
    
    # Step 5: Process each conflict group
    observed_states_per_user = defaultdict(set)
    order_counter = len(result.audit)
    
    for user_id, group in conflict_groups:
        # Get observed states for this specific user
        observed_states = observed_states_per_user[user_id]
        
        winning_event, group_audits = _resolve_conflict_group(
            group, observed_states, order_counter
        )
        
        result.audit.extend(group_audits)
        order_counter += len(group_audits)
        
        if winning_event is not None:
            # Add to timeline
            result.timeline.append({
                "timestamp": winning_event.timestamp,
                "cognitive_state": winning_event.cognitive_state,
                "confidence": winning_event.confidence,
                "source": winning_event.source
            })
            
            # Track observed states for this user only
            observed_states_per_user[user_id].add(winning_event.cognitive_state)
    
    return result


def reconcile_for_user(user_id: str, events: List[CognitiveEvent]) -> ReconciliationResult:
    """
    Reconcile events for a specific user.
    
    Filters events by user_id before reconciliation.
    
    Args:
        user_id: The user identifier
        events: List of all CognitiveEvent objects
        
    Returns:
        ReconciliationResult for the specified user
    """
    user_events = [e for e in events if e.user_id == user_id]
    return reconcile(user_events)
