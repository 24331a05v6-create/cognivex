import React from 'react';

const STATES = {
  focused: { color: '#00d4aa', bg: 'rgba(0,212,170,0.12)', label: 'FOCUSED', icon: '\u25C9' },
  confused: { color: '#ff6b6b', bg: 'rgba(255,107,107,0.12)', label: 'CONFUSED', icon: '\u2731' },
  distracted: { color: '#ffd93d', bg: 'rgba(255,217,61,0.12)', label: 'DISTRACTED', icon: '\u25CE' },
};

export default function CurrentState({ timeline }) {
  const latest = timeline && timeline.length > 0 ? timeline[timeline.length - 1] : null;
  const stateInfo = latest ? STATES[latest.cognitive_state] : null;

  return (
    <div className="panel current-state-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u2316'}</span>
        <h3>Current Cognitive State</h3>
      </div>
      {latest ? (
        <div className="current-state-display">
          <div
            className="state-badge-large"
            style={{
              color: stateInfo.color,
              background: stateInfo.bg,
              boxShadow: `0 0 30px ${stateInfo.color}22`,
            }}
          >
            <span className="state-icon">{stateInfo.icon}</span>
            <span className="state-label">{stateInfo.label}</span>
          </div>
          <div className="state-details">
            <div className="state-detail">
              <span className="detail-label">Confidence</span>
              <div className="confidence-bar-container">
                <div
                  className="confidence-bar"
                  style={{
                    width: `${latest.confidence * 100}%`,
                    background: `linear-gradient(90deg, ${stateInfo.color}88, ${stateInfo.color})`,
                  }}
                />
                <span className="confidence-value">{Math.round(latest.confidence * 100)}%</span>
              </div>
            </div>
            <div className="state-detail">
              <span className="detail-label">Source</span>
              <span className="detail-value">{formatSource(latest.source)}</span>
            </div>
            <div className="state-detail">
              <span className="detail-label">Timestamp</span>
              <span className="detail-value mono">{formatTime(latest.timestamp)}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <span className="empty-icon">{'\u25CE'}</span>
          <p>No reconciled cognitive state yet</p>
          <p className="empty-hint">Send an event to begin building the session timeline.</p>
        </div>
      )}
    </div>
  );
}

function formatSource(source) {
  const map = { camera_a: 'Camera A', camera_b: 'Camera B', ui_log: 'UI Log' };
  return map[source] || source;
}

function formatTime(ts) {
  if (!ts) return '--';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return ts;
  }
}
