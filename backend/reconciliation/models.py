"""
Cognivex - Event Schema & Normalization
Phase 2: Standard cognitive event model and input normalization
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import hashlib
import json


# Supported sources
VALID_SOURCES = {"camera_a", "camera_b", "ui_log"}

# Supported cognitive states
VALID_COGNITIVE_STATES = {"focused", "confused", "distracted"}

# Supported reliability levels
VALID_RELIABILITY = {"high", "medium", "low"}


class ValidationError(Exception):
    """Raised when event validation fails"""
    pass


@dataclass(frozen=True)
class CognitiveEvent:
    """
    Standard cognitive event model.
    
    This is an immutable dataclass representing a normalized cognitive event.
    All fields are validated and normalized upon creation.
    """
    event_id: str
    source: str
    user_id: str
    timestamp: str
    cognitive_state: str
    confidence: float
    reliability: str


def generate_event_id(source: str, user_id: str, timestamp: str, 
                      cognitive_state: str, confidence: float, 
                      reliability: str) -> str:
    """
    Generate a deterministic event ID from normalized event fields.
    
    Uses SHA-256 hashing to create a reproducible identifier.
    The same normalized input will always produce the same event_id.
    """
    # Create a canonical string representation of the event
    canonical = json.dumps({
        "source": source,
        "user_id": user_id,
        "timestamp": timestamp,
        "cognitive_state": cognitive_state,
        "confidence": confidence,
        "reliability": reliability
    }, sort_keys=True)
    
    # Generate SHA-256 hash and return first 16 characters
    hash_object = hashlib.sha256(canonical.encode('utf-8'))
    return hash_object.hexdigest()[:16]


def normalize_timestamp(timestamp_str: str) -> str:
    """
    Normalize an ISO-8601 timestamp to a consistent UTC representation.
    
    Handles various ISO-8601 formats and ensures consistent formatting.
    """
    try:
        # Try parsing with various formats
        if timestamp_str.endswith('Z'):
            # Handle Z suffix
            dt = datetime.fromisoformat(timestamp_str[:-1])
            dt = dt.replace(tzinfo=timezone.utc)
        elif '+' in timestamp_str or timestamp_str.endswith('-00:00'):
            # Handle timezone offsets
            dt = datetime.fromisoformat(timestamp_str)
        else:
            # Assume UTC if no timezone info
            dt = datetime.fromisoformat(timestamp_str)
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to UTC if not already
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        
        # Format consistently: YYYY-MM-DDTHH:MM:SS.ffffffZ
        # Remove trailing zeros in microseconds for cleaner output
        formatted = dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        # Remove trailing zeros in microseconds but keep at least 3 digits
        if '.' in formatted:
            base, frac = formatted.split('.')
            frac = frac.rstrip('Z')
            # Keep at least 3 digits for milliseconds
            frac = frac[:3] if len(frac) >= 3 else frac.ljust(3, '0')
            formatted = f"{base}.{frac}Z"
        
        return formatted
    except ValueError as e:
        raise ValidationError(f"Invalid timestamp format: {timestamp_str}. Error: {e}")


def validate_event(data: dict) -> None:
    """
    Validate event data and raise ValidationError with clear messages.
    
    Args:
        data: Dictionary containing event data
        
    Raises:
        ValidationError: If any validation fails
    """
    # Check required fields
    required_fields = ["source", "user_id", "timestamp", "cognitive_state", 
                       "confidence", "reliability"]
    
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")
    
    # Validate source
    source = str(data["source"]).strip().lower()
    if not source:
        raise ValidationError("Source cannot be empty")
    if source not in VALID_SOURCES:
        raise ValidationError(
            f"Invalid source: {source}. "
            f"Supported sources: {', '.join(sorted(VALID_SOURCES))}"
        )
    
    # Validate user_id
    user_id = str(data["user_id"]).strip()
    if not user_id:
        raise ValidationError("user_id cannot be empty")
    
    # Validate cognitive_state
    cognitive_state = str(data["cognitive_state"]).strip().lower()
    if not cognitive_state:
        raise ValidationError("cognitive_state cannot be empty")
    if cognitive_state not in VALID_COGNITIVE_STATES:
        raise ValidationError(
            f"Invalid cognitive_state: {cognitive_state}. "
            f"Supported states: {', '.join(sorted(VALID_COGNITIVE_STATES))}"
        )
    
    # Validate confidence
    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError):
        raise ValidationError(
            f"Invalid confidence value: {data['confidence']}. "
            f"Must be a number between 0.0 and 1.0"
        )
    
    if confidence < 0.0 or confidence > 1.0:
        raise ValidationError(
            f"Confidence out of range: {confidence}. "
            f"Must be between 0.0 and 1.0"
        )
    
    # Validate reliability
    reliability = str(data["reliability"]).strip().lower()
    if not reliability:
        raise ValidationError("reliability cannot be empty")
    if reliability not in VALID_RELIABILITY:
        raise ValidationError(
            f"Invalid reliability: {reliability}. "
            f"Supported values: {', '.join(sorted(VALID_RELIABILITY))}"
        )
    
    # Validate timestamp (will be done during normalization)
    timestamp_str = str(data["timestamp"]).strip()
    if not timestamp_str:
        raise ValidationError("timestamp cannot be empty")


def normalize_event(raw_data: dict) -> CognitiveEvent:
    """
    Normalize raw event data into a standard CognitiveEvent.
    
    Flow:
        raw input -> validate -> normalize -> return standard event
    
    Args:
        raw_data: Dictionary containing raw event data
        
    Returns:
        Normalized CognitiveEvent instance
        
    Raises:
        ValidationError: If validation fails
    """
    # Step 1: Validate
    validate_event(raw_data)
    
    # Step 2: Normalize fields
    source = str(raw_data["source"]).strip().lower()
    user_id = str(raw_data["user_id"]).strip()
    cognitive_state = str(raw_data["cognitive_state"]).strip().lower()
    confidence = round(float(raw_data["confidence"]), 2)
    reliability = str(raw_data["reliability"]).strip().lower()
    timestamp = normalize_timestamp(str(raw_data["timestamp"]).strip())
    
    # Step 3: Generate deterministic event_id
    event_id = generate_event_id(
        source=source,
        user_id=user_id,
        timestamp=timestamp,
        cognitive_state=cognitive_state,
        confidence=confidence,
        reliability=reliability
    )
    
    # Step 4: Return standard event
    return CognitiveEvent(
        event_id=event_id,
        source=source,
        user_id=user_id,
        timestamp=timestamp,
        cognitive_state=cognitive_state,
        confidence=confidence,
        reliability=reliability
    )
