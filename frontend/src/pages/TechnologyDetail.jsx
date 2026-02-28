import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import TrajectoryChart from '../components/TrajectoryChart';
import PillarPanel from '../components/PillarPanel';

export default function TechnologyDetail() {
  const { techId } = useParams();
  const navigate = useNavigate();
  const [tech, setTech] = useState(null);
  const [scale, setScale] = useState(1.0);
  const [simData, setSimData] = useState(null);

  useEffect(() => {
    api.technology(techId).then(setTech).catch(() => {});
  }, [techId]);

  // Re-simulate when scale changes
  useEffect(() => {
    if (!tech) return;
    api
      .simulate({ techId: tech.id, region: tech.region || 'Global', scale })
      .then(setSimData)
      .catch(() => {});
  }, [tech, scale]);

  if (!tech) {
    return <div className="fade-in" style={{ padding: 'var(--sp-16) 0', textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading…</div>;
  }

  const traj = simData || tech.trajectory || {};

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

      {/* ── Scaling Multiplier Simulator ── */}
      <div className="detail-section">
        <h2 className="detail-section-title">Scaling Multiplier Simulator</h2>
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--sp-6)',
            maxWidth: 480,
          }}
        >
          <div className="slider-group">
            <div className="slider-header">
              <span className="control-label">Deployment Scale</span>
              <span className="text-mono" style={{ color: 'var(--text-primary)' }}>
                {scale.toFixed(1)}×
              </span>
            </div>
            <input
              type="range"
              min="0.1"
              max="5"
              step="0.1"
              value={scale}
              onChange={(e) => setScale(parseFloat(e.target.value))}
            />
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.625rem',
                color: 'var(--text-tertiary)',
              }}
            >
              <span>0.1×</span>
              <span>1× (baseline)</span>
              <span>5×</span>
            </div>
          </div>
          <p className="microcopy" style={{ marginTop: 'var(--sp-4)', borderTop: 'none', paddingTop: 0 }}>
            Adjust deployment levels to see corresponding impact changes across
            all three environmental dimensions.
          </p>
        </div>
      </div>

      {/* ── Geographic Sensitivity ── */}
      <div className="detail-section">
        <h2 className="detail-section-title">Geographic Sensitivity</h2>
        <div className="region-panel">
          <div className="region-list">
            {(tech.regionSensitivity || []).map((r) => (
              <div key={r.region} className="region-row">
                <span className="region-name">{r.region}</span>
                <div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--sp-2)',
                    }}
                  >
                    <span className="text-overline" style={{ minWidth: 88 }}>
                      Water Stress
                    </span>
                    <div className="region-bar" style={{ flex: 1 }}>
                      <div
                        className="region-bar-fill"
                        style={{
                          width: `${r.waterStress * 100}%`,
                          background: 'var(--water-color)',
                        }}
                      />
                    </div>
                    <span className="region-value">
                      {(r.waterStress * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--sp-2)',
                    }}
                  >
                    <span className="text-overline" style={{ minWidth: 88 }}>
                      Grid Carbon
                    </span>
                    <div className="region-bar" style={{ flex: 1 }}>
                      <div
                        className="region-bar-fill"
                        style={{
                          width: `${Math.min(100, (r.gridCarbon / 700) * 100)}%`,
                          background: 'var(--pollution-color)',
                        }}
                      />
                    </div>
                    <span className="region-value">
                      {r.gridCarbon} gCO₂/kWh
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Driver Breakdown ── */}
      <div className="detail-section">
        <h2 className="detail-section-title">Driver Breakdown</h2>
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}
        >
          <table className="driver-table">
            <tbody>
              {(tech.drivers || []).map((d, i) => (
                <tr key={i}>
                  <td>{d.label}</td>
                  <td>{d.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
