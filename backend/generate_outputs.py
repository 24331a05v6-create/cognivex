"""
Cognivex - Generate Expected Outputs
Generates timeline.json and audit.json from the fixture dataset
"""

import os
import sys
import json

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from reconciliation.models import normalize_event
from reconciliation.engine import reconcile
from storage.database import initialize_database, save_event, get_all_events, delete_all_events


def load_fixtures():
    """Load the edge cases fixture dataset"""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'edge_cases.json')
    with open(fixture_path, 'r') as f:
        return json.load(f)


def generate_outputs():
    """Generate timeline.json and audit.json from fixtures"""
    # Initialize a temporary database
    temp_db_path = os.path.join(os.path.dirname(__file__), 'temp_generate.db')
    initialize_database(temp_db_path)
    
    try:
        # Load fixtures
        fixtures = load_fixtures()
        
        # Ingest all events
        for test_case in fixtures['test_cases']:
            for event_data in test_case['events']:
                try:
                    event = normalize_event(event_data)
                    save_event(event, temp_db_path)
                except Exception as e:
                    print(f"Error ingesting event: {e}")
        
        # Get all events
        all_events = get_all_events(temp_db_path)
        
        # Reconcile all events
        result = reconcile(all_events)
        
        # Generate timeline output
        timeline_output = {
            "description": "Reconciled cognitive timeline generated from edge_cases.json",
            "version": "1.0.0",
            "total_events": len(result.timeline),
            "timeline": result.timeline
        }
        
        # Generate audit output
        audit_records = []
        for record in result.audit:
            audit_records.append({
                "user_id": record.user_id,
                "event_ids": list(record.event_ids),
                "decision": record.decision,
                "reason": record.reason,
                "final_state": record.final_state,
                "reconciliation_order": record.reconciliation_order
            })
        
        audit_output = {
            "description": "Audit trail generated from edge_cases.json reconciliation",
            "version": "1.0.0",
            "total_decisions": len(audit_records),
            "audit_records": audit_records
        }
        
        # Write outputs
        outputs_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        os.makedirs(outputs_dir, exist_ok=True)
        
        timeline_path = os.path.join(outputs_dir, 'timeline.json')
        audit_path = os.path.join(outputs_dir, 'audit.json')
        
        with open(timeline_path, 'w') as f:
            json.dump(timeline_output, f, indent=2)
        
        with open(audit_path, 'w') as f:
            json.dump(audit_output, f, indent=2)
        
        print(f"Generated {timeline_path}")
        print(f"Generated {audit_path}")
        print(f"Timeline entries: {len(result.timeline)}")
        print(f"Audit records: {len(result.audit)}")
        
    finally:
        # Clean up temporary database
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == '__main__':
    generate_outputs()
