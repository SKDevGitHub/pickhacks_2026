import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import PillarPanel from '../components/PillarPanel';

export default function Forecasts() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => {});
  }, []);

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Forecasts</h1>
        <p className="page-subtitle">
          Core intelligence view — technologies grouped by category with Power,
          Pollution, and Water projections for each.
        </p>
      </div>

      {categories.map((cat) => (
        <div key={cat.id} className="category-block">
          {/* ── Category Header ── */}
          <div className="category-header">
            <div className="category-meta">
              <h2 className="category-name">{cat.name}</h2>
              <p className="category-desc">{cat.description}</p>
            </div>
            <div className="category-averages">
              <div className="avg-chip">
                <span className="avg-chip-value" style={{ color: 'var(--power-color)' }}>
                  {cat.averages.power}
                </span>
                <span className="avg-chip-label">Power</span>
              </div>
              <div className="avg-chip">
                <span className="avg-chip-value" style={{ color: 'var(--pollution-color)' }}>
                  {cat.averages.pollution}
                </span>
                <span className="avg-chip-label">Pollution</span>
              </div>
              <div className="avg-chip">
                <span className="avg-chip-value" style={{ color: 'var(--water-color)' }}>
                  {cat.averages.water}
                </span>
                <span className="avg-chip-label">Water</span>
              </div>
            </div>
          </div>

          {/* ── Technology List ── */}
          <div className="tech-list">
            {cat.technologies.map((tech) => (
              <div
                key={tech.id}
                className="tech-card"
                onClick={() => navigate(`/forecasts/${tech.id}`)}
              >
                <div className="tech-card-info">
                  <div className="tech-card-name">{tech.name}</div>
                  <div className="tech-card-desc">{tech.description}</div>
                </div>
                <div className="tech-card-pillars">
                  <PillarPanel type="power" data={tech.power} compact />
                  <PillarPanel type="pollution" data={tech.pollution} compact />
                  <PillarPanel type="water" data={tech.water} compact />
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
                  <span className="risk-label">Externality Risk</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <p className="microcopy">
        All projections are derived from aggregated lifecycle assessment data,
        regional grid carbon intensity datasets, and deployment scaling
        assumptions. Default forecast horizon: 12–36 months.
      </p>
    </div>
  );
}
