import React, { useState, useEffect, useCallback } from 'react';
import { api } from './services/api';
import CurrentState from './components/CurrentState';
import Timeline from './components/Timeline';
import SourceSignals from './components/SourceSignals';
import ConflictResolution from './components/ConflictResolution';
import AuditTrail from './components/AuditTrail';
import Replay from './components/Replay';
import EventIngestion from './components/EventIngestion';
import DemoScenarios from './components/DemoScenarios';
import './App.css';

const USERS = ['u123', 'u456', 'u789'];

export default function App() {
  const [userId, setUserId] = useState('u123');
  const [backendStatus, setBackendStatus] = useState('checking');
  const [timeline, setTimeline] = useState([]);
  const [events, setEvents] = useState([]);
  const [auditRecords, setAuditRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const checkBackend = useCallback(async () => {
    try {
      await api.health();
      setBackendStatus('connected');
    } catch {
      setBackendStatus('offline');
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [timelineRes, eventsRes, auditRes] = await Promise.all([
        api.timeline(userId),
        api.events(userId),
        api.audit(userId),
      ]);
      setTimeline(timelineRes.timeline || []);
      setEvents(eventsRes.events || []);
      setAuditRecords(auditRes.audit_records || []);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [userId, refreshKey]);

  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => clearInterval(interval);
  }, [checkBackend]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refresh = () => setRefreshKey((k) => k + 1);

  const totalEvents = events.length;
  const conflictsResolved = auditRecords.filter((r) => r.decision === 'conflict_resolved').length;
  const rejectedEvents = auditRecords.filter((r) => r.decision === 'rejected').length;
  const duplicatesIgnored = auditRecords.filter((r) => r.decision === 'duplicate_ignored').length;

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">{'\u2B22'}</span>
            <div>
              <h1>COGNIVEX</h1>
              <p className="subtitle">Real-Time Cognitive State Reconciliation</p>
            </div>
          </div>
        </div>
        <div className="header-center">
          <div className="status-indicator" data-status={backendStatus}>
            <span className="status-dot" />
            <span>{backendStatus === 'connected' ? 'Backend Connected' : backendStatus === 'checking' ? 'Checking...' : 'Backend Offline'}</span>
          </div>
        </div>
        <div className="header-right">
          <div className="user-selector">
            <label>User</label>
            <select value={userId} onChange={(e) => { setUserId(e.target.value); setSelectedEvent(null); }}>
              {USERS.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <button className="btn btn-refresh" onClick={refresh}>{'\u21BB'} Refresh</button>
        </div>
      </header>

      <main className="app-main">
        <div className="summary-cards">
          <div className="summary-card">
            <div className="card-value">{totalEvents}</div>
            <div className="card-label">Total Events</div>
          </div>
          <div className="summary-card conflicts">
            <div className="card-value">{conflictsResolved}</div>
            <div className="card-label">Conflicts Resolved</div>
          </div>
          <div className="summary-card rejected">
            <div className="card-value">{rejectedEvents}</div>
            <div className="card-label">Rejected Events</div>
          </div>
          <div className="summary-card duplicates">
            <div className="card-value">{duplicatesIgnored}</div>
            <div className="card-label">Duplicates Handled</div>
          </div>
        </div>

        <div className="dashboard-grid">
          <div className="grid-left">
            <CurrentState timeline={timeline} />
            <SourceSignals events={events} />
            <ConflictResolution auditRecords={auditRecords} />
          </div>
          <div className="grid-center">
            <Timeline
              timeline={timeline}
              onSelectEvent={setSelectedEvent}
              selectedEvent={selectedEvent}
            />
          </div>
          <div className="grid-right">
            <AuditTrail auditRecords={auditRecords} />
            <Replay userId={userId} onReplayComplete={refresh} />
          </div>
        </div>

        <div className="bottom-panels">
          <EventIngestion userId={userId} onEventSent={refresh} />
          <DemoScenarios userId={userId} onScenarioComplete={refresh} />
        </div>
      </main>

      {loading && <div className="loading-overlay"><div className="spinner large" /></div>}
    </div>
  );
}
