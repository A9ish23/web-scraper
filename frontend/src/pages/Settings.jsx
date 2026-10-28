import { useState, useEffect } from 'react';
import { getSettings, updateSettings } from '../api';

const FIELDS = [
  { key: 'max_concurrent', label: 'Max concurrent requests', type: 'number', min: 1, max: 50 },
  { key: 'request_timeout', label: 'Request timeout (s)', type: 'number', min: 1, max: 120, step: 0.5 },
  { key: 'retry_attempts', label: 'Retry attempts', type: 'number', min: 0, max: 10 },
  { key: 'retry_backoff', label: 'Retry backoff (s)', type: 'number', min: 0.1, max: 30, step: 0.1 },
  { key: 'rate_limit_delay', label: 'Rate limit delay (s)', type: 'number', min: 0, max: 30, step: 0.1 },
  { key: 'respect_robots_txt', label: 'Respect robots.txt', type: 'checkbox' },
  { key: 'user_agent', label: 'User-Agent string', type: 'text' },
  { key: 'log_level', label: 'Log level', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'] },
];

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    getSettings()
      .then(s => { setSettings(s); setDraft(s); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key, value) => {
    setDraft(d => ({ ...d, [key]: value }));
    setSaved(false);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      // Only send changed fields
      const changed = {};
      for (const f of FIELDS) {
        if (draft[f.key] !== settings[f.key]) {
          changed[f.key] = draft[f.key];
        }
      }
      if (Object.keys(changed).length === 0) {
        setSaved(true);
        setSaving(false);
        return;
      }
      const updated = await updateSettings(changed);
      setSettings(updated);
      setDraft(updated);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = settings && FIELDS.some(f => draft[f.key] !== settings[f.key]);

  if (loading) return <div className="page"><div className="empty-state">Loading...</div></div>;

  return (
    <div className="page">
      <h1 className="page-title">Settings</h1>

      {error && <div className="error-state">{error}</div>}

      <form onSubmit={handleSave} className="settings-form">
        {FIELDS.map(f => (
          <div className="field" key={f.key}>
            <label className="field-label" htmlFor={f.key}>{f.label}</label>
            {f.type === 'checkbox' ? (
              <input
                id={f.key}
                type="checkbox"
                checked={!!draft[f.key]}
                onChange={e => handleChange(f.key, e.target.checked)}
                className="checkbox"
              />
            ) : f.type === 'select' ? (
              <select
                id={f.key}
                className="input select"
                value={draft[f.key] || ''}
                onChange={e => handleChange(f.key, e.target.value)}
              >
                {f.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input
                id={f.key}
                type={f.type}
                className="input"
                value={draft[f.key] ?? ''}
                onChange={e => handleChange(f.key, f.type === 'number' ? Number(e.target.value) : e.target.value)}
                min={f.min}
                max={f.max}
                step={f.step}
              />
            )}
          </div>
        ))}

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving || !hasChanges}>
            {saving ? 'Saving...' : 'Save settings'}
          </button>
          {saved && <span className="msg-ok">Settings saved</span>}
          {hasChanges && <button type="button" className="btn btn-ghost" onClick={() => setDraft({...settings})}>Reset</button>}
        </div>
      </form>

      <div className="section" style={{ marginTop: 32 }}>
        <h2 className="section-title">Current config (read-only)</h2>
        <pre className="code-block">{JSON.stringify(settings, null, 2)}</pre>
      </div>
    </div>
  );
}
