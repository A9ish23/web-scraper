import { useState, useEffect, useCallback } from 'react';
import { getStats, createJob } from '../api';

export default function Dashboard({ wsEvents }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [urls, setUrls] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitMsg, setSubmitMsg] = useState(null);

  const fetchStats = useCallback(() => {
    setLoading(true);
    getStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  // Refresh stats when WS events arrive
  useEffect(() => {
    if (wsEvents.length > 0) fetchStats();
  }, [wsEvents.length, fetchStats]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const list = urls.split('\n').map(u => u.trim()).filter(Boolean);
    if (!list.length) return;
    setSubmitting(true);
    setSubmitMsg(null);
    try {
      const res = await createJob(list);
      setSubmitMsg({ type: 'ok', text: `Job ${res.job_id} started (${list.length} URLs)` });
      setUrls('');
      setTimeout(fetchStats, 1000);
    } catch (err) {
      setSubmitMsg({ type: 'err', text: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && !stats) return <div className="page"><div className="empty-state">Loading...</div></div>;
  if (error) return <div className="page"><div className="error-state">Error: {error}</div></div>;

  return (
    <div className="page">
      <h1 className="page-title">Dashboard</h1>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total jobs</div>
          <div className="stat-value">{stats?.total_jobs ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total results</div>
          <div className="stat-value">{stats?.total_results ?? 0}</div>
        </div>
        {stats?.jobs_by_status && Object.entries(stats.jobs_by_status).map(([k, v]) => (
          <div className="stat-card" key={k}>
            <div className="stat-label">{k}</div>
            <div className="stat-value">{v}</div>
          </div>
        ))}
      </div>

      {stats?.results_by_type && Object.keys(stats.results_by_type).length > 0 && (
        <div className="section">
          <h2 className="section-title">Results by type</h2>
          <div className="type-bar">
            {Object.entries(stats.results_by_type).map(([type, count]) => (
              <div key={type} className="type-segment" title={`${type}: ${count}`}>
                <span className="type-label">{type}</span>
                <span className="type-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="section">
        <h2 className="section-title">Quick scrape</h2>
        <form onSubmit={handleSubmit} className="scrape-form">
          <textarea
            value={urls}
            onChange={e => setUrls(e.target.value)}
            placeholder="Paste URLs here, one per line"
            rows={4}
            className="input textarea"
          />
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={submitting || !urls.trim()}>
              {submitting ? 'Starting...' : 'Start scrape'}
            </button>
            {submitMsg && (
              <span className={submitMsg.type === 'ok' ? 'msg-ok' : 'msg-err'}>
                {submitMsg.text}
              </span>
            )}
          </div>
        </form>
      </div>

      {stats?.recent_jobs?.length > 0 && (
        <div className="section">
          <h2 className="section-title">Recent jobs</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>URL</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_jobs.map(j => (
                <tr key={j.id}>
                  <td className="mono">{j.id}</td>
                  <td className="truncate" title={j.url}>{j.url}</td>
                  <td><span className={`badge badge-${j.status}`}>{j.status}</span></td>
                  <td className="mono">{j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
