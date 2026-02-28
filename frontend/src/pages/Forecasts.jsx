import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import PillarPanel from '../components/PillarPanel';

export default function Forecasts() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [cities, setCities] = useState([]);
  const [selectedCityId, setSelectedCityId] = useState('');

  useEffect(() => {
    api.categories().then(setCategories).catch(() => {});
    api
      .cities()
      .then((data) => {
        setCities(data);
        if (data.length) setSelectedCityId(data[0].id);
      })
      .catch(() => {});
  }, []);

  const selectedCity = cities.find((city) => city.id === selectedCityId) || null;

  const formatValue = (value) => {
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toFixed(1);
  };

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Forecasts</h1>
        <p className="page-subtitle">
          Core intelligence view — technologies grouped by category with Power,
          Pollution, and Water projections for each.
        </p>
      </div>

      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--sp-5)',
          marginBottom: 'var(--sp-8)',
          display: 'grid',
          gap: 'var(--sp-4)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--sp-4)', flexWrap: 'wrap' }}>
          <div>
            <div className="text-overline">City Selector</div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
              5 pre-loaded cities with baseline utility and pollution stats.
            </div>
          </div>
          <select
            value={selectedCityId}
            onChange={(e) => setSelectedCityId(e.target.value)}
            style={{
              minWidth: 220,
              height: 36,
              background: 'var(--bg-elevated)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-sm)',
              padding: '0 var(--sp-3)',
            }}
          >
            {cities.map((city) => (
              <option key={city.id} value={city.id}>
                {city.name}
              </option>
            ))}
          </select>
        </div>

        {selectedCity && (
          <>
            <div style={{ display: 'flex', gap: 'var(--sp-4)', flexWrap: 'wrap' }}>
              <div className="avg-chip" style={{ minWidth: 160 }}>
                <span className="avg-chip-value" style={{ color: 'var(--power-color)' }}>
                  {formatValue(selectedCity.stats.power.value)}
                </span>
                <span className="avg-chip-label">Power ({selectedCity.stats.power.unit}) · {selectedCity.stats.power.avgGrowth.toFixed(1)}%</span>
              </div>
              <div className="avg-chip" style={{ minWidth: 160 }}>
                <span className="avg-chip-value" style={{ color: 'var(--water-color)' }}>
                  {formatValue(selectedCity.stats.water.value)}
                </span>
                <span className="avg-chip-label">Water ({selectedCity.stats.water.unit}) · {selectedCity.stats.water.avgGrowth.toFixed(1)}%</span>
              </div>
              <div className="avg-chip" style={{ minWidth: 160 }}>
                <span className="avg-chip-value" style={{ color: 'var(--pollution-color)' }}>
                  {formatValue(selectedCity.stats.pollution.value)}
                </span>
                <span className="avg-chip-label">Pollution ({selectedCity.stats.pollution.unit}) · {selectedCity.stats.pollution.avgGrowth.toFixed(1)}%</span>
              </div>
            </div>
            <p className="microcopy" style={{ marginTop: 0 }}>
              Source: {selectedCity.source}
              {selectedCity.intersections > 0 ? ` · Intersections: ${selectedCity.intersections.toLocaleString()}` : ''}
            </p>
          </>
        )}
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
