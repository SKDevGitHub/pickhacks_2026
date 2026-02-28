import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../api';
import TrajectoryChart from '../../components/TrajectoryChart';
import PillarPanel from '../../components/PillarPanel';

export default function TechnologyDetail() {
  const { techId } = useParams();
  const navigate = useNavigate();
  const [tech, setTech] = useState(null);

  useEffect(() => {
    api.technology(techId).then(setTech).catch(() => {});
  }, [techId]);

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
        <h1 className="detail-title">{tech.name}</h1>
        <p className="detail-desc">{tech.description}</p>
        <div style={{ display: 'flex', gap: 'var(--sp-4)', marginTop: 'var(--sp-4)' }}>
          <span className="text-overline">{tech.category}</span>
          <span className="text-overline">Horizon: {tech.forecastHorizon}</span>
          <span className="text-overline">Region: {tech.region}</span>
        </div>
      </div>

      {/* ── Summary Pillars ── */}
      <div className="pillar-grid" style={{ marginBottom: 'var(--sp-8)' }}>
        <PillarPanel type="power" data={tech.power} />
        <PillarPanel type="pollution" data={tech.pollution} />
        <PillarPanel type="water" data={tech.water} />
      </div>

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
