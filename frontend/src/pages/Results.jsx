import { useState, useEffect } from 'react';
import { getResults, exportResults, saveResultLabel, saveSearchJudgment, trainMlClassifier, getMlStatus, getSearchEvaluation } from '../api';
import { useFetch } from '../hooks/useFetch';

export default function Results() {
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [pageType, setPageType] = useState('');
  const [semantic, setSemantic] = useState(false);
  const [sortBy, setSortBy] = useState('scraped_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [mlStatus, setMlStatus] = useState(null);
  const [training, setTraining] = useState(false);
  const [classifierEvaluation, setClassifierEvaluation] = useState(null);
  const [mlMessage, setMlMessage] = useState('');
  const [mlError, setMlError] = useState(false);
  const [searchEvaluation, setSearchEvaluation] = useState(null);
  const [evaluatingSearch, setEvaluatingSearch] = useState(false);
  const limit = 20;

  const params = { limit, offset: page * limit, search, sort_by: sortBy, sort_order: sortOrder, page_type: pageType || undefined, semantic: semantic || undefined };
  const { data, loading, error } = useFetch(
    () => getResults(params),
    [search, pageType, sortBy, sortOrder, page, semantic]
  );

  useEffect(() => { getMlStatus().then(setMlStatus).catch(() => {}); }, []);

  const results = data?.results || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  const handleSearch = (e) => {
    e.preventDefault();
    setSearch(searchInput);
    setSearchEvaluation(null);
    setPage(0);
  };

  const handleSort = (col) => {
    if (sortBy === col) setSortOrder(o => o === 'asc' ? 'desc' : 'asc');
    else { setSortBy(col); setSortOrder('asc'); }
    setPage(0);
  };

  const handleTrain = async () => {
    const trainCounts = mlStatus?.label_counts?.train || {};
    const trainExampleCount = Object.values(trainCounts).reduce((sum, count) => sum + count, 0);
    const categoryCount = Object.keys(trainCounts).length;
    if (trainExampleCount < 6 || categoryCount < 2) {
      setMlError(true);
      setMlMessage(`Training needs at least 6 training labels from 2 categories. You currently have ${trainExampleCount} label${trainExampleCount === 1 ? '' : 's'} across ${categoryCount} categor${categoryCount === 1 ? 'y' : 'ies'}. Expand results and save correct labels first.`);
      return;
    }
    setTraining(true);
    setMlError(false);
    try {
      const report = await trainMlClassifier();
      setClassifierEvaluation(report.evaluation || null);
      setMlMessage(report.message + (report.evaluation ? ` Evaluation set: ${(report.evaluation.accuracy * 100).toFixed(1)}% accuracy, ${(report.evaluation.macro_f1 * 100).toFixed(1)}% macro F1 (${report.evaluation.evaluation_size} examples).` : ''));
      setMlStatus(report.model);
      getMlStatus().then(setMlStatus).catch(() => {});
    } catch (err) { setMlError(true); setMlMessage(`Training failed: ${friendlyApiError(err.message)}`); }
    finally { setTraining(false); }
  };

  const handleLabel = async (id, label, split) => {
    try {
      await saveResultLabel(id, label, split);
      setMlError(false);
      setMlMessage(`Label saved to the ${split} set.`);
      getMlStatus().then(setMlStatus).catch(() => {});
    } catch (err) { setMlError(true); setMlMessage(`Could not save label: ${friendlyApiError(err.message)}`); }
  };

  const handleSearchJudgment = async (id, query, relevance) => {
    try {
      await saveSearchJudgment(id, query, relevance);
      setMlError(false);
      setMlMessage('Search relevance judgment saved for this query.');
    } catch (err) { setMlError(true); setMlMessage(`Could not save rating: ${friendlyApiError(err.message)}`); }
  };

  const handleEvaluateSearch = async () => {
    setEvaluatingSearch(true);
    try { setSearchEvaluation(await getSearchEvaluation(search)); }
    catch (err) { setSearchEvaluation({ measured: false, message: err.message }); }
    finally { setEvaluatingSearch(false); }
  };

  const handleExport = async (fmt) => {
    setExporting(true);
    try {
      const data = await exportResults(fmt, { search, page_type: pageType });
      if (fmt === 'csv') {
        const blob = new Blob([data], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'results.csv'; a.click();
        URL.revokeObjectURL(url);
      } else {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'results.json'; a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      alert('Export failed: ' + err.message);
    } finally {
      setExporting(false);
    }
  };

  const sortIcon = (col) => {
    if (sortBy !== col) return '';
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Results</h1>
        <div className="header-actions">
          <button className="btn btn-ghost" onClick={handleTrain} disabled={training}>{training ? 'Training…' : `Train classifier (${mlStatus?.label_counts?.train ? Object.values(mlStatus.label_counts.train).reduce((sum, count) => sum + count, 0) : 0} train)`}</button>
          <button className="btn btn-ghost" onClick={() => handleExport('csv')} disabled={exporting}>Export CSV</button>
          <button className="btn btn-ghost" onClick={() => handleExport('json')} disabled={exporting}>Export JSON</button>
        </div>
      </div>
      <p className="muted">Exports follow the current search and type filters. They include cleaned page text, useful links and images, and a short field guide in JSON.</p>
      <p className="muted">{mlStatus?.trained ? 'A text classifier is active.' : 'Page categories currently use transparent rules.'} Training labels and held-out evaluation labels are kept separate. {mlStatus?.label_counts?.evaluation ? `${Object.values(mlStatus.label_counts.evaluation).reduce((sum, count) => sum + count, 0)} evaluation examples saved.` : 'Add evaluation examples to measure generalization.'}</p>
      {mlMessage && <div className={`training-notice${mlError ? ' error' : ''}`} role="status" aria-live="polite">{mlMessage}</div>}
      {classifierEvaluation && <div className="detail-section">
        <h3>Held-out classification results</h3>
        <p>Accuracy: {(classifierEvaluation.accuracy * 100).toFixed(1)}% · Macro F1: {(classifierEvaluation.macro_f1 * 100).toFixed(1)}% · {classifierEvaluation.evaluation_size} labeled pages</p>
        <table className="data-table"><thead><tr><th>Category</th><th>Precision</th><th>Recall</th><th>F1</th><th>Examples</th></tr></thead>
          <tbody>{classifierEvaluation.labels.map(label => {
            const row = classifierEvaluation.report[label] || {};
            return <tr key={label}><td>{label}</td><td>{((row.precision || 0) * 100).toFixed(1)}%</td><td>{((row.recall || 0) * 100).toFixed(1)}%</td><td>{((row['f1-score'] || 0) * 100).toFixed(1)}%</td><td>{row.support || 0}</td></tr>;
          })}</tbody>
        </table>
      </div>}

      <div className="toolbar">
        <form onSubmit={handleSearch} className="search-form">
          <input
            className="input"
            type="text"
            placeholder="Search title, URL, description..."
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
          />
          <label className="muted"><input type="checkbox" checked={semantic} onChange={e => { setSemantic(e.target.checked); setSearchEvaluation(null); setPage(0); }} /> Meaning-based search</label>
          <button type="submit" className="btn btn-ghost">Search</button>
          {semantic && search && <button type="button" className="btn btn-ghost" onClick={handleEvaluateSearch} disabled={evaluatingSearch}>{evaluatingSearch ? 'Evaluating…' : 'Evaluate search'}</button>}
          {search && <button type="button" className="btn btn-ghost" onClick={() => { setSearch(''); setSearchInput(''); }}>Clear</button>}
        </form>
        <select className="input select" value={pageType} onChange={e => { setPageType(e.target.value); setPage(0); }}>
          <option value="">All types</option>
          <option value="article">Article</option>
          <option value="product">Product</option>
          <option value="job">Job</option>
          <option value="profile">Profile</option>
          <option value="forum">Forum</option>
          <option value="search">Search</option>
          <option value="other">Other</option>
        </select>
        <span className="result-count">{total} result{total !== 1 ? 's' : ''}</span>
      </div>
      {semantic && <p className="muted">Meaning-based search compares the intent of your query with page text. The first search may take longer while the embedding model loads.</p>}
      {searchEvaluation && <p className="muted">{searchEvaluation.measured ? `Search evaluation for “${searchEvaluation.query}” (${searchEvaluation.judged_results} judged): Precision@10 ${searchEvaluation.precision_at_k}, Recall@10 ${searchEvaluation.recall_at_k ?? '—'}, MRR@10 ${searchEvaluation.mrr_at_k}, nDCG@10 ${searchEvaluation.ndcg_at_k}. Grades 2–3 count as relevant.` : searchEvaluation.message}</p>}

      {error && <div className="error-state">{error}</div>}

      {loading && !results.length ? (
        <div className="empty-state">Loading...</div>
      ) : results.length === 0 ? (
        <div className="empty-state">
          {search || pageType ? 'No results match your filters.' : 'No results yet. Start a scrape job first.'}
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('id')}>ID{sortIcon('id')}</th>
              <th className="sortable" onClick={() => handleSort('title')}>Title{sortIcon('title')}</th>
              <th className="sortable" onClick={() => handleSort('url')}>URL{sortIcon('url')}</th>
              <th className="sortable" onClick={() => handleSort('page_type')}>Type{sortIcon('page_type')}</th>
              {semantic && search && <th>Similarity</th>}
              <th className="sortable" onClick={() => handleSort('scraped_at')}>Scraped{sortIcon('scraped_at')}</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {results.map(r => (
              <>
                <tr key={r.id} className={expanded === r.id ? 'row-expanded' : ''}>
                  <td className="mono">{r.id}</td>
                  <td className="truncate" title={r.title}>{r.title || '—'}</td>
                  <td className="truncate mono" title={r.url}>{r.url}</td>
                  <td><span className={`badge badge-type-${r.page_type}`}>{r.page_type}</span></td>
                  {semantic && search && <td>{Math.round((r.similarity || 0) * 100)}%</td>}
                  <td className="mono">{r.scraped_at ? new Date(r.scraped_at).toLocaleString() : '—'}</td>
                  <td>
                    <button className="btn btn-sm btn-ghost" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
                      {expanded === r.id ? '−' : '+'}
                    </button>
                  </td>
                </tr>
                {expanded === r.id && (
                  <tr key={`${r.id}-detail`} className="detail-row">
                    <td colSpan={semantic && search ? 7 : 6}>
                      <ResultDetail result={r} onLabel={handleLabel} onSearchJudgment={handleSearchJudgment} semantic={semantic} query={search} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span className="page-info">Page {page + 1} of {totalPages}</span>
          <button className="btn btn-ghost" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}

function friendlyApiError(message) {
  if (message === 'Method Not Allowed') {
    return 'The backend is still running an older version. Restart the backend server, refresh this page, and try again.';
  }
  return message;
}

function ResultDetail({ result, onLabel, onSearchJudgment, semantic, query }) {
  const [labelSplit, setLabelSplit] = useState('train');
  let data = {};
  try { data = JSON.parse(result.data || '{}'); } catch {}
  const paragraphs = data.paragraphs || [];
  const textLength = paragraphs.reduce((total, paragraph) => total + paragraph.length, 0);
  const nlp = data.nlp || {};
  const classification = data.classification || {};
  let host = '—';
  try { host = new URL(result.url).hostname; } catch {}

  return (
    <div className="result-detail">
      <div className="detail-grid">
        <div className="detail-section">
          <h3>Metadata</h3>
          <dl>
            <dt>Title</dt><dd>{data.title || '—'}</dd>
            <dt>Description</dt><dd>{data.description || '—'}</dd>
            <dt>Website</dt><dd>{host}</dd>
            {data.site_name && <><dt>Site name</dt><dd>{data.site_name}</dd></>}
            {data.author && <><dt>Author</dt><dd>{data.author}</dd></>}
            {data.published_at && <><dt>Published</dt><dd>{data.published_at}</dd></>}
            {data.language && <><dt>Language</dt><dd>{data.language}</dd></>}
            {data.canonical_url && <><dt>Canonical URL</dt><dd><a href={data.canonical_url} target="_blank" rel="noreferrer">{data.canonical_url}</a></dd></>}
            <dt>Page category</dt><dd><span className={`badge badge-type-${result.page_type}`}>{result.page_type || 'unknown'}</span> <span className="muted">(estimated from page signals)</span></dd>
            <dt>Classification confidence</dt><dd>{classification.confidence != null ? `${Math.round(classification.confidence * 100)}%` : '—'} <span className="muted">{classification.method || ''}</span></dd>
            {classification.evidence?.length > 0 && <><dt>Signals</dt><dd>{classification.evidence.join(', ')}</dd></>}
            <dt>Scraped</dt><dd>{result.scraped_at ? new Date(result.scraped_at).toLocaleString() : '—'}</dd>
            <dt>Content collected</dt><dd>{textLength.toLocaleString()} characters of paragraph text</dd>
            <dt>Job ID</dt><dd className="mono">{result.job_id || '—'}</dd>
            <dt>Label set</dt><dd><select className="input select" value={labelSplit} onChange={e => setLabelSplit(e.target.value)}><option value="train">Training</option><option value="evaluation">Held-out evaluation</option></select></dd>
            <dt>Correct label</dt><dd><select className="input select" defaultValue="" onChange={e => e.target.value && onLabel(result.id, e.target.value, labelSplit)}><option value="">Choose category…</option><option value="article">Article</option><option value="product">Product</option><option value="job">Job</option><option value="profile">Profile</option><option value="forum">Forum</option><option value="search">Search</option><option value="other">Other</option></select> <span className="muted">Held-out examples are never used to fit the classifier.</span></dd>
          </dl>
        </div>
        <div className="detail-section">
          <h3>Content summary</h3>
          <dl>
            <dt>Headings</dt><dd>{data.headings?.length || 0} <span className="muted">section titles</span></dd>
            <dt>Paragraphs</dt><dd>{paragraphs.length} <span className="muted">unique text blocks</span></dd>
            <dt>Links</dt><dd>{data.links?.length || 0} <span className="muted">meaningful page links</span></dd>
            <dt>Images</dt><dd>{data.images?.length || 0} <span className="muted">with available alt text</span></dd>
          </dl>
        </div>
      </div>
      {data.headings?.length > 0 && (
        <div className="detail-section">
          <h3>Headings</h3>
          <ul className="heading-list">
            {data.headings.slice(0, 15).map((h, i) => (
              <li key={i}><span className="mono tag-label">{h.tag}</span> {h.text}</li>
            ))}
            {data.headings.length > 15 && <li className="muted">...and {data.headings.length - 15} more</li>}
          </ul>
        </div>
      )}
      {paragraphs.length > 0 && (
        <div className="detail-section">
          <h3>Text preview</h3>
          <ul className="heading-list">
            {paragraphs.slice(0, 3).map((paragraph, i) => <li key={i}>{paragraph}</li>)}
            {paragraphs.length > 3 && <li className="muted">Showing 3 of {paragraphs.length} paragraphs</li>}
          </ul>
        </div>
      )}
      {(nlp.summary || nlp.topics?.length || nlp.entities?.length || nlp.sentiment) && (
        <div className="detail-section">
          <h3>Language analysis <span className="muted">(automated estimates)</span></h3>
          {nlp.summary && <p><strong>Summary:</strong> {nlp.summary}</p>}
          {nlp.topics?.length > 0 && <p><strong>Topics:</strong> {nlp.topics.join(', ')}</p>}
          {nlp.sentiment && <p><strong>Sentiment:</strong> {nlp.sentiment.label} ({nlp.sentiment.score}, {nlp.sentiment.method})</p>}
          {nlp.entities?.length > 0 && <p><strong>Entity candidates:</strong> {nlp.entities.map(entity => `${entity.text} (${entity.type.replaceAll('_', ' ')})`).join(', ')}</p>}
          <p className="muted">{nlp.analysis_note}</p>
        </div>
      )}
      {semantic && query && <div className="detail-section">
        <h3>Search relevance judgment</h3>
        <label>How useful is this page for “{query}”? <select className="input select" defaultValue="" onChange={e => e.target.value !== '' && onSearchJudgment(result.id, query, Number(e.target.value))}>
          <option value="">Rate this result…</option><option value="0">0 · Not relevant</option><option value="1">1 · Slightly relevant</option><option value="2">2 · Relevant</option><option value="3">3 · Highly relevant</option>
        </select></label>
      </div>}
    </div>
  );
}
