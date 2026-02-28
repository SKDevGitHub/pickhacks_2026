import { useState, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { api } from '../../api';

export default function GenerateAdmin() {
  const { getAccessTokenSilently } = useAuth0();
  const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
  const [stems, setStems] = useState([]);
  const [selected, setSelected] = useState('');
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [editingId, setEditingId] = useState('');
  const [editForm, setEditForm] = useState({ title: '', summary: '', content: '', tags: '' });
  const [saving, setSaving] = useState(false);

  async function getApiToken() {
    if (audience) {
      return getAccessTokenSilently({ authorizationParams: { audience } });
    }
    return getAccessTokenSilently();
  }

  useEffect(() => {
    async function loadData() {
      try {
        const token = await getApiToken();
        const [stemData, articleData] = await Promise.all([
          api.articleStems(token),
          api.articles(),
        ]);
        setStems(stemData);
        setHistory(articleData);
      } catch (err) {
        setError(err.message || 'Unable to load generator data');
      }
    }

    loadData();
  }, [getAccessTokenSilently, audience]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const token = await getApiToken();
      const article = await api.generateArticle(selected || null, token);
      setResult(article);
      // refresh history
      const updated = await api.articles();
      setHistory(updated);
    } catch (err) {
      setError(err.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  function startEdit(article) {
    setEditingId(article.id);
    setEditForm({
      title: article.title || '',
      summary: article.summary || '',
      content: article.content || '',
      tags: (article.tags || []).join(', '),
    });
  }

  async function handleSaveEdit() {
    if (!editingId) return;

    setSaving(true);
    setError(null);
    try {
      const token = await getApiToken();
      const payload = {
        title: editForm.title,
        summary: editForm.summary,
        content: editForm.content,
        tags: editForm.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      };

      await api.updateArticle(editingId, payload, token);
      const updated = await api.articles();
      setHistory(updated);
      setEditingId('');
    } catch (err) {
      setError(err.message || 'Failed to save article');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-shell">
      <div className="page-header">
        <h1 className="page-title">Article Generator</h1>
        <p className="page-subtitle">
          Use Gemini AI to generate news articles about emerging technologies
        </p>
      </div>

      {/* ── Generator Controls ── */}
      <div className="gen-panel">
        <div className="gen-controls">
          <label className="gen-label">
            Technology
            <select
              className="gen-select"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={generating}
            >
              <option value="">General Roundup (all technologies)</option>
              {stems.map((s) => (
                <option key={s.stem} value={s.stem}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>

          <button
            className={`btn-primary gen-btn${generating ? ' gen-btn--loading' : ''}`}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? (
              <>
                <span className="gen-spinner" />
                Generating…
              </>
            ) : (
              'Generate Article'
            )}
          </button>
        </div>

        {/* ── Status ── */}
        {error && (
          <div className="gen-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {result && (
          <div className="gen-success">
            <div className="gen-success-icon">✓</div>
            <div>
              <strong>Article created:</strong> {result.title}
              <p className="gen-success-meta">{result.summary}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Recent Articles ── */}
      <section className="gen-history">
        <h2 className="section-title">Generated Articles ({history.length})</h2>
        {history.length === 0 ? (
          <p className="gen-history-empty">No articles generated yet.</p>
        ) : (
          <div className="gen-history-list">
            {history.map((a) => (
              <div key={a.id} className="gen-history-item">
                <div className="gen-history-title">{a.title}</div>
                <div className="gen-history-meta">
                  <span>{new Date(a.generatedAt).toLocaleString()}</span>
                  {a.tags?.length > 0 && (
                    <span className="gen-history-tags">
                      {a.tags.join(', ')}
                    </span>
                  )}
                </div>
                <p className="gen-history-summary">{a.summary}</p>
                <button
                  className="btn-secondary gen-edit-btn"
                  onClick={() => startEdit(a)}
                >
                  Edit article
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {editingId && (
        <section className="gen-editor">
          <h2 className="section-title">Edit Article</h2>

          <label className="gen-label">
            Title
            <input
              className="gen-input"
              value={editForm.title}
              onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
            />
          </label>

          <label className="gen-label">
            Summary
            <textarea
              className="gen-textarea gen-textarea--summary"
              value={editForm.summary}
              onChange={(e) => setEditForm((prev) => ({ ...prev, summary: e.target.value }))}
            />
          </label>

          <label className="gen-label">
            Tags (comma-separated)
            <input
              className="gen-input"
              value={editForm.tags}
              onChange={(e) => setEditForm((prev) => ({ ...prev, tags: e.target.value }))}
            />
          </label>

          <label className="gen-label">
            Content (Markdown)
            <textarea
              className="gen-textarea gen-textarea--content"
              value={editForm.content}
              onChange={(e) => setEditForm((prev) => ({ ...prev, content: e.target.value }))}
            />
          </label>

          <div className="gen-editor-actions">
            <button className="btn-primary" onClick={handleSaveEdit} disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            <button className="btn-secondary" onClick={() => setEditingId('')} disabled={saving}>
              Cancel
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
