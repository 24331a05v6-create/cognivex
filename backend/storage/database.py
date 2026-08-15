"""
Cognivex - SQLite Storage Layer
Phase 3: Local SQLite event storage for normalized cognitive events
"""

import sqlite3
import os
from typing import List, Optional
from contextlib import contextmanager

# Import the CognitiveEvent model from Phase 2
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from reconciliation.models import CognitiveEvent


# Default database path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'cognivex.db')


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH):
    """
    Context manager for SQLite database connections.
    
    Ensures connections are properly closed and transactions are committed.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Create the database and events table if they do not exist.
    
    This function is idempotent - calling it multiple times has no effect.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                cognitive_state TEXT NOT NULL,
                confidence REAL NOT NULL,
                reliability TEXT NOT NULL
            )
        ''')
        
        # Create indexes for efficient retrieval
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_events_user_id 
            ON events (user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_events_timestamp 
            ON events (timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_events_user_timestamp 
            ON events (user_id, timestamp)
        ''')
        
        conn.commit()


def save_event(event: CognitiveEvent, db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Store a normalized CognitiveEvent in the database.
    
    Args:
        event: CognitiveEvent instance to store
        db_path: Path to the SQLite database file
        
    Returns:
        True if the event was newly inserted
        False if the event already existed (idempotent)
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO events (event_id, source, user_id, timestamp, 
                                   cognitive_state, confidence, reliability)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.event_id,
                event.source,
                event.user_id,
                event.timestamp,
                event.cognitive_state,
                event.confidence,
                event.reliability
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Event already exists - idempotent behavior
            return False


def get_event(event_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[CognitiveEvent]:
    """
    Retrieve a single event by event_id.
    
    Args:
        event_id: The unique event identifier
        db_path: Path to the SQLite database file
        
    Returns:
        CognitiveEvent if found, None otherwise
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT event_id, source, user_id, timestamp, 
                   cognitive_state, confidence, reliability
            FROM events
            WHERE event_id = ?
        ''', (event_id,))
        
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return CognitiveEvent(
            event_id=row['event_id'],
            source=row['source'],
            user_id=row['user_id'],
            timestamp=row['timestamp'],
            cognitive_state=row['cognitive_state'],
            confidence=row['confidence'],
            reliability=row['reliability']
        )


def get_events_for_user(user_id: str, db_path: str = DEFAULT_DB_PATH) -> List[CognitiveEvent]:
    """
    Retrieve all events for a specific user, ordered by timestamp then event_id.
    
    Args:
        user_id: The user identifier
        db_path: Path to the SQLite database file
        
    Returns:
        List of CognitiveEvent instances in deterministic order
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT event_id, source, user_id, timestamp, 
                   cognitive_state, confidence, reliability
            FROM events
            WHERE user_id = ?
            ORDER BY timestamp ASC, event_id ASC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        
        return [
            CognitiveEvent(
                event_id=row['event_id'],
                source=row['source'],
                user_id=row['user_id'],
                timestamp=row['timestamp'],
                cognitive_state=row['cognitive_state'],
                confidence=row['confidence'],
                reliability=row['reliability']
            )
            for row in rows
        ]


def get_all_events(db_path: str = DEFAULT_DB_PATH) -> List[CognitiveEvent]:
    """
    Retrieve all stored events in deterministic order.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        List of all CognitiveEvent instances ordered by timestamp then event_id
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT event_id, source, user_id, timestamp, 
                   cognitive_state, confidence, reliability
            FROM events
            ORDER BY timestamp ASC, event_id ASC
        ''')
        
        rows = cursor.fetchall()
        
        return [
            CognitiveEvent(
                event_id=row['event_id'],
                source=row['source'],
                user_id=row['user_id'],
                timestamp=row['timestamp'],
                cognitive_state=row['cognitive_state'],
                confidence=row['confidence'],
                reliability=row['reliability']
            )
            for row in rows
        ]


def delete_all_events(db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Delete all events from the database.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Number of events deleted
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM events')
        count = cursor.fetchone()[0]
        
        cursor.execute('DELETE FROM events')
        conn.commit()
        
        return count
