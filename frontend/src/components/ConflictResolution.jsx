import React from 'react';

export default function ConflictResolution({ auditRecords }) {
  const conflicts = (auditRecords || []).filter(
    (r) => r.decision === 'conflict_resolved' || r.decision === 'rejected'
  );

  return (
    <div className="panel conflict-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u2694'}</span>
        <h3>Conflict Resolution</h3>
        <span className="badge">{conflicts.length}</span>
      </div>
      {conflicts.length === 0 ? (
        <div className="empty-state compact">
          <p>No conflicts recorded.</p>
        </div>
      ) : (
        <div className="conflict-list">
          {conflicts.map((record, idx) => (
            <div key={idx} className={`conflict-card ${record.decision}`}>
              <div className="conflict-decision-badge" data-decision={record.decision}>
                {record.decision === 'conflict_resolved' ? '\u2714 RESOLVED' : '\u26A0 REJECTED'}
              </div>
              <div className="conflict-reason">{record.reason}</div>
              {record.final_state && (
                <div className="conflict-result">
                  Final state: <strong style={{ color: getStateColor(record.final_state) }}>{record.final_state.toUpperCase()}</strong>
                </div>
              )}
              <div className="conflict-events">
                Events: {record.event_ids.length} considered
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function getStateColor(state) {
  return { focused: '#00d4aa', confused: '#ff6b6b', distracted: '#ffd93d' }[state] || '#aaa';
}
