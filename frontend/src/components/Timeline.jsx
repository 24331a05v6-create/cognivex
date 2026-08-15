import React from 'react';

const STATES = {
  focused: { color: '#00d4aa', icon: '\u25C9' },
  confused: { color: '#ff6b6b', icon: '\u2731' },
  distracted: { color: '#ffd93d', icon: '\u25CE' },
};

export default function Timeline({ timeline, onSelectEvent, selectedEvent }) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="panel timeline-panel">
        <div className="panel-header">
          <span className="panel-icon">{'\u25B7'}</span>
          <h3>Cognitive Timeline</h3>
        </div>
        <div className="empty-state">
          <span className="empty-icon">{'\u25B7'}</span>
          <p>No reconciled cognitive events yet</p>
          <p className="empty-hint">Send an event to begin building the session timeline.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel timeline-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u25B7'}</span>
        <h3>Cognitive Timeline</h3>
        <span className="badge">{timeline.length} events</span>
      </div>
      <div className="timeline-list">
        {timeline.map((event, idx) => {
          const st = STATES[event.cognitive_state] || STATES.focused;
          const isSelected = selectedEvent === idx;
          return (
            <div
              key={idx}
              className={`timeline-item ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelectEvent(isSelected ? null : idx)}
            >
              <div className="timeline-time mono">{formatTime(event.timestamp)}</div>
              <div className="timeline-connector">
                <div className="timeline-dot" style={{ background: st.color, boxShadow: `0 0 8px ${st.color}66` }} />
                {idx < timeline.length - 1 && <div className="timeline-line" />}
              </div>
              <div className="timeline-content">
                <div className="timeline-state" style={{ color: st.color }}>
                  <span>{st.icon}</span> {event.cognitive_state.toUpperCase()}
                </div>
                <div className="timeline-meta">
                  <span>{Math.round(event.confidence * 100)}%</span>
                  <span className="separator">{'\u00B7'}</span>
                  <span>{formatSource(event.source)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatSource(s) {
  return { camera_a: 'Camera A', camera_b: 'Camera B', ui_log: 'UI Log' }[s] || s;
}

function formatTime(ts) {
  if (!ts) return '--';
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}
