// Use relative URLs so the app works regardless of hostname/port.
// During `npm run dev` (Vite proxy), requests go through the proxy.
// When served from the FastAPI backend directly, same-origin applies.
const API = '';

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res;
}

export async function getHealth() {
  return (await request('/api/health')).json();
}

export async function getStats() {
  return (await request('/api/stats')).json();
}

export async function createJob(urls, config = null) {
  return (await request('/api/jobs', {
    method: 'POST',
    body: JSON.stringify({ urls, config }),
  })).json();
}

export async function getJobs(limit = 20, offset = 0, status = null) {
  const params = new URLSearchParams({ limit, offset });
  if (status) params.set('status', status);
  return (await request(`/api/jobs?${params}`)).json();
}

export async function getJob(id) {
  return (await request(`/api/jobs/${id}`)).json();
}

export async function stopJob(id) {
  return (await request(`/api/jobs/${id}/stop`, { method: 'POST' })).json();
}

export async function deleteJob(id) {
  return (await request(`/api/jobs/${id}`, { method: 'DELETE' })).json();
}

export async function getResults(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') sp.set(k, v); });
  return (await request(`/api/results?${sp}`)).json();
}

export async function getResult(id) {
  return (await request(`/api/results/${id}`)).json();
}

export async function saveResultLabel(id, label, split) {
  return (await request(`/api/results/${id}/label`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ label, split }),
  })).json();
}

export async function saveSearchJudgment(id, query, relevance) {
  return (await request(`/api/results/${id}/search-judgment`, {
    method: 'POST', body: JSON.stringify({ query, relevance }),
  })).json();
}

export async function trainMlClassifier() {
  return (await request('/api/ml/train', { method: 'POST' })).json();
}

export async function getMlStatus() {
  return (await request('/api/ml/status')).json();
}

export async function getSearchEvaluation(query) {
  const sp = new URLSearchParams({ query });
  return (await request(`/api/ml/search-evaluation?${sp}`)).json();
}

export async function exportResults(fmt, params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') sp.set(k, v); });
  const res = await request(`/api/results/export/${fmt}?${sp}`);
  if (fmt === 'csv') return res.text();
  return res.json();
}

export async function getLogs(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') sp.set(k, v); });
  return (await request(`/api/logs?${sp}`)).json();
}

export async function getSettings() {
  return (await request('/api/settings')).json();
}

export async function updateSettings(data) {
  return (await request('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  })).json();
}

export function connectWS(onMessage) {
  const wsBase = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;
  const ws = new WebSocket(`${wsBase}/ws`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onclose = () => setTimeout(() => connectWS(onMessage), 3000);
  ws.onerror = () => ws.close();
  // Send keepalive
  const interval = setInterval(() => {
    if (ws.readyState === 1) ws.send('ping');
    else clearInterval(interval);
  }, 30000);
  return ws;
}
