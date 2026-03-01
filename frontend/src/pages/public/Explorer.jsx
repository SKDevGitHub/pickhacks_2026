import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { api } from '../../api';
import PillarPanel from '../../components/charts/PillarPanel';
import { useRadarFavorites } from '../../hooks/useRadarFavorites';
import { isEduEmail } from '../../auth/authz';

export default function Explorer() {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth0();
  const eduAllowed = isAuthenticated && isEduEmail(user);
  const [technologies, setTechnologies] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [sortBy, setSortBy] = useState('power');
  const { isFavorite, toggleFavorite } = useRadarFavorites();

  useEffect(() => {
    api.categories().then((cats) =>
      setCategories(cats.map((c) => ({ id: c.id, name: c.name })))
    );
  }, []);

  useEffect(() => {
    const params = {};
    if (search) params.search = search;
    if (category) params.category = category;
    if (sortBy) params.sortBy = sortBy;
    api.technologies(params).then(setTechnologies).catch(() => {});
  }, [search, category, sortBy]);

  const openForecastDetail = (techId) => {
    if (!eduAllowed) return;
    navigate(`/forecasts/${techId}`);
  };

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Explorer</h1>
        <p className="page-subtitle">
          Searchable, filterable directory of all modeled technologies.
          Filter by Power Intensity, Emission Tier, Water Stress Exposure,
          and Category.
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
          <span className="filter-label">Sort</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="power">Power Intensity</option>
            <option value="pollution">Emission Impact</option>
            <option value="water">Water Stress</option>
          </select>
        </div>
      </div>

      {/* ── Results Grid ── */}
      <div className="explorer-grid">
        {technologies.map((tech) => (
          <div
            key={tech.id}
            className={`alert-card${eduAllowed ? '' : ' alert-card-disabled'}`}
            style={eduAllowed ? { cursor: 'pointer' } : { cursor: 'default', opacity: 0.85 }}
            onClick={() => openForecastDetail(tech.id)}
          >
            <div className="alert-card-header">
              <div>
                <div className="alert-card-name">{tech.name}</div>
                <div className="alert-card-meta">
                  {tech.category} · {tech.region}
                </div>
              </div>
              <div className="tech-card-actions">
                {isAuthenticated && (
                  <button
                    className={isFavorite(tech.id) ? 'btn-auth btn-logout' : 'btn-auth btn-login'}
                    style={{ height: 24, padding: '0 8px', fontSize: '0.65rem', marginBottom: 6 }}
                    onClick={(event) => {
                      event.stopPropagation();
                      toggleFavorite(tech.id);
                    }}
                  >
                    {isFavorite(tech.id) ? 'Untrack' : 'Track'}
                  </button>
                )}

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

      {!isAuthenticated && technologies.length > 0 && (
        <p className="microcopy" style={{ marginTop: 'var(--sp-4)', borderTop: 'none', paddingTop: 0 }}>
          Sign in to open full forecast details and use Radar tracking features.
        </p>
      )}

      <p className="microcopy" style={{ marginTop: 'var(--sp-8)' }}>
        Forecast indices range from 0 (minimal impact) to 100 (critical). Deltas
        represent projected 12-month change. All assessments follow ISO
        14040/44–compliant lifecycle aggregation methodology.
      </p>
    </div>
  );
}
