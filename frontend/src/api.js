const BASE = '/api';

async function fetchJSON(path, options = {}) {
  const { token, headers, ...rest } = options;
  const mergedHeaders = {
    ...(headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: mergedHeaders,
  });
  if (!res.ok) {
    let detail = '';
    try {
      const payload = await res.json();
      detail = payload?.detail ? ` - ${payload.detail}` : '';
    } catch {
      try {
        const text = await res.text();
        detail = text ? ` - ${text}` : '';
      } catch {
        detail = '';
      }
    }
    throw new Error(`API ${res.status}: ${path}${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => fetchJSON('/health'),
  engineStatus: () => fetchJSON('/engine-status'),
  macroSummary: () => fetchJSON('/macro-summary'),
  categories: (city, scale) => {
    const qs = new URLSearchParams();
    if (city) qs.set('city', city);
    if (scale != null && scale !== 1) qs.set('scale', scale);
    const q = qs.toString();
    return fetchJSON(`/categories${q ? '?' + q : ''}`);
  },
  technologies: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') qs.set(k, v);
    });
    const q = qs.toString();
    return fetchJSON(`/technologies${q ? '?' + q : ''}`);
  },
  technology: (id, city, scale) => {
    const qs = new URLSearchParams();
    if (city) qs.set('city', city);
    if (scale != null && scale !== 1) qs.set('scale', scale);
    const q = qs.toString();
    return fetchJSON(`/technologies/${id}${q ? '?' + q : ''}`);
  },
  alerts: () => fetchJSON('/alerts'),
  regions: () => fetchJSON('/regions'),
  cities: () => fetchJSON('/cities'),
  budget: (city, scale) => {
    const qs = new URLSearchParams();
    if (city) qs.set('city', city);
    if (scale != null && scale !== 1) qs.set('scale', scale);
    const q = qs.toString();
    return fetchJSON(`/budget${q ? '?' + q : ''}`);
  },
  simulate: (params) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`/scenarios/simulate?${qs}`);
  },

  // ── Articles / News ──
  articles: () => fetchJSON('/articles'),
  adminArticles: (token) => fetchJSON('/admin/articles', { token }),
  article: (id) => fetchJSON(`/articles/${id}`),
  updateArticle: (id, payload, token) =>
    fetchJSON(`/articles/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      token,
    }),
  articleStems: (token) => fetchJSON('/article-stems', { token }),
  generateArticle: (tech, token) => {
    const qs = tech ? `?tech=${encodeURIComponent(tech)}` : '';
    return fetchJSON(`/articles/generate${qs}`, { method: 'POST', token });
  },
  setArticleStatus: (id, status, token) =>
    fetchJSON(`/articles/${id}/status?status=${encodeURIComponent(status)}`, {
      method: 'POST',
      token,
    }),
  deleteArticle: (id, token) =>
    fetchJSON(`/articles/${id}`, {
      method: 'DELETE',
      token,
    }),

};
