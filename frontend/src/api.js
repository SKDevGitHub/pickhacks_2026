const BASE = '/api';

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  health: () => fetchJSON('/health'),
  engineStatus: () => fetchJSON('/engine-status'),
  macroSummary: () => fetchJSON('/macro-summary'),
  categories: () => fetchJSON('/categories'),
  technologies: (params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') qs.set(k, v);
    });
    const q = qs.toString();
    return fetchJSON(`/technologies${q ? '?' + q : ''}`);
  },
  technology: (id) => fetchJSON(`/technologies/${id}`),
  alerts: () => fetchJSON('/alerts'),
  regions: () => fetchJSON('/regions'),
  cities: () => fetchJSON('/cities'),
  simulate: (params) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON(`/scenarios/simulate?${qs}`);
  },
};
