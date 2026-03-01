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
  const city = searchParams.get('city') || undefined;
  const scale = parseFloat(searchParams.get('scale')) || 1;
  const [tech, setTech] = useState(null);
  const { isFavorite, toggleFavorite } = useRadarFavorites();

  useEffect(() => {
    api.technology(techId, city, scale).then(setTech).catch(() => {});
  }, [techId, city, scale]);

  if (!tech) {
    return <div className="fade-in" style={{ padding: 'var(--sp-16) 0', textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading…</div>;
  }

  const traj = tech.trajectory || {};

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

      {/* ── Driver Breakdown ── */}
      <div className="detail-section">
        <h2 className="detail-section-title">Driver Breakdown</h2>
        <div className="driver-breakdown">
          {(tech.drivers || []).map((d, i) => (
            <article key={i} className="driver-card">
              <div className="driver-card-head">
                <h3 className="driver-card-label">{d.label}</h3>
                <span className="driver-card-value">{d.value}</span>
              </div>
              <div className="driver-card-meter" aria-hidden="true">
                <span
                  className="driver-card-meter-fill"
                  style={{ width: `${Math.max(28, 100 - i * 12)}%` }}
                />
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
