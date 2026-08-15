import React, { useState } from 'react';
import { api } from '../services/api';

const DEFAULT_EVENT = {
  source: 'camera_a',
  user_id: 'u123',
  timestamp: '',
  cognitive_state: 'focused',
  confidence: 0.85,
  reliability: 'high',
};

export default function EventIngestion({ userId, onEventSent }) {
  const [form, setForm] = useState({ ...DEFAULT_EVENT, user_id: userId });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  React.useEffect(() => {
    setForm((prev) => ({ ...prev, user_id: userId }));
  }, [userId]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setResult(null);
    setError(null);
  };

  const sendEvent = async () => {
    setSending(true);
    setError(null);
    setResult(null);

    const event = {
      ...form,
      confidence: parseFloat(form.confidence),
      timestamp: form.timestamp || new Date().toISOString().replace('Z', '').split('.')[0] + 'Z',
    };

    try {
      const res = await api.ingest(event);
      setResult(res);
      if (onEventSent) onEventSent();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="panel ingest-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u27A4'}</span>
        <h3>Ingest Event</h3>
      </div>
      <div className="ingest-form">
        <div className="form-row">
          <label>Source</label>
          <select value={form.source} onChange={(e) => handleChange('source', e.target.value)}>
            <option value="camera_a">Camera A</option>
            <option value="camera_b">Camera B</option>
            <option value="ui_log">UI Log</option>
          </select>
        </div>
        <div className="form-row">
          <label>Cognitive State</label>
          <select value={form.cognitive_state} onChange={(e) => handleChange('cognitive_state', e.target.value)}>
            <option value="focused">Focused</option>
            <option value="confused">Confused</option>
            <option value="distracted">Distracted</option>
          </select>
        </div>
        <div className="form-row">
          <label>Confidence</label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={form.confidence}
            onChange={(e) => handleChange('confidence', e.target.value)}
          />
          <span className="range-value">{Math.round(form.confidence * 100)}%</span>
        </div>
        <div className="form-row">
          <label>Reliability</label>
          <select value={form.reliability} onChange={(e) => handleChange('reliability', e.target.value)}>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        <div className="form-row">
          <label>User ID</label>
          <input
            type="text"
            value={form.user_id}
            onChange={(e) => handleChange('user_id', e.target.value)}
          />
        </div>
        <button className="btn btn-send" onClick={sendEvent} disabled={sending}>
          {sending ? <><span className="spinner" /> Sending...</> : '\u27A4 Send Event'}
        </button>

        {result && (
          <div className={`ingest-result ${result.status}`}>
            {result.status === 'created' ? '\u2714 Event created' : '\u21BA Duplicate (already exists)'}
            <span className="mono"> {result.event_id}</span>
          </div>
        )}
        {error && <div className="ingest-result error">{'\u2716'} {error}</div>}
      </div>
    </div>
  );
}
