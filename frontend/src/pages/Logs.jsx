import { useState, useCallback, useEffect } from 'react';
import { getLogs } from '../api';

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [jobFilter, setJobFilter] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const [page, setPage] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const limit = 50;

  const fetchLogs = useCallback(() => {
    setLoading(true);
    getLogs({ job_id: jobFilter || undefined, level: levelFilter || undefined, limit, offset: page * limit })
      .then(d => { setLogs(d.logs); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [jobFilter, levelFilter, page]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchLogs, 3000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchLogs]);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Logs</h1>
        <label className="toggle-label">
          <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
          Auto-refresh
        </label>
      </div>

      <div className="toolbar">
        <input
          className="input"
          type="text"
          placeholder="Filter by job ID"
          value={jobFilter}
          onChange={e => { setJobFilter(e.target.value); setPage(0); }}
        />
        <select className="input select" value={levelFilter} onChange={e => { setLevelFilter(e.target.value); setPage(0); }}>
          <option value="">All levels</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
        <button className="btn btn-ghost" onClick={fetchLogs} title="Refresh">↻</button>
      </div>

      {error && <div className="error-state">{error}</div>}

      {loading && !logs.length ? (
        <div className="empty-state">Loading...</div>
      ) : logs.length === 0 ? (
        <div className="empty-state">No logs found.</div>
      ) : (
        <div className="log-list">
          {logs.map(l => (
            <div key={l.id} className={`log-entry log-${l.level?.toLowerCase()}`}>
              <span className="log-time mono">{l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ''}</span>
              <span className={`log-level badge badge-${l.level?.toLowerCase()}`}>{l.level}</span>
              <span className="log-job mono">{l.job_id}</span>
              <span className="log-msg">{l.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="pagination">
        <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
        <span className="page-info">Page {page + 1}</span>
        <button className="btn btn-ghost" disabled={logs.length < limit} onClick={() => setPage(p => p + 1)}>Next →</button>
      </div>
    </div>
  );
}
