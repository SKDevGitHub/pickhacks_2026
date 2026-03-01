import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api';
import TrajectoryChart from '../../components/charts/TrajectoryChart';

function formatValue(value) {
  if (value == null) return '–';
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(1);
}

export default function Scenarios() {
  const [technologies, setTechnologies] = useState([]);
  const [regions, setRegions] = useState([]);

  // Scenario A
  const [techA, setTechA] = useState('');
  const [regionA, setRegionA] = useState('');
  const [simA, setSimA] = useState(null);

  // Scenario B (comparison)
  const [compare, setCompare] = useState(false);
  const [techB, setTechB] = useState('');
  const [regionB, setRegionB] = useState('');
  const [simB, setSimB] = useState(null);

  useEffect(() => {
    api.technologies().then((t) => {
      setTechnologies(t);
      if (t.length > 0) setTechA(t[0].id);
      if (t.length > 1) setTechB(t[1].id);
    });
    api.regions().then((r) => {
      const filtered = r.filter((name) => name !== 'Global');
      setRegions(filtered);
      if (filtered.length > 0) {
        setRegionA(filtered[0]);
        setRegionB(filtered[0]);
      }
    });
  }, []);

  const runSim = useCallback(async () => {
    if (techA) {
      const a = await api.simulate({ techId: techA, region: regionA, scale: 1.0 });
      setSimA(a);
    }
    if (compare && techB) {
      const b = await api.simulate({ techId: techB, region: regionB, scale: 1.0 });
      setSimB(b);
    } else {
      setSimB(null);
    }
  }, [techA, regionA, compare, techB, regionB]);

  // Auto-run on param change
  useEffect(() => {
    runSim();
  }, [runSim]);

  return (
    <div className="fade-in">
      <div className="page-intro">
        <h1 className="page-title">Scenarios</h1>
        <p className="page-subtitle">
          Simulate deployment choices and compare projected Power, Pollution, and
          Water outputs across technologies, regions, and scales.
        </p>
      </div>

      {/* ── Comparison Toggle ── */}
      <div style={{ marginBottom: 'var(--sp-6)' }}>
        <div className="toggle-group">
          <button
            className={`toggle-btn ${!compare ? 'active' : ''}`}
            onClick={() => setCompare(false)}
          >
            Single
          </button>
          <button
            className={`toggle-btn ${compare ? 'active' : ''}`}
            onClick={() => setCompare(true)}
          >
            Compare
          </button>
        </div>
      </div>

      {/* ── Controls ── */}
      <div
        className="scenario-controls"
        style={{
          gridTemplateColumns: compare ? '1fr 1fr' : '1fr 1fr 1fr auto',
        }}
      >
        {/* Scenario A */}
        <div style={compare ? { display: 'contents' } : { display: 'contents' }}>
          {compare && (
            <div style={{ gridColumn: '1 / -1', marginBottom: 'var(--sp-2)' }}>
              <span className="text-overline">Scenario A</span>
            </div>
          )}
          <div className="control-group">
            <label className="control-label">Technology</label>
            <select value={techA} onChange={(e) => setTechA(e.target.value)}>
              {technologies.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label className="control-label">Region</label>
            <select value={regionA} onChange={(e) => setRegionA(e.target.value)}>
              {regions.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Scenario B (if comparing) */}
        {compare && (
          <>
            <div style={{ gridColumn: '1 / -1', marginTop: 'var(--sp-4)', marginBottom: 'var(--sp-2)' }}>
              <span className="text-overline">Scenario B</span>
            </div>
            <div className="control-group">
              <label className="control-label">Technology</label>
              <select value={techB} onChange={(e) => setTechB(e.target.value)}>
                {technologies.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="control-group">
              <label className="control-label">Region</label>
              <select value={regionB} onChange={(e) => setRegionB(e.target.value)}>
                {regions.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>

      {/* ── Result Charts ── */}
      {simA && (
        <>
          <div style={{ marginBottom: 'var(--sp-4)' }}>
            <span className="text-headline">
              {simA.technology}
              {compare && simB ? ` vs ${simB.technology}` : ''}
            </span>
            <span className="text-caption" style={{ marginLeft: 'var(--sp-3)' }}>
              {simA.region}
              {compare && simB
                ? ` | ${simB.region}`
                : ''}
            </span>
          </div>

          <div className="charts-row">
            {['power', 'pollution', 'water'].map((dim) => {
              const colors = {
                power: '#6b8aad',
                pollution: '#d4915e',
                water: '#6b9a9a',
              };
              return (
                <div key={dim} className="chart-panel">
                  <div
                    className="chart-panel-title"
                    style={{
                      color: colors[dim],
                      textTransform: 'capitalize',
                    }}
                  >
                    {dim}
                    {simA.metrics?.[dim] && (
                      <span
                        className="text-caption"
                        style={{ marginLeft: 'var(--sp-3)', textTransform: 'none' }}
                      >
                        Index: {formatValue(simA.metrics[dim].forecastIndex)} {simA.metrics[dim].unit || ''}
                      </span>
                    )}
                  </div>
                  <TrajectoryChart
                    historical={simA[dim]?.historical || []}
                    projected={simA[dim]?.projected || []}
                    color={colors[dim]}
                    label={`${dim} A`}
                  />
                  {compare && simB && (
                    <div style={{ marginTop: 'var(--sp-3)', opacity: 0.7 }}>
                      <div
                        style={{
                          fontSize: '0.6875rem',
                          color: 'var(--text-tertiary)',
                          marginBottom: 4,
                        }}
                      >
                        Scenario B — {simB.technology}
                      </div>
                      <TrajectoryChart
                        historical={simB[dim]?.historical || []}
                        projected={simB[dim]?.projected || []}
                        color={colors[dim]}
                        label={`${dim} B`}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      <p className="microcopy" style={{ marginTop: 'var(--sp-6)' }}>
        Solid lines = observed data. Dotted lines = model projections. Shaded
        bands = uncertainty ranges. Simulations adjust projected values linearly
        relative to the baseline deployment scale assumption.
      </p>
    </div>
  );
}
