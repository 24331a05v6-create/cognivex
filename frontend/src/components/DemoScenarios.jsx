import React, { useState } from 'react';
import { api } from '../services/api';

export default function DemoScenarios({ userId, onScenarioComplete }) {
  const [running, setRunning] = useState(null);
  const [results, setResults] = useState([]);

  const addResult = (msg, type = 'info') => {
    setResults((prev) => [...prev.slice(-4), { msg, type, time: Date.now() }]);
  };

  const runScenario = async (name, events) => {
    setRunning(name);
    addResult(`Running ${name}...`, 'running');
    try {
      for (const evt of events) {
        const event = { ...evt, user_id: userId, timestamp: evt.timestamp || new Date().toISOString().replace('Z', '').split('.')[0] + 'Z' };
        await api.ingest(event);
      }
      addResult(`${name} completed`, 'success');
      if (onScenarioComplete) onScenarioComplete();
    } catch (err) {
      addResult(`${name} failed: ${err.message}`, 'error');
    } finally {
      setRunning(null);
    }
  };

  const scenarios = [
    {
      name: 'Conflict Scenario',
      label: '\u2694 Conflict',
      events: [
        { source: 'camera_a', cognitive_state: 'focused', confidence: 0.85, reliability: 'high' },
        { source: 'ui_log', cognitive_state: 'confused', confidence: 0.60, reliability: 'medium' },
      ],
    },
    {
      name: 'Duplicate Event',
      label: '\u21BA Duplicate',
      events: [
        { source: 'camera_b', cognitive_state: 'distracted', confidence: 0.70, reliability: 'medium', timestamp: '2024-07-01T10:00:00Z' },
        { source: 'camera_b', cognitive_state: 'distracted', confidence: 0.70, reliability: 'medium', timestamp: '2024-07-01T10:00:00Z' },
      ],
    },
    {
      name: 'Late Event',
      label: '\u23F0 Late Event',
      events: [
        { source: 'camera_a', cognitive_state: 'focused', confidence: 0.90, reliability: 'high', timestamp: '2024-07-01T12:00:00Z' },
        { source: 'ui_log', cognitive_state: 'confused', confidence: 0.65, reliability: 'medium', timestamp: '2024-07-01T09:00:00Z' },
      ],
    },
  ];

  return (
    <div className="panel demo-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u2699'}</span>
        <h3>Demo Scenarios</h3>
      </div>
      <div className="demo-buttons">
        {scenarios.map((s) => (
          <button
            key={s.name}
            className="btn btn-demo"
            onClick={() => runScenario(s.name, s.events)}
            disabled={running !== null}
          >
            {running === s.name ? <span className="spinner" /> : s.label}
          </button>
        ))}
      </div>
      {results.length > 0 && (
        <div className="demo-results">
          {results.map((r, i) => (
            <div key={r.time + i} className={`demo-result ${r.type}`}>{r.msg}</div>
          ))}
        </div>
      )}
    </div>
  );
}
