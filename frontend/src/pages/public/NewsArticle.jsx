import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import DOMPurify from 'dompurify';
import { api } from '../../api';

export default function NewsArticle() {
  const { articleId } = useParams();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [audioUrl, setAudioUrl] = useState('');
  const [audioLoading, setAudioLoading] = useState(true);
  const [audioUnavailable, setAudioUnavailable] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError('');
    api.article(articleId)
      .then(setArticle)
      .catch((err) => setError(err.message || 'Failed to load article'))
      .finally(() => setLoading(false));
  }, [articleId]);

  /* Auto-fetch audio for published articles */
  useEffect(() => {
    if (!articleId) return;
    let cancelled = false;

    (async () => {
      setAudioLoading(true);
      setAudioUnavailable(false);
      try {
        const res = await fetch(`/api/articles/${articleId}/audio`);
        if (!res.ok) throw new Error('unavailable');
        const blob = await res.blob();
        if (cancelled) return;
        setAudioUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
      } catch {
        if (!cancelled) setAudioUnavailable(true);
      } finally {
        if (!cancelled) setAudioLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [articleId]);

  useEffect(() => {
    return () => { if (audioUrl) URL.revokeObjectURL(audioUrl); };
  }, [audioUrl]);

  if (loading) {
    return (
      <div className="page-shell">
        <div className="page-header">
          <h1 className="page-title">News</h1>
          <p className="page-subtitle">Loading article…</p>
        </div>
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="page-shell">
        <div className="page-header">
          <h1 className="page-title">News</h1>
          <p className="page-subtitle">{error || 'Article not found.'}</p>
          <Link to="/news" className="btn-secondary news-back-btn">← Back to News</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <div className="page-header">
        <Link to="/news" className="btn-secondary news-back-btn">← Back to News</Link>
        <h1 className="page-title news-detail-title">{article.title}</h1>
        <p className="page-subtitle">{article.summary}</p>
      </div>

      <article className="news-detail-card">
        {article.image?.url && (
          <div className="news-hero-wrap">
            <img className="news-hero-image" src={article.image.url} alt={article.title} />
            <p className="news-hero-credit">
              {article.image.provider || 'Image source'}
              {article.image.license ? ` · ${article.image.license}` : ''}
              {article.image.sourcePage && (
                <>
                  {' '}· <a href={article.image.sourcePage} target="_blank" rel="noreferrer">source</a>
                </>
              )}
            </p>
          </div>
        )}

        <div className="news-card-meta">
          <span className="news-timestamp">{new Date(article.generatedAt).toLocaleString()}</span>
          {article.tags?.length > 0 && (
            <div className="news-tags">
              {article.tags.map((tag) => (
                <span key={tag} className="news-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>

        <div className="news-audio-block">
          {audioLoading && <p className="news-audio-loading">Loading audio…</p>}
          {audioUnavailable && <p className="news-audio-error">Audio unavailable</p>}
          {audioUrl && (
            <audio controls className="news-audio-player">
              <source src={audioUrl} type="audio/mpeg" />
            </audio>
          )}
        </div>

        <div
          className="news-content"
          dangerouslySetInnerHTML={{ __html: markdownToHtml(article.content) }}
        />

        {article.sources?.length > 0 && (
          <section className="news-sources">
            <h3>Sources</h3>
            <ul>
              {article.sources.map((source, idx) => (
                <li key={`${source.url || source.title}-${idx}`}>
                  <a href={source.url || '#'} target="_blank" rel="noreferrer">
                    [{idx + 1}] {source.title}
                  </a>
                  {source.publisher ? ` — ${source.publisher}` : ''}
                  {source.publishedAt ? ` (${new Date(source.publishedAt).toLocaleDateString()})` : ''}
                </li>
              ))}
            </ul>
          </section>
        )}
      </article>
    </div>
  );
}

function markdownToHtml(md) {
  if (!md) return '';
  const escaped = String(md)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  let html = escaped
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br/>');
  html = html.replace(/((?:<li>.+?<\/li>(?:<br\/>)?)+)/g, '<ul>$1</ul>');
  return DOMPurify.sanitize(`<p>${html}</p>`, {
    ALLOWED_TAGS: ['h2', 'h3', 'h4', 'strong', 'em', 'ul', 'li', 'br', 'p'],
    ALLOWED_ATTR: [],
  });
}
