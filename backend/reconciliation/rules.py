"""
Cognivex - Reconciliation Rules
Phase 5: State transition rules, reliability weights, and conflict resolution constants
"""

# =============================================================================
# RELIABILITY WEIGHTS
# =============================================================================
# Used for conflict resolution scoring: score = confidence × reliability_weight

RELIABILITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4
}

# =============================================================================
# VALID COGNITIVE STATES
# =============================================================================

VALID_STATES = {"focused", "confused", "distracted"}

# =============================================================================
# STATE TRANSITION RULES
# =============================================================================
# Define which cognitive state transitions are valid.
# A transition is valid if the "from_state" has been observed earlier in the user's session.
# 
# Rule: "confused" is only valid if "focused" occurred earlier for the same user.
# This prevents "confused" as the first observed state without context.

# Valid transitions: (from_state, to_state)
VALID_TRANSITIONS = {
    ("focused", "confused"),      # focused → confused is valid
    ("focused", "distracted"),    # focused → distracted is valid
    ("confused", "focused"),      # confused → focused is valid
    ("distracted", "focused"),    # distracted → focused is valid
}

# States that require a prior state to be valid
# Key: state that requires validation
# Value: set of states that must have been observed earlier
STATE_DEPENDENCIES = {
    "confused": {"focused"},      # confused requires focused to have been seen
}

# =============================================================================
# DUPLICATE HANDLING RULES
# =============================================================================
# Define how duplicates are identified and resolved.
#
# Rule: "Duplicate event from same source at different timestamp → keep latest"
#
# Duplicate identity: same (source, user_id, cognitive_state)
# Resolution: Keep the event with the latest timestamp

# Fields that define a duplicate group (same observation, different time)
DUPLICATE_IDENTITY_FIELDS = ("source", "user_id", "cognitive_state")

# =============================================================================
# TEMPORAL CONFLICT GROUPING
# =============================================================================
# Events with the same normalized timestamp are considered a conflict group.

# =============================================================================
# UI INTERACTION PROXIMITY
# =============================================================================
# UI log events are considered interaction events.
# When a UI interaction and cognitive event occur at the same timestamp,
# the UI interaction is considered temporally relevant.

INTERACTION_SOURCES = {"ui_log"}

# =============================================================================
# AUDIT DECISION TYPES
# =============================================================================

AUDIT_DECISIONS = {
    "accepted": "Event accepted into timeline",
    "duplicate_ignored": "Duplicate event with identical deterministic event_id",
    "replaced": "Event replaced by newer observation from same source",
    "conflict_resolved": "Conflict between events resolved by scoring",
    "rejected": "Event rejected due to dependency violation",
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_reliability_weight(reliability: str) -> float:
    """
    Get the reliability weight for scoring.
    
    Args:
        reliability: The reliability level (high, medium, low)
        
    Returns:
        Weight value (1.0, 0.7, or 0.4)
    """
    return RELIABILITY_WEIGHTS.get(reliability, 0.4)


def calculate_conflict_score(confidence: float, reliability: str) -> float:
    """
    Calculate the conflict resolution score.
    
    score = confidence × reliability_weight
    
    Args:
        confidence: Confidence value (0.0 to 1.0)
        reliability: Reliability level (high, medium, low)
        
    Returns:
        Conflict score
    """
    weight = get_reliability_weight(reliability)
    return confidence * weight


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """
    Check if a state transition is valid.
    
    Args:
        from_state: The previous cognitive state
        to_state: The new cognitive state
        
    Returns:
        True if transition is valid, False otherwise
    """
    return (from_state, to_state) in VALID_TRANSITIONS


def can_state_be_first(state: str, observed_states: set) -> bool:
    """
    Check if a state can be the first observed state or if it requires prior context.
    
    Args:
        state: The cognitive state to validate
        observed_states: Set of states already observed in the session
        
    Returns:
        True if the state can be accepted, False otherwise
    """
    if state not in STATE_DEPENDENCIES:
        return True
    
    required_prior_states = STATE_DEPENDENCIES[state]
    return bool(required_prior_states & observed_states)


def get_duplicate_identity_key(event) -> tuple:
    """
    Generate a duplicate identity key for an event.
    
    Args:
        event: CognitiveEvent instance
        
    Returns:
        Tuple of (source, user_id, cognitive_state)
    """
    return (event.source, event.user_id, event.cognitive_state)
