import React from 'react';

const DECISION_STYLES = {
  conflict_resolved: { icon: '\u2714', color: '#00d4aa', label: 'Conflict Resolved' },
  duplicate_ignored: { icon: '\u21BA', color: '#7eb8da', label: 'Duplicate Ignored' },
  replaced: { icon: '\u21C4', color: '#c084fc', label: 'Replaced' },
  rejected: { icon: '\u26A0', color: '#ff6b6b', label: 'Rejected' },
  accepted: { icon: '\u2714', color: '#00d4aa', label: 'Accepted' },
};

export default function AuditTrail({ auditRecords }) {
  return (
    <div className="panel audit-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u{1F4CB}'}</span>
        <h3>Audit Trail</h3>
        <span className="badge">{(auditRecords || []).length} decisions</span>
      </div>
      {!auditRecords || auditRecords.length === 0 ? (
        <div className="empty-state compact">
          <p>No audit records.</p>
        </div>
      ) : (
        <div className="audit-list">
          {auditRecords.map((record, idx) => {
            const style = DECISION_STYLES[record.decision] || DECISION_STYLES.accepted;
            return (
              <div key={idx} className="audit-entry">
                <div className="audit-icon" style={{ color: style.color }}>{style.icon}</div>
                <div className="audit-content">
                  <div className="audit-decision" style={{ color: style.color }}>{style.label}</div>
                  <div className="audit-reason">{record.reason}</div>
                  {record.final_state && (
                    <div className="audit-final-state">
                      Final: <span style={{ color: getStateColor(record.final_state) }}>{record.final_state}</span>
                    </div>
                  )}
                </div>
                <div className="audit-order mono">#{record.reconciliation_order}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function getStateColor(state) {
  return { focused: '#00d4aa', confused: '#ff6b6b', distracted: '#ffd93d' }[state] || '#aaa';
}
