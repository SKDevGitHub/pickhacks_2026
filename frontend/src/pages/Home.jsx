import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { MOMENTUM_SUPPLEMENTS, TRENDING_SIGNALS, LATEST_NEWS } from '../data/mockHomepage';

const PILLAR_COLOR = {
  power:     { fg: 'var(--power-color)',     bg: 'var(--power-bg)',     label: 'Power'     },
  pollution: { fg: 'var(--pollution-color)', bg: 'var(--pollution-bg)', label: 'Pollution' },
  water:     { fg: 'var(--water-color)',     bg: 'var(--water-bg)',     label: 'Water'     },
};

const RISK_DOT   = { high: 'var(--accent-amber)', medium: '#c4a96b', low: 'var(--accent-green)' };
const TAG_COLOR  = {
  Power:     { fg: 'var(--power-color)',     bg: 'var(--power-bg)'     },
  Pollution: { fg: 'var(--pollution-color)', bg: 'var(--pollution-bg)' },
  Water:     { fg: 'var(--water-color)',     bg: 'var(--water-bg)'     },
};

function MicroBar({ value, color }) {
  return (
    <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
      <div style={{ width: `${Math.min(value, 100)}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.6s var(--ease-out)' }} />
    </div>
  );
}

function EnvMicroPanel({ type, data }) {
  const conf = PILLAR_COLOR[type];
  return (
    <div style={{ flex: '1 1 0', padding: '8px 10px', background: conf.bg, borderRadius: 8, minWidth: 0 }}>
      <div style={{ fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: conf.fg, marginBottom: 3 }}>
        {conf.label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 600, color: conf.fg, lineHeight: 1 }}>
          {data?.forecastIndex ?? '–'}
        </span>
        <span style={{ fontSize: '0.6875rem', fontWeight: 500, color: (data?.delta ?? 0) > 0 ? 'var(--accent-amber-text)' : 'var(--accent-green-text)' }}>
          {(data?.delta ?? 0) > 0 ? '↑' : '↓'}{Math.abs(data?.delta ?? 0).toFixed(1)}
        </span>
      </div>
      <MicroBar value={data?.forecastIndex ?? 0} color={conf.fg} />
    </div>
  );
}

function MomentumCard({ tech, supplement, onClick }) {
  const momentum   = supplement?.momentum ?? 50;
  const delta      = supplement?.delta    ?? 0;
  const insight    = supplement?.insight  ?? '';
  const isHighRisk = tech.externalityRisk > 70;

  return (
    <article
      onClick={onClick}
      style={{
        background: 'var(--bg-card)', border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-lg)', padding: 'var(--sp-5) var(--sp-6)',
        cursor: 'pointer', transition: 'background 220ms var(--ease-out), border-color 220ms var(--ease-out), transform 220ms var(--ease-out)',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-card-hover)'; e.currentTarget.style.borderColor = 'var(--border-hover)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-card)';       e.currentTarget.style.borderColor = 'var(--border-primary)';  e.currentTarget.style.transform = 'translateY(0)';    }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--sp-4)', marginBottom: 'var(--sp-4)' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: '0.9375rem', fontWeight: 600, letterSpacing: '-0.01em', marginBottom: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {tech.name}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
            {tech.category} · {tech.forecastHorizon} horizon
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, justifyContent: 'flex-end' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '1.5rem', fontWeight: 600, lineHeight: 1, color: momentum >= 75 ? 'var(--accent-amber-text)' : 'var(--text-primary)' }}>
              {momentum}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'flex-end', marginTop: 2 }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 500, color: delta > 0 ? 'var(--accent-green-text)' : 'var(--accent-amber-text)' }}>
              {delta > 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}%
            </span>
            <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)' }}>7d</span>
          </div>
          <div style={{ fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginTop: 1 }}>Momentum</div>
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: 'var(--border-secondary)', marginBottom: 'var(--sp-3)' }} />

      {/* Environmental Snapshot */}
      <div style={{ marginBottom: 'var(--sp-4)' }}>
        <div style={{ fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 'var(--sp-2)' }}>
          Environmental Snapshot
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <EnvMicroPanel type="power"     data={tech.power}     />
          <EnvMicroPanel type="pollution" data={tech.pollution} />
          <EnvMicroPanel type="water"     data={tech.water}     />
        </div>
      </div>

      {/* AI Insight */}
      {insight && (
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 'var(--sp-3)', fontStyle: 'italic' }}>
          "{insight}"
        </div>
      )}

      {/* Footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {isHighRisk && (
            <span style={{ fontSize: '0.625rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--accent-amber-text)', background: 'var(--accent-amber-muted)', padding: '2px 7px', borderRadius: 4 }}>
              Elevated Risk
            </span>
          )}
          <span style={{ fontSize: '0.625rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            ERS {tech.externalityRisk}
          </span>
        </div>
        <span style={{ fontSize: '0.8125rem', color: 'var(--accent-blue)', fontWeight: 500 }}>
          View Forecast →
        </span>
      </div>
    </article>
  );
}

export default function Home() {
  const navigate = useNavigate();
  const [status,   setStatus]   = useState(null);
  const [allTechs, setAllTechs] = useState([]);

  useEffect(() => {
    api.engineStatus().then(setStatus).catch(() => {});
    api.technologies({ sortBy: 'risk' }).then(setAllTechs).catch(() => {});
  }, []);

  return (
    <div className="fade-in" style={{ maxWidth: 'var(--content-max)', margin: '0 auto' }}>

      {/* Mission statement */}
      <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', marginBottom: 'var(--sp-5)', letterSpacing: '-0.005em' }}>
        Track emerging technologies and forecast their environmental impact before they scale.
      </p>

      {/* Engine Status Strip */}
      {status && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 1, background: 'var(--border-primary)', borderRadius: 'var(--radius-md)', overflow: 'hidden', marginBottom: 'var(--sp-7)' }}>
          {[
            { value: status.technologiesModeled, label: 'Technologies Tracked',  color: 'var(--text-primary)' },
            { value: '7',                         label: 'Breakout Signals',      color: 'var(--accent-blue-text)' },
            { value: status.highRiskAlerts,       label: 'Elevated Env. Flags',   color: 'var(--accent-amber-text)' },
            { value: new Date(status.lastModelUpdate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }), label: 'Last Updated', color: 'var(--text-primary)' },
          ].map((item, i) => (
            <div key={i} style={{ background: 'var(--bg-card)', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '1.125rem', fontWeight: 600, color: item.color, lineHeight: 1 }}>{item.value}</span>
              <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)', fontWeight: 500, letterSpacing: '0.01em', lineHeight: 1.4 }}>{item.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Two-column layout */}
      <div className="home-two-col">

        {/* LEFT — Primary Feed */}
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 'var(--sp-5)' }}>
            <h2 style={{ fontSize: '0.875rem', fontWeight: 600, letterSpacing: '-0.01em' }}>Emerging Technologies</h2>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>Ranked by momentum · {allTechs.length} tracked</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
            {allTechs
              .slice()
              .sort((a, b) => (MOMENTUM_SUPPLEMENTS[b.id]?.momentum ?? 0) - (MOMENTUM_SUPPLEMENTS[a.id]?.momentum ?? 0))
              .map((tech) => (
                <MomentumCard
                  key={tech.id}
                  tech={tech}
                  supplement={MOMENTUM_SUPPLEMENTS[tech.id]}
                  onClick={() => navigate(`/forecasts/${tech.id}`)}
                />
              ))}
          </div>

          <p style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)', marginTop: 'var(--sp-6)', lineHeight: 1.6, fontStyle: 'italic', paddingTop: 'var(--sp-4)', borderTop: '1px solid var(--border-secondary)' }}>
            Forecasts based on aggregated lifecycle assessment data, grid carbon intensity datasets, environmental
            benchmarks, and deployment scaling assumptions. Default horizon: 12–36 months.
          </p>
        </div>

        {/* RIGHT — Sidebar */}
        <aside style={{ position: 'sticky', top: 'calc(var(--nav-height) + 24px)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>

          {/* Trending Signals */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-5)' }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 'var(--sp-4)' }}>Trending Signals</div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {TRENDING_SIGNALS.map((sig, i) => (
                <div
                  key={sig.id}
                  onClick={() => navigate(`/forecasts/${sig.id}`)}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 0', borderBottom: i < TRENDING_SIGNALS.length - 1 ? '1px solid var(--border-secondary)' : 'none', cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: RISK_DOT[sig.riskLevel], flexShrink: 0 }} />
                    <span style={{ fontSize: '0.8125rem', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{sig.name}</span>
                  </div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-green-text)', flexShrink: 0, marginLeft: 8 }}>▲{sig.delta.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Latest Research & News */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-5)' }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 'var(--sp-4)' }}>Latest Research &amp; News</div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {LATEST_NEWS.map((article, i) => (
                <div key={i} style={{ padding: '9px 0', borderBottom: i < LATEST_NEWS.length - 1 ? '1px solid var(--border-secondary)' : 'none' }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 500, lineHeight: 1.45, color: 'var(--text-primary)', marginBottom: 4 }}>{article.headline}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: TAG_COLOR[article.tag]?.fg ?? 'var(--text-tertiary)', background: TAG_COLOR[article.tag]?.bg ?? 'transparent', padding: '1px 6px', borderRadius: 4 }}>{article.tag}</span>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>{article.source}</span>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>·</span>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>{article.date}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </aside>
      </div>
    </div>
  );
}
