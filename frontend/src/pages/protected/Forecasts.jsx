import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import PillarPanel from '../../components/charts/PillarPanel';

export default function Forecasts() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [cities, setCities] = useState([]);
  const [selectedCityId, setSelectedCityId] = useState('');
  const [scale, setScale] = useState(1);

  useEffect(() => {
    api
      .cities()
      .then((data) => {
        setCities(data);
        if (data.length) setSelectedCityId(data[0].id);
      })
      .catch(() => {});
  }, []);

  // Re-fetch categories whenever the selected city or scale changes
  useEffect(() => {
    if (!selectedCityId) return;
    const cityParam = selectedCityId === '_average' ? undefined : selectedCityId;
    api.categories(cityParam, scale).then(setCategories).catch(() => {});
  }, [selectedCityId, scale]);

  const selectedCity = selectedCityId === '_average' ? null : cities.find((city) => city.id === selectedCityId) || null;

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
            <option value="_average">Average (all cities)</option>
            {cities.map((city) => (
              <option key={city.id} value={city.id}>
                {city.name}
              </option>
            ))}
          </select>
        </div>

        {/* ── Deployment Scale Slider ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-4)', flexWrap: 'wrap' }}>
          <div>
            <div className="text-overline">Deployment Scale</div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
              Adjust how many units of each technology are deployed.
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
            <input
              type="range"
              min="0.1"
              max="10"
              step="0.1"
              value={scale}
              onChange={(e) => setScale(parseFloat(e.target.value))}
              style={{ width: 180, accentColor: 'var(--power-color)' }}
            />
            <span style={{ minWidth: 42, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
              {scale.toFixed(1)}×
            </span>
          </div>
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
            {selectedCity.intersections > 0 && (
              <p className="microcopy" style={{ marginTop: 0 }}>
                Intersections: {selectedCity.intersections.toLocaleString()}
              </p>
            )}
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
                  {formatValue(cat.averages.power)}
                </span>
                <span className="avg-chip-label">Avg Power (kWh)</span>
              </div>
              <div className="avg-chip">
                <span className="avg-chip-value" style={{ color: 'var(--pollution-color)' }}>
                  {formatValue(cat.averages.pollution)}
                </span>
                <span className="avg-chip-label">Avg CO₂ (kg)</span>
              </div>
              <div className="avg-chip">
                <span className="avg-chip-value" style={{ color: 'var(--water-color)' }}>
                  {formatValue(cat.averages.water)}
                </span>
                <span className="avg-chip-label">Avg Water (kgal)</span>
              </div>
            </div>
          </div>

          {/* ── Technology List ── */}
          <div className="tech-list">
            {cat.technologies.map((tech) => (
              <div
                key={tech.id}
                className="tech-card"
                onClick={() => navigate(`/forecasts/${tech.id}?city=${encodeURIComponent(selectedCityId)}${scale !== 1 ? `&scale=${scale}` : ''}`)}
              >
                <div className="tech-card-info">
                  <div className="tech-card-name">{tech.name}</div>
                  <div className="tech-card-desc">{tech.description}</div>
                </div>
                {tech.scaling && (
                  <div style={{ gridColumn: '1 / -1', paddingTop: 'var(--sp-1)', display: 'flex', gap: 'var(--sp-4)', flexWrap: 'wrap', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                      {tech.scaling.method === 'intersections'
                        ? `Scales by intersections`
                        : `${tech.scaling.unitsPerMillionPop} units / 1M pop`}
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>·</span>
                    <span>{tech.cost.units.toLocaleString(undefined, { maximumFractionDigits: 0 })} units deployed</span>
                    <span style={{ color: 'var(--text-tertiary)' }}>·</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>${tech.cost.total >= 1000 ? `${(tech.cost.total / 1000).toFixed(1)}B` : `${formatValue(tech.cost.total)}M`}</span>
                  </div>
                )}
                {/* ── Budget bar ── */}
                {selectedCity && selectedCity.cityFunds > 0 && tech.cost && (() => {
                  const pct = (tech.cost.total / selectedCity.cityFunds) * 100;
                  const barWidth = Math.min(pct, 100);
                  const costLabel = tech.cost.total >= 1000
                    ? `$${(tech.cost.total / 1000).toFixed(1)}B`
                    : `$${formatValue(tech.cost.total)}M`;
                  return (
                    <div style={{ gridColumn: '1 / -1', paddingTop: 'var(--sp-1)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>City Budget Impact</span>
                        <span style={{
                          fontSize: '0.7rem',
                          fontVariantNumeric: 'tabular-nums',
                          fontWeight: pct > 25 ? 600 : 400,
                          color: pct > 100 ? '#e74c3c' : pct > 25 ? '#f39c12' : 'var(--text-secondary)',
                        }}>
                          {costLabel} · {pct.toFixed(1)}% of budget
                        </span>
                      </div>
                      <div style={{
                        position: 'relative',
                        height: 10,
                        background: 'var(--bg-elevated)',
                        borderRadius: 'var(--radius-sm)',
                        overflow: 'hidden',
                        border: '1px solid var(--border-primary)',
                      }}>
                        <div style={{
                          width: `${barWidth}%`,
                          height: '100%',
                          background: pct > 100 ? '#e74c3c' : pct > 25 ? '#f39c12' : 'var(--power-color)',
                          opacity: 0.85,
                          borderRadius: 'var(--radius-sm)',
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                    </div>
                  );
                })()}
                <div className="tech-card-pillars" style={{ gridColumn: '1 / -1', marginTop: 'var(--sp-3)' }}>
                  <PillarPanel type="power" data={tech.power} compact />
                  <PillarPanel type="pollution" data={tech.pollution} compact />
                  <PillarPanel type="water" data={tech.water} compact />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <p className="microcopy">
        All projections are derived from aggregated lifecycle assessment data,
        regional grid carbon intensity datasets, and deployment scaling
        assumptions.
      </p>
    </div>
  );
}
