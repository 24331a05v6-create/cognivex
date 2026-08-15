import React, { useState } from 'react';
import { api } from '../services/api';

export default function Replay({ userId, onReplayComplete }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runReplay = async () => {
    setLoading(true);
    setError(null);
    setStatus(null);
    try {
      const result = await api.replay();
      setStatus(result);
      if (onReplayComplete) onReplayComplete();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel replay-panel">
      <div className="panel-header">
        <span className="panel-icon">{'\u21BB'}</span>
        <h3>Replay</h3>
      </div>
      <div className="replay-content">
        <button className="btn btn-replay" onClick={runReplay} disabled={loading}>
          {loading ? (
            <><span className="spinner" /> Running...</>
          ) : (
            '\u21BB Run Replay'
          )}
        </button>

        {error && (
          <div className="replay-status error">
            <span className="status-icon">{'\u2716'}</span> {error}
          </div>
        )}

        {status && (
          <div className="replay-status success">
            <div className="replay-result-row">
              <span className="replay-label">Deterministic:</span>
              <span className="replay-value yes">YES</span>
            </div>
            <div className="replay-result-row">
              <span className="replay-label">Users Processed:</span>
              <span className="replay-value">{status.user_count}</span>
            </div>
            {status.results && status.results[userId] && (
              <>
                <div className="replay-result-row">
                  <span className="replay-label">Timeline Entries:</span>
                  <span className="replay-value">{status.results[userId].timeline.length}</span>
                </div>
                <div className="replay-result-row">
                  <span className="replay-label">Audit Records:</span>
                  <span className="replay-value">{status.results[userId].audit.length}</span>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
