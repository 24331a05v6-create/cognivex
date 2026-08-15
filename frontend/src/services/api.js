const API_BASE = 'http://127.0.0.1:5000';

async function apiCall(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  const response = await fetch(url, config);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }

  return data;
}

export const api = {
  health: () => apiCall('/'),
  ingest: (event) => apiCall('/ingest', { method: 'POST', body: JSON.stringify(event) }),
  events: (userId) => apiCall(`/events/${userId}`),
  timeline: (userId) => apiCall(`/timeline/${userId}`),
  audit: (userId) => apiCall(`/audit/${userId}`),
  replay: () => apiCall('/replay', { method: 'POST' }),
};
