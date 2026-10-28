import { useState, useEffect, useCallback } from 'react';
import { getJobs, createJob, stopJob, deleteJob } from '../api';

export default function Jobs({ wsEvents }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [urls, setUrls] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const limit = 20;

  const fetchJobs = useCallback(() => {
    setLoading(true);
    getJobs(limit, page * limit, filter || null)
      .then(d => { setJobs(d.jobs); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, filter]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);
  useEffect(() => {
    if (wsEvents.length > 0) fetchJobs();
  }, [wsEvents.length]);

  const handleCreate = async (e) => {
    e.preventDefault();
    const list = urls.split('\n').map(u => u.trim()).filter(Boolean);
    if (!list.length) return;
    setSubmitting(true);
    try {
      await createJob(list);
      setUrls('');
      setShowForm(false);
      setTimeout(fetchJobs, 500);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async (id) => {
    try { await stopJob(id); setTimeout(fetchJobs, 500); }
    catch (err) { setError(err.message); }
  };

  const handleDelete = async (id) => {
    if (!confirm(`Delete job ${id} and all its results?`)) return;
    try { await deleteJob(id); fetchJobs(); }
    catch (err) { setError(err.message); }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Jobs</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ New job'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="scrape-form section">
          <textarea
            value={urls}
            onChange={e => setUrls(e.target.value)}
            placeholder="URLs to scrape, one per line"
            rows={5}
            className="input textarea"
            autoFocus
          />
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={submitting || !urls.trim()}>
              {submitting ? 'Starting...' : 'Start scrape'}
            </button>
          </div>
        </form>
      )}

      {error && <div className="error-state">{error}</div>}

      <div className="toolbar">
        <select className="input select" value={filter} onChange={e => { setFilter(e.target.value); setPage(0); }}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <button className="btn btn-ghost" onClick={fetchJobs} title="Refresh">↻</button>
      </div>

      {loading && !jobs.length ? (
        <div className="empty-state">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="empty-state">No jobs found. Create one to get started.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>URL</th>
              <th>Status</th>
              <th>Created</th>
              <th>Completed</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(j => (
              <tr key={j.id}>
                <td className="mono">{j.id}</td>
                <td className="truncate" title={j.url}>{j.url}</td>
                <td><span className={`badge badge-${j.status}`}>{j.status}</span></td>
                <td className="mono">{j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
                <td className="mono">{j.completed_at ? new Date(j.completed_at).toLocaleString() : '—'}</td>
                <td className="actions">
                  {j.status === 'running' && (
                    <button className="btn btn-sm btn-ghost" onClick={() => handleStop(j.id)} title="Stop">■</button>
                  )}
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(j.id)} title="Delete">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="pagination">
        <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
        <span className="page-info">Page {page + 1}</span>
        <button className="btn btn-ghost" disabled={jobs.length < limit} onClick={() => setPage(p => p + 1)}>Next →</button>
      </div>
    </div>
  );
}
