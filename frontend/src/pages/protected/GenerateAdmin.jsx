import { useState, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';

const AUTH_REDIRECTING = '__AUTH_REDIRECTING__';
const AUTH_SCOPE = 'openid profile email';

function isArticleAuthzError(err) {
  const message = String(err?.message || '');
  return message.includes('403') && message.includes('article');
}

export default function GenerateAdmin() {
  const { getAccessTokenSilently } = useAuth0();
  const navigate = useNavigate();
  const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
  const [stems, setStems] = useState([]);
  const [selected, setSelected] = useState('');
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [editingId, setEditingId] = useState('');
  const [editingStatus, setEditingStatus] = useState('draft');
  const [editForm, setEditForm] = useState({ title: '', summary: '', content: '', tags: '' });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const filteredHistory = history.filter((article) => {
    if (statusFilter === 'all') return true;
    return (article.status || 'draft') === statusFilter;
  });

  useEffect(() => {
    try {
      const saved = localStorage.getItem('techsignals-article-status-filter');
      if (saved === 'all' || saved === 'draft' || saved === 'published') {
        setStatusFilter(saved);
      }
    } catch {
      // ignore localStorage issues
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('techsignals-article-status-filter', statusFilter);
    } catch {
      // ignore localStorage issues
    }
  }, [statusFilter]);

  async function getApiToken(forceRefresh = false) {
    try {
      if (audience) {
        return await getAccessTokenSilently({
          cacheMode: forceRefresh ? 'off' : 'on',
          authorizationParams: { audience, scope: AUTH_SCOPE },
        });
      }
      return await getAccessTokenSilently({
        cacheMode: forceRefresh ? 'off' : 'on',
        authorizationParams: { scope: AUTH_SCOPE },
      });
    } catch (err) {
      if (err?.error === 'consent_required' || err?.error === 'login_required') {
        navigate(`/generate-auth?returnTo=${encodeURIComponent('/generate')}`);
        throw new Error(AUTH_REDIRECTING);
      }
      throw err;
    }
  }

  async function refreshAdminArticles(token) {
    const articleData = await api.adminArticles(token);
    setHistory(articleData);
  }

  async function loadAdminArticlesWithRetry(initialToken) {
    setHistoryLoading(true);
    try {
      await refreshAdminArticles(initialToken);
    } catch (err) {
      if (!isArticleAuthzError(err)) throw err;
      const freshToken = await getApiToken(true);
      await refreshAdminArticles(freshToken);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    async function loadData() {
      try {
        let token = await getApiToken();
        let stemData;
        try {
          stemData = await api.articleStems(token);
        } catch (stemErr) {
          if (!isArticleAuthzError(stemErr)) throw stemErr;
          token = await getApiToken(true);
          stemData = await api.articleStems(token);
        }
        setStems(stemData);
        await loadAdminArticlesWithRetry(token);
      } catch (err) {
        if (err?.message === AUTH_REDIRECTING) return;
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
      await loadAdminArticlesWithRetry(token);
    } catch (err) {
      if (err?.message === AUTH_REDIRECTING) return;
      setError(err.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  function startEdit(article) {
    setEditingId(article.id);
    setEditingStatus(article.status || 'draft');
    setEditForm({
      title: article.title || '',
      summary: article.summary || '',
      content: article.content || '',
      tags: (article.tags || []).join(', '),
    });
  }

  function closeEditModal() {
    setEditingId('');
    setEditingStatus('draft');
    setEditForm({ title: '', summary: '', content: '', tags: '' });
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
        status: editingStatus,
        tags: editForm.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      };

      await api.updateArticle(editingId, payload, token);
      await loadAdminArticlesWithRetry(token);
      closeEditModal();
    } catch (err) {
      if (err?.message === AUTH_REDIRECTING) return;
      setError(err.message || 'Failed to save article');
    } finally {
      setSaving(false);
    }
  }

  async function handleSetStatus(articleId, status) {
    setError(null);
    try {
      const token = await getApiToken();
      await api.setArticleStatus(articleId, status, token);
      await loadAdminArticlesWithRetry(token);
      if (editingId && editingId === articleId) {
        setEditingStatus(status);
      }
    } catch (err) {
      if (err?.message === AUTH_REDIRECTING) return;
      setError(err.message || 'Failed to change publication status');
    }
  }

  function openDeleteModal(article) {
    setDeleteTarget(article);
  }

  function closeDeleteModal() {
    if (deleting) return;
    setDeleteTarget(null);
  }

  async function confirmDeleteArticle() {
    if (!deleteTarget?.id) return;
    setError(null);
    setDeleting(true);
    const articleId = deleteTarget.id;
    const previousHistory = history;
    setHistory((prev) => prev.filter((item) => item.id !== articleId));

    if (editingId === articleId) {
      closeEditModal();
    }

    try {
      const token = await getApiToken();
      await api.deleteArticle(articleId, token);
      setDeleteTarget(null);
    } catch (err) {
      if (err?.message === AUTH_REDIRECTING) return;
      setHistory(previousHistory);
      setError(err.message || 'Failed to delete article');
    } finally {
      setDeleting(false);
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
              <p className="gen-success-meta">Saved as draft.</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Recent Articles ── */}
      <section className="gen-history">
        <div className="gen-history-header-row">
          <h2 className="section-title">Generated Articles ({filteredHistory.length})</h2>
          <div className="gen-filter-group" role="tablist" aria-label="Filter articles by status">
            <button
              className={`gen-filter-btn${statusFilter === 'all' ? ' active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              All
            </button>
            <button
              className={`gen-filter-btn${statusFilter === 'draft' ? ' active' : ''}`}
              onClick={() => setStatusFilter('draft')}
            >
              Draft
            </button>
            <button
              className={`gen-filter-btn${statusFilter === 'published' ? ' active' : ''}`}
              onClick={() => setStatusFilter('published')}
            >
              Published
            </button>
          </div>
        </div>
        {historyLoading && (
          <div className="gen-history-loading" role="status" aria-live="polite">
            <div className="gen-loading-bar" />
            <span>Loading generated articles…</span>
          </div>
        )}
        {!historyLoading && filteredHistory.length === 0 ? (
          <p className="gen-history-empty">No articles generated yet.</p>
        ) : (
          <div className="gen-history-list" aria-busy={historyLoading ? 'true' : 'false'}>
            {filteredHistory.map((a) => (
              <div key={a.id} className="gen-history-item">
                <div className="gen-history-title-row">
                  <div className="gen-history-title">{a.title}</div>
                  <span className={`gen-status-badge ${a.status === 'published' ? 'published' : 'draft'}`}>
                    {a.status === 'published' ? 'Published' : 'Draft'}
                  </span>
                </div>
                <div className="gen-history-meta">
                  <span>{new Date(a.generatedAt).toLocaleString()}</span>
                  {a.tags?.length > 0 && (
                    <span className="gen-history-tags">
                      {a.tags.join(', ')}
                    </span>
                  )}
                </div>
                <p className="gen-history-summary">{a.summary}</p>
                <div className="gen-history-actions">
                  <button
                    className="btn-secondary gen-edit-btn"
                    onClick={() => startEdit(a)}
                  >
                    Edit article
                  </button>
                  {a.status === 'published' ? (
                    <button
                      className="btn-secondary gen-edit-btn"
                      onClick={() => handleSetStatus(a.id, 'draft')}
                    >
                      Move to draft
                    </button>
                  ) : (
                    <button
                      className="btn-primary gen-edit-btn"
                      onClick={() => handleSetStatus(a.id, 'published')}
                    >
                      Publish
                    </button>
                  )}
                  <button
                    className="btn-secondary gen-edit-btn gen-delete-btn"
                    onClick={() => openDeleteModal(a)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {deleteTarget && (
        <div className="gen-modal-overlay" onClick={closeDeleteModal}>
          <section className="gen-editor gen-modal gen-delete-modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="section-title">Delete Article</h2>
            <p className="page-subtitle">
              This will permanently delete <strong>{deleteTarget.title}</strong>.
            </p>
            <p className="page-subtitle">This action cannot be undone.</p>

            <div className="gen-editor-actions">
              <button className="btn-secondary" onClick={closeDeleteModal} disabled={deleting}>
                Cancel
              </button>
              <button className="btn-primary gen-delete-confirm" onClick={confirmDeleteArticle} disabled={deleting}>
                {deleting ? 'Deleting…' : 'Confirm Delete'}
              </button>
            </div>
          </section>
        </div>
      )}

      {editingId && (
        <div className="gen-modal-overlay" onClick={closeEditModal}>
          <section className="gen-editor gen-modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="section-title">Edit Article</h2>

            <label className="gen-label">
              Status
              <select
                className="gen-select"
                value={editingStatus}
                onChange={(e) => setEditingStatus(e.target.value)}
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
            </label>

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
                placeholder="# Heading\n\nWrite article content in Markdown..."
              />
            </label>

            <div className="gen-editor-actions">
              <button className="btn-primary" onClick={handleSaveEdit} disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button className="btn-secondary" onClick={closeEditModal} disabled={saving}>
                Cancel
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
