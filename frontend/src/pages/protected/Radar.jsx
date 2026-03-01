import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { api } from '../../api';
import PillarPanel from '../../components/charts/PillarPanel';
import { useRadarFavorites } from '../../hooks/useRadarFavorites';
import { isEduEmail } from '../../auth/authz';

export default function Radar() {
  const navigate = useNavigate();
  const { user } = useAuth0();
  const eduAllowed = isEduEmail(user);
  const [technologies, setTechnologies] = useState([]);
  const { favoriteIds, toggleFavorite } = useRadarFavorites();

  useEffect(() => {
    api.technologies({ sortBy: 'power' }).then(setTechnologies).catch(() => {});
  }, []);

  const favorites = useMemo(
    () => technologies.filter((tech) => favoriteIds.includes(tech.id)),
    [technologies, favoriteIds]
  );

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Radar</h1>
        <p className="page-subtitle">
          Your tracked emerging technologies and their environmental impact profiles.
        </p>
      </div>

      {/* ── Tracked technologies ── */}
      <div className="category-block">
        {favorites.length === 0 ? (
          <div
            style={{
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-lg)',
              padding: 'var(--sp-6)',
              color: 'var(--text-tertiary)',
            }}
          >
            No tracked technologies yet. Track technologies from the Explorer page to see them here.
          </div>
        ) : (
          <div className="explorer-grid">
            {favorites.map((tech) => (
              <div key={tech.id} className="alert-card">
                <div className="alert-card-header">
                  <div>
                    <div className="alert-card-name">{tech.name}</div>
                    <div className="alert-card-meta">{tech.category}</div>
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

                {eduAllowed && (
                  <div style={{ marginTop: 'var(--sp-3)', display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      className="btn-auth btn-login"
                      style={{ height: 28, padding: '0 10px', fontSize: '0.7rem' }}
                      onClick={() => navigate(`/forecasts/${tech.id}`)}
                    >
                      View Forecast
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
