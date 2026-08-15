"""
Cognivex - Flask REST API
Phase 4: API layer connecting HTTP requests to event normalization and storage
"""

import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import defaultdict

# Add the backend directory to the path for imports
sys.path.insert(0, os.path.dirname(__file__))

from reconciliation.models import normalize_event, ValidationError
from reconciliation.engine import reconcile_for_user
from storage.database import (
    initialize_database,
    save_event,
    get_event,
    get_events_for_user,
    get_all_events,
    delete_all_events
)


def create_app(test_db_path=None):
    """
    Create and configure the Flask application.
    
    Args:
        test_db_path: Optional path to a test database (for testing)
    """
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Set database path
    if test_db_path:
        app.config['DATABASE_PATH'] = test_db_path
    else:
        app.config['DATABASE_PATH'] = os.path.join(
            os.path.dirname(__file__), 'cognivex.db'
        )
    
    # Initialize database on first request
    with app.app_context():
        initialize_database(app.config['DATABASE_PATH'])
    
    @app.route('/')
    def home():
        """Health check endpoint"""
        return jsonify({
            'message': 'Cognivex API is running',
            'version': '1.0.0',
            'status': 'healthy'
        })
    
    @app.route('/ingest', methods=['POST'])
    def ingest():
        """
        Ingest a cognitive event.
        
        Accepts JSON with event data, normalizes it, and stores it.
        """
        # Check if JSON body exists
        if not request.is_json:
            return jsonify({
                'error': 'Missing JSON body',
                'status': 'error'
            }), 400
        
        try:
            data = request.get_json(silent=True)
            
            # Validate JSON was parsed
            if data is None:
                return jsonify({
                    'error': 'Invalid JSON',
                    'status': 'error'
                }), 400
            
            # Normalize the event (this validates and normalizes)
            event = normalize_event(data)
            
            # Store the event
            is_new = save_event(event, app.config['DATABASE_PATH'])
            
            if is_new:
                return jsonify({
                    'event_id': event.event_id,
                    'status': 'created',
                    'event': {
                        'event_id': event.event_id,
                        'source': event.source,
                        'user_id': event.user_id,
                        'timestamp': event.timestamp,
                        'cognitive_state': event.cognitive_state,
                        'confidence': event.confidence,
                        'reliability': event.reliability
                    }
                }), 201
            else:
                return jsonify({
                    'event_id': event.event_id,
                    'status': 'duplicate',
                    'message': 'Event already exists',
                    'event': {
                        'event_id': event.event_id,
                        'source': event.source,
                        'user_id': event.user_id,
                        'timestamp': event.timestamp,
                        'cognitive_state': event.cognitive_state,
                        'confidence': event.confidence,
                        'reliability': event.reliability
                    }
                }), 200
                
        except ValidationError as e:
            return jsonify({
                'error': str(e),
                'status': 'error'
            }), 400
        except Exception as e:
            return jsonify({
                'error': 'Internal server error',
                'status': 'error'
            }), 500
    
    @app.route('/events/<user_id>', methods=['GET'])
    def get_user_events(user_id):
        """
        Get all events for a specific user.
        
        Returns events in deterministic order (timestamp, event_id).
        """
        try:
            events = get_events_for_user(user_id, app.config['DATABASE_PATH'])
            
            events_list = [
                {
                    'event_id': event.event_id,
                    'source': event.source,
                    'user_id': event.user_id,
                    'timestamp': event.timestamp,
                    'cognitive_state': event.cognitive_state,
                    'confidence': event.confidence,
                    'reliability': event.reliability
                }
                for event in events
            ]
            
            return jsonify({
                'user_id': user_id,
                'count': len(events_list),
                'events': events_list
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': 'Internal server error',
                'status': 'error'
            }), 500
    
    @app.route('/timeline/<user_id>', methods=['GET'])
    def get_timeline(user_id):
        """
        Get reconciled timeline for a user.
        
        Uses the reconciliation engine to produce a deterministic cognitive timeline.
        """
        try:
            # Get all events for the user
            events = get_events_for_user(user_id, app.config['DATABASE_PATH'])
            
            # Reconcile events
            result = reconcile_for_user(user_id, events)
            
            return jsonify({
                'user_id': user_id,
                'status': 'success',
                'timeline': result.timeline,
                'audit_count': len(result.audit)
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': 'Internal server error',
                'status': 'error'
            }), 500
    
    @app.route('/audit/<user_id>', methods=['GET'])
    def get_audit(user_id):
        """
        Get audit trail for a user.
        
        Returns the actual audit trail generated by the reconciliation engine.
        """
        try:
            # Get all events for the user
            events = get_events_for_user(user_id, app.config['DATABASE_PATH'])
            
            # Reconcile events to get audit
            result = reconcile_for_user(user_id, events)
            
            # Convert audit records to JSON-serializable format
            audit_records = []
            for record in result.audit:
                audit_records.append({
                    'user_id': record.user_id,
                    'event_ids': list(record.event_ids),
                    'decision': record.decision,
                    'reason': record.reason,
                    'final_state': record.final_state,
                    'reconciliation_order': record.reconciliation_order
                })
            
            return jsonify({
                'user_id': user_id,
                'status': 'success',
                'audit_count': len(audit_records),
                'audit_records': audit_records
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': 'Internal server error',
                'status': 'error'
            }), 500
    
    @app.route('/replay', methods=['POST'])
    def replay():
        """
        Replay all stored events through the reconciliation engine.
        
        Returns deterministic timeline and audit output.
        """
        try:
            # Get all events from the database
            all_events = get_all_events(app.config['DATABASE_PATH'])
            
            # Group events by user_id
            user_events = defaultdict(list)
            for event in all_events:
                user_events[event.user_id].append(event)
            
            # Reconcile for each user
            replay_results = {}
            for user_id, events in user_events.items():
                result = reconcile_for_user(user_id, events)
                
                # Convert audit records to JSON-serializable format
                audit_records = []
                for record in result.audit:
                    audit_records.append({
                        'user_id': record.user_id,
                        'event_ids': list(record.event_ids),
                        'decision': record.decision,
                        'reason': record.reason,
                        'final_state': record.final_state,
                        'reconciliation_order': record.reconciliation_order
                    })
                
                replay_results[user_id] = {
                    'timeline': result.timeline,
                    'audit': audit_records
                }
            
            return jsonify({
                'status': 'success',
                'deterministic': True,
                'user_count': len(replay_results),
                'results': replay_results
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': 'Internal server error',
                'status': 'error'
            }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return jsonify({
            'error': 'Endpoint not found',
            'status': 'error'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 errors"""
        return jsonify({
            'error': 'Method not allowed',
            'status': 'error'
        }), 405
    
    return app


# Create the application instance
app = create_app()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
