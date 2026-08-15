# Cognivex

**Real-Time Cognitive State Reconciliation**

A local real-time cognitive state reconciliation system that ingests asynchronous events from multiple sources, deterministically reconciles conflicts, and produces an auditable cognitive timeline.

**Live Demo:** [https://cognivex-654j.vercel.app](https://cognivex-654j.vercel.app)

**Demo Video:** [Watch on Google Drive](https://drive.google.com/file/d/1bZOjXjUOcz4I2jVp24kJ02ibxRvkVV5j/view?usp=sharing)

---

## Problem Statement

In multi-modal cognitive monitoring, events arrive from different sources (cameras, UI logs, sensors) at different times, with different reliability levels, and sometimes with conflicting observations. A robust system must:

- Accept events from multiple sources
- Normalize and store them reliably
- Reconcile conflicts using deterministic rules
- Produce a single coherent cognitive timeline per user
- Record every decision in an audit trail
- Support replay for verification

## Solution

Cognivex provides a complete backend (Flask + SQLite) and frontend (React + Vite) for deterministic cognitive state reconciliation. Events are normalized, stored, and reconciled using a pure function that guarantees same input always produces same output.

---

## Architecture

```
Cognitive Event Sources (camera_a, camera_b, ui_log)
                |
                v
         Flask REST API
                |
                v
        Event Normalization
                |
                v
            SQLite
                |
                v
    Deterministic Reconciliation Engine
                |
                v
        Timeline + Audit Trail
                |
                v
        React Dashboard (Vite)
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite 6 |
| Backend | Python 3, Flask, flask-cors |
| Database | SQLite (local file) |
| Testing | pytest |

---

## Key Features

- **Multi-source ingestion** — camera_a, camera_b, ui_log
- **Deterministic event IDs** — SHA-256 hash of normalized fields
- **Temporal reconciliation** — chronological ordering, late events
- **Conflict resolution** — confidence x reliability scoring
- **State dependency rules** — confused requires prior focused
- **Full audit trail** — every decision recorded with reason
- **Replay** — deterministic re-processing of all events
- **Idempotency** — duplicates handled correctly
- **Multi-user isolation** — events never leak between users
- **Premium dark dashboard** — cybersecurity/AI aesthetic

---

## Event Schema

```json
{
  "source": "camera_a",
  "user_id": "u123",
  "timestamp": "2024-07-01T10:00:00Z",
  "cognitive_state": "focused",
  "confidence": 0.85,
  "reliability": "high"
}
```

| Field | Type | Values |
|-------|------|--------|
| `source` | string | `camera_a`, `camera_b`, `ui_log` |
| `user_id` | string | Non-empty identifier |
| `timestamp` | string | ISO-8601 UTC |
| `cognitive_state` | string | `focused`, `confused`, `distracted` |
| `confidence` | number | 0.0 - 1.0 |
| `reliability` | string | `high`, `medium`, `low` |

---

## Reconciliation Logic

### Processing Pipeline

1. **Sort** — timestamp ascending, then event_id ascending
2. **Deduplicate** — remove exact duplicates (same event_id)
3. **Same-source resolution** — keep latest observation per (source, user, state)
4. **Group conflicts** — events at same timestamp per user
5. **Validate dependencies** — confused requires prior focused
6. **Resolve conflicts** — score = confidence x reliability_weight
7. **Generate timeline** — ordered cognitive states
8. **Generate audit** — every decision recorded

### Reliability Weights

| Reliability | Weight |
|-------------|--------|
| high | 1.0 |
| medium | 0.7 |
| low | 0.4 |

### Conflict Resolution

When events conflict at the same timestamp:

```
score = confidence x reliability_weight
```

Higher score wins. Ties broken by event_id.

### State Dependency Rules

- `confused` is only valid if `focused` occurred earlier in the user's session
- `distracted` is only valid if `focused` occurred earlier
- First event must be `focused`

### Audit Decision Types

| Decision | Description |
|----------|-------------|
| `accepted` | Event accepted into timeline |
| `duplicate_ignored` | Exact duplicate removed |
| `replaced` | Older same-source event replaced |
| `conflict_resolved` | Conflict resolved by scoring |
| `rejected` | Event rejected (dependency violation) |

---

## API Endpoints

### POST /ingest

Ingest a cognitive event.

```bash
curl -X POST http://localhost:5000/ingest \
  -H "Content-Type: application/json" \
  -d '{"source":"camera_a","user_id":"u123","timestamp":"2024-07-01T10:00:00Z","cognitive_state":"focused","confidence":0.85,"reliability":"high"}'
```

**Response (201):**
```json
{
  "event_id": "cb093e41aa4180d9",
  "status": "created",
  "event": { ... }
}
```

**Response (200 — duplicate):**
```json
{
  "event_id": "cb093e41aa4180d9",
  "status": "duplicate",
  "message": "Event already exists"
}
```

### GET /timeline/<user_id>

Get reconciled cognitive timeline.

```bash
curl http://localhost:5000/timeline/u123
```

**Response:**
```json
{
  "user_id": "u123",
  "status": "success",
  "timeline": [
    {
      "timestamp": "2024-07-01T10:00:00.000Z",
      "cognitive_state": "focused",
      "confidence": 0.85,
      "source": "camera_a"
    }
  ],
  "audit_count": 1
}
```

### GET /audit/<user_id>

Get audit trail for reconciliation decisions.

```bash
curl http://localhost:5000/audit/u123
```

**Response:**
```json
{
  "user_id": "u123",
  "status": "success",
  "audit_count": 1,
  "audit_records": [
    {
      "user_id": "u123",
      "event_ids": ["event1", "event2"],
      "decision": "conflict_resolved",
      "reason": "Conflict resolved: focused won with score 0.85",
      "final_state": "focused",
      "reconciliation_order": 0
    }
  ]
}
```

### POST /replay

Re-run deterministic reconciliation on all stored events.

```bash
curl -X POST http://localhost:5000/replay
```

**Response:**
```json
{
  "status": "success",
  "deterministic": true,
  "user_count": 2,
  "results": {
    "u123": {
      "timeline": [...],
      "audit": [...]
    }
  }
}
```

---

## Project Structure

```
cognivex/
├── backend/
│   ├── app.py                    # Flask application
│   ├── reconciliation/
│   │   ├── models.py             # CognitiveEvent, normalization
│   │   ├── rules.py              # Weights, transitions, helpers
│   │   └── engine.py             # Reconciliation engine
│   ├── storage/
│   │   └── database.py           # SQLite CRUD
│   ├── tests/
│   │   ├── test_models.py        # 36 tests
│   │   ├── test_database.py      # 20 tests
│   │   ├── test_api.py           # 22 tests
│   │   ├── test_reconciliation.py # 32 tests
│   │   └── test_phase6_7.py      # 22 tests
│   ├── fixtures/
│   │   └── edge_cases.json       # 6 edge case scenarios
│   └── generate_outputs.py       # Output generator
├── frontend/
│   ├── index.html                # Vite entry HTML
│   ├── package.json              # React + Vite config
│   ├── vite.config.js            # Vite configuration
│   └── src/
│       ├── index.jsx             # React entry point
│       ├── App.jsx               # Main dashboard
│       ├── App.css               # Dark theme styles
│       ├── components/
│       │   ├── CurrentState.jsx
│       │   ├── Timeline.jsx
│       │   ├── SourceSignals.jsx
│       │   ├── ConflictResolution.jsx
│       │   ├── AuditTrail.jsx
│       │   ├── Replay.jsx
│       │   ├── EventIngestion.jsx
│       │   └── DemoScenarios.jsx
│       └── services/
│           └── api.js            # API service layer
├── outputs/
│   ├── timeline.json             # Generated timeline
│   └── audit.json                # Generated audit
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Setup Instructions

### Backend

```bash
cd cognivex/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r ../requirements.txt
python app.py
```

Backend runs at `http://localhost:5000`

### Frontend

```bash
cd cognivex/frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

### Production Build

```bash
cd cognivex/frontend
npm run build    # Output in dist/
npm run preview  # Preview production build
```

---

## Running Tests

```bash
cd cognivex/backend
python -m pytest tests/ -v
```

**132 tests** covering:
- Event normalization and validation (36)
- SQLite storage and idempotency (20)
- Flask REST API endpoints (22)
- Reconciliation engine logic (32)
- Audit, replay, edge cases (22)

---

## Fixture Dataset

`backend/fixtures/edge_cases.json` covers all required edge cases:

| Case | Scenario |
|------|----------|
| CASE_1 | Exact duplicate (same event_id) |
| CASE_2 | Same source duplicate (different timestamps) |
| CASE_3 | Camera A vs UI Log conflict |
| CASE_4 | Late/out-of-order event |
| CASE_5 | Invalid dependency (confused before focused) |
| CASE_6 | Multi-user isolation |

---

## Example Outputs

Generated from fixture dataset via `python generate_outputs.py`:

- `outputs/timeline.json` — 11 reconciled timeline entries
- `outputs/audit.json` — 4 audit decisions

---

## MVP Limitations

- **Synthetic events only** — The MVP uses manually created or programmatically generated cognitive events. It does not perform real facial-expression detection or video analysis.
- **OpenCV/TensorFlow not included** — Real video-processing pipelines (OpenCV, TensorFlow) are external upstream inputs that could be connected to the `/ingest` endpoint in a future implementation.
- **Single-node architecture** — Designed for local/demo use, not distributed deployment.
- **No authentication** — Open API for demonstration purposes.

---

## Future Enhancements

- Real-time video processing pipeline integration (OpenCV/TensorFlow)
- WebSocket support for live event streaming
- User authentication and session management
- Historical analytics and trend visualization
- Multi-node distributed deployment
- React Native mobile dashboard

---

## License

This project is for educational purposes.
