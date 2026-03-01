import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import PillarPanel from '../../components/charts/PillarPanel';
import { useRadarFavorites } from '../../hooks/useRadarFavorites';

export default function Radar() {
  const navigate = useNavigate();
  const [technologies, setTechnologies] = useState([]);
  const [search, setSearch] = useState('');
  const { favoriteIds, toggleFavorite } = useRadarFavorites();

  useEffect(() => {
    api.technologies({ sortBy: 'risk' }).then(setTechnologies).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return technologies;
    return technologies.filter(
      (tech) =>
        tech.name.toLowerCase().includes(q) ||
        tech.category.toLowerCase().includes(q) ||
        tech.description.toLowerCase().includes(q)
    );
  }, [technologies, search]);

  const favorites = useMemo(
    () => technologies.filter((tech) => favoriteIds.includes(tech.id)),
    [technologies, favoriteIds]
  );

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Radar</h1>
        <p className="page-subtitle">
          Track and favorite emerging technologies so your watchlist stays focused
          on what matters most.
        </p>
      </div>

      <div className="filter-bar" style={{ marginBottom: 'var(--sp-6)' }}>
        <input
          type="text"
          placeholder="Search technologies to track…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      <div className="category-block" style={{ marginBottom: 'var(--sp-8)' }}>
        <div className="category-header">
          <div className="category-meta">
            <h2 className="category-name">Favorites</h2>
            <p className="category-desc">
              {favorites.length} technology{favorites.length === 1 ? '' : 'ies'} in your radar watchlist.
            </p>
          </div>
        </div>

        {favorites.length === 0 ? (
          <div
            style={{
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)',
              padding: 'var(--sp-6)',
              color: 'var(--text-tertiary)',
            }}
          >
            No favorites yet. Add technologies from the list below.
          </div>
        ) : (
          <div className="explorer-grid">
            {favorites.map((tech) => (
              <div key={tech.id} className="alert-card">
                <div className="alert-card-header">
                  <div>
                    <div className="alert-card-name">{tech.name}</div>
                    <div className="alert-card-meta">{tech.category} · {tech.forecastHorizon}</div>
                  </div>
                  <button
                    className="btn-auth btn-logout"
                    style={{ height: 28, padding: '0 10px', fontSize: '0.7rem' }}
                    onClick={() => toggleFavorite(tech.id)}
                  >
                    Remove
                  </button>
                </div>

                <div className="tech-card-pillars">
                  <PillarPanel type="power" data={tech.power} compact />
                  <PillarPanel type="pollution" data={tech.pollution} compact />
                  <PillarPanel type="water" data={tech.water} compact />
                </div>

                <div style={{ marginTop: 'var(--sp-3)', display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    className="btn-auth btn-login"
                    style={{ height: 28, padding: '0 10px', fontSize: '0.7rem' }}
                    onClick={() => navigate(`/forecasts/${tech.id}`)}
                  >
                    View Forecast
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="category-block">
        <div className="category-header">
          <div className="category-meta">
            <h2 className="category-name">All Emerging Technologies</h2>
            <p className="category-desc">
              Use Track to add technologies to your Radar watchlist.
            </p>
          </div>
        </div>

        <div className="tech-list">
          {filtered.map((tech) => {
            const isFavorite = favoriteIds.includes(tech.id);
            return (
              <div key={tech.id} className="tech-card">
                <div className="tech-card-info" onClick={() => navigate(`/forecasts/${tech.id}`)}>
                  <div className="tech-card-name">{tech.name}</div>
                  <div className="tech-card-desc">{tech.description}</div>
                </div>

                <div className="tech-card-pillars" onClick={() => navigate(`/forecasts/${tech.id}`)}>
                  <PillarPanel type="power" data={tech.power} compact />
                  <PillarPanel type="pollution" data={tech.pollution} compact />
                  <PillarPanel type="water" data={tech.water} compact />
                </div>

                <div className="tech-card-risk" style={{ alignItems: 'flex-end', gap: 'var(--sp-2)' }}>
                  <button
                    className={isFavorite ? 'btn-secondary btn-untrack' : 'btn-primary'}
                    style={{ height: 28, padding: '0 10px', fontSize: '0.7rem' }}
                    onClick={() => toggleFavorite(tech.id)}
                  >
                    {isFavorite ? 'Untrack' : 'Track'}
                  </button>
                  <span className="risk-label">Risk {tech.externalityRisk}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
