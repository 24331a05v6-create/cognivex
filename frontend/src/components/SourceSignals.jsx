import React from 'react';

const STATE_COLORS = {
  focused: '#00d4aa',
  confused: '#ff6b6b',
  distracted: '#ffd93d',
};

const RELIABILITY_COLORS = {
  high: '#00d4aa',
  medium: '#7eb8da',
  low: '#ff6b6b',
};

const SOURCE_ICONS = {
  camera_a: '\u{1F4F7}',
  camera_b: '\u{1F4F9}',
  ui_log: '\u{1F4DD}',
};

export default function SourceSignals({ events }) {
  const sourceMap = {};

  if (events && events.length > 0) {
    events.forEach((e) => {
      if (!sourceMap[e.source] || new Date(e.timestamp) > new Date(sourceMap[e.source].timestamp)) {
        sourceMap[e.source] = e;
      }
    });
  }

  const sources = ['camera_a', 'camera_b', 'ui_log'];

  return (
    <div className="panel source-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u25C8'}</span>
        <h3>Source Signals</h3>
      </div>
      <div className="source-grid">
        {sources.map((src) => {
          const evt = sourceMap[src];
          return (
            <div key={src} className={`source-card ${evt ? 'active' : 'inactive'}`}>
              <div className="source-icon">{SOURCE_ICONS[src] || '\u25CF'}</div>
              <div className="source-name">{formatSource(src)}</div>
              {evt ? (
                <>
                  <div
                    className="source-state"
                    style={{ color: STATE_COLORS[evt.cognitive_state] || '#aaa' }}
                  >
                    {evt.cognitive_state.toUpperCase()}
                  </div>
                  <div className="source-details">
                    <div className="source-detail">
                      <span className="detail-label">Confidence</span>
                      <span className="detail-value">{Math.round(evt.confidence * 100)}%</span>
                    </div>
                    <div className="source-detail">
                      <span className="detail-label">Reliability</span>
                      <span
                        className="detail-value reliability-badge"
                        style={{ color: RELIABILITY_COLORS[evt.reliability] || '#aaa' }}
                      >
                        {evt.reliability.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="source-no-data">No data</div>
              )}
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
