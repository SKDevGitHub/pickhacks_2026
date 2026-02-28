import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import PillarPanel from '../components/PillarPanel';

const HORIZON_OPTIONS = ['', '12m', '24m', '36m'];

export default function Explorer() {
  const navigate = useNavigate();
  const [technologies, setTechnologies] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [horizon, setHorizon] = useState('');
  const [sortBy, setSortBy] = useState('risk');

  useEffect(() => {
    api.categories().then((cats) =>
      setCategories(cats.map((c) => ({ id: c.id, name: c.name })))
    );
  }, []);

  useEffect(() => {
    const params = {};
    if (search) params.search = search;
    if (category) params.category = category;
    if (horizon) params.horizon = horizon;
    if (sortBy) params.sortBy = sortBy;
    api.technologies(params).then(setTechnologies).catch(() => {});
  }, [search, category, horizon, sortBy]);

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Explorer</h1>
        <p className="page-subtitle">
          Searchable, filterable directory of all modeled technologies.
          Filter by Power Intensity, Emission Risk Tier, Water Stress Exposure,
          Category, and Forecast Horizon.
        </p>
      </div>

      {/* ── Filters ── */}
      <div className="filter-bar">
        <input
          type="text"
          placeholder="Search technologies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
          <span className="filter-label">Category</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
          <span className="filter-label">Horizon</span>
          <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
            {HORIZON_OPTIONS.map((h) => (
              <option key={h} value={h}>{h || 'All'}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
          <span className="filter-label">Sort</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="risk">Risk Score</option>
            <option value="power">Power Intensity</option>
            <option value="pollution">Emission Risk</option>
            <option value="water">Water Stress</option>
          </select>
        </div>
      </div>

      {/* ── Results Grid ── */}
      <div className="explorer-grid">
        {technologies.map((tech) => (
          <div
            key={tech.id}
            className="alert-card"
            onClick={() => navigate(`/forecasts/${tech.id}`)}
          >
            <div className="alert-card-header">
              <div>
                <div className="alert-card-name">{tech.name}</div>
                <div className="alert-card-meta">
                  {tech.category} · {tech.forecastHorizon} · {tech.region}
                </div>
              </div>
              <div className="tech-card-risk">
                <span
                  className="risk-score"
                  style={{
                    color:
                      tech.externalityRisk > 70
                        ? 'var(--accent-amber-text)'
                        : 'var(--text-secondary)',
                  }}
                >
                  {tech.externalityRisk}
                </span>
                <span className="risk-label">Risk</span>
              </div>
            </div>

            <div className="tech-card-pillars">
              <PillarPanel type="power" data={tech.power} compact />
              <PillarPanel type="pollution" data={tech.pollution} compact />
              <PillarPanel type="water" data={tech.water} compact />
            </div>
          </div>
        ))}
      </div>

      {technologies.length === 0 && (
        <div
          style={{
            textAlign: 'center',
            padding: 'var(--sp-16) 0',
            color: 'var(--text-tertiary)',
          }}
        >
          No technologies match your filters.
        </div>
      )}

      <p className="microcopy" style={{ marginTop: 'var(--sp-8)' }}>
        Forecast indices range from 0 (minimal impact) to 100 (critical). Deltas
        represent projected 12-month change. All assessments follow ISO
        14040/44–compliant lifecycle aggregation methodology.
      </p>
    </div>
  );
}
