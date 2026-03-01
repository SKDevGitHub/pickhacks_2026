import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api';
import TrajectoryChart from '../../components/charts/TrajectoryChart';
import PillarPanel from '../../components/charts/PillarPanel';
import { useRadarFavorites } from '../../hooks/useRadarFavorites';

export default function TechnologyDetail() {
  const { techId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [cities, setCities] = useState([]);
  const [selectedCityId, setSelectedCityId] = useState(searchParams.get('city') || '');
  const [scale, setScale] = useState(parseFloat(searchParams.get('scale')) || 1);
  const [tech, setTech] = useState(null);
  const { isFavorite, toggleFavorite } = useRadarFavorites();

  /* Load city list once */
  useEffect(() => {
    api.cities().then((data) => {
      setCities(data);
      if (!selectedCityId && data.length) setSelectedCityId(data[0].id);
    }).catch(() => {});
  }, []);

  /* Re-fetch tech whenever city or scale changes */
  useEffect(() => {
    const city = selectedCityId === '_average' ? undefined : selectedCityId || undefined;
    api.technology(techId, city, scale).then(setTech).catch(() => {});
  }, [techId, selectedCityId, scale]);

  if (!tech) {
    return <div className="fade-in" style={{ padding: 'var(--sp-16) 0', textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading…</div>;
  }

  const traj = tech.trajectory || {};

  const formatValue = (value) => {
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toFixed(1);
  };

  const selectStyle = {
    minWidth: 200,
    height: 36,
    background: 'var(--bg-elevated)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-primary)',
    borderRadius: 'var(--radius-sm)',
    padding: '0 var(--sp-3)',
  };

  return (
    <div className="fade-in">
      {/* ── Back Link ── */}
      <button className="detail-back" onClick={() => navigate('/forecasts')}>
        ← Back to Forecasts
      </button>

      {/* ── Header ── */}
      <div className="detail-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--sp-4)' }}>
          <h1 className="detail-title">{tech.name}</h1>
          <button
            className={isFavorite(tech.id) ? 'btn-secondary btn-untrack' : 'btn-primary'}
            style={{ height: 32, padding: '0 14px', fontSize: '0.75rem', flexShrink: 0 }}
            onClick={() => toggleFavorite(tech.id)}
          >
            {isFavorite(tech.id) ? 'Untrack' : 'Track'}
          </button>
        </div>
        <p className="detail-desc">{tech.description}</p>
        <div style={{ display: 'flex', gap: 'var(--sp-4)', marginTop: 'var(--sp-4)' }}>
          <span className="text-overline">{tech.category}</span>
          <span className="text-overline">Region: {tech.region}</span>
        </div>
      </div>

      {/* ── City & Scale Selectors ── */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--sp-4) var(--sp-5)',
          marginBottom: 'var(--sp-6)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--sp-6)',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          <span className="text-overline" style={{ whiteSpace: 'nowrap' }}>City</span>
          <select value={selectedCityId} onChange={(e) => setSelectedCityId(e.target.value)} style={selectStyle}>
            <option value="_average">Average (all cities)</option>
            {cities.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          <span className="text-overline" style={{ whiteSpace: 'nowrap' }}>Scale</span>
          <input
            type="range"
            min="0.1"
            max="10"
            step="0.1"
            value={scale}
            onChange={(e) => setScale(parseFloat(e.target.value))}
            style={{ width: 160, accentColor: 'var(--power-color)' }}
          />
          <span style={{ minWidth: 42, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
            {scale.toFixed(1)}×
          </span>
        </div>
      </div>

      {/* ── Summary Pillars ── */}
      <div className="pillar-grid" style={{ marginBottom: 'var(--sp-4)' }}>
        <PillarPanel type="power" data={tech.power} />
        <PillarPanel type="pollution" data={tech.pollution} />
        <PillarPanel type="water" data={tech.water} />
      </div>

      {/* ── Cost Summary ── */}
      {tech.cost && (
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--sp-4) var(--sp-5)',
            marginBottom: 'var(--sp-8)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--sp-6)',
            flexWrap: 'wrap',
          }}
        >
          <div className="text-overline" style={{ marginRight: 'auto' }}>Deployment Cost</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Units</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{tech.cost.units.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Per Unit</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>${tech.cost.perUnit < 1 ? `${(tech.cost.perUnit * 1000).toFixed(0)}K` : `${tech.cost.perUnit.toLocaleString()}M`}</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Total</div>
            <div style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>${tech.cost.total >= 1000 ? `${(tech.cost.total / 1000).toFixed(1)}B` : `${tech.cost.total.toFixed(0)}M`}</div>
          </div>
        </div>
      )}

      {/* ── Trajectory Charts ── */}
      <div className="detail-section">
        <h2 className="detail-section-title">Trajectory Forecast</h2>
        <div className="charts-row">
          <div className="chart-panel">
            <div className="chart-panel-title" style={{ color: 'var(--power-color)' }}>
              Power
            </div>
            <TrajectoryChart
              historical={traj.power?.historical || []}
              projected={traj.power?.projected || []}
              color="#6b8aad"
              label="Power Index"
            />
          </div>
          <div className="chart-panel">
            <div className="chart-panel-title" style={{ color: 'var(--pollution-color)' }}>
              Pollution
            </div>
            <TrajectoryChart
              historical={traj.pollution?.historical || []}
              projected={traj.pollution?.projected || []}
              color="#d4915e"
              label="Pollution Index"
            />
          </div>
          <div className="chart-panel">
            <div className="chart-panel-title" style={{ color: 'var(--water-color)' }}>
              Water
            </div>
            <TrajectoryChart
              historical={traj.water?.historical || []}
              projected={traj.water?.projected || []}
              color="#6b9a9a"
              label="Water Index"
            />
          </div>
        </div>
        <p className="microcopy">
          Solid lines represent observed data. Dotted lines are model
          projections. Shaded bands indicate uncertainty ranges.
        </p>
      </div>
    </div>
  );
}
