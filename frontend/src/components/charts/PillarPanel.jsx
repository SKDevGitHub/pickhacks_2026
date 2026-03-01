import SparklineChart from './SparklineChart';

const PILLAR_CONF = {
  power: { label: 'Power', color: 'var(--power-color)', cls: 'pillar-power', hex: '#6b8aad' },
  pollution: { label: 'Pollution', color: 'var(--pollution-color)', cls: 'pillar-pollution', hex: '#d4915e' },
  water: { label: 'Water', color: 'var(--water-color)', cls: 'pillar-water', hex: '#6b9a9a' },
};

function formatValue(value) {
  if (value == null) return '–';
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(1);
}

/**
 * Renders a single pillar mini-panel (Power, Pollution, or Water).
 *
 * @param {{ type: 'power'|'pollution'|'water', data: object, compact?: boolean }} props
 */
export default function PillarPanel({ type, data, compact = false }) {
  const conf = PILLAR_CONF[type];
  const idx = data?.forecastIndex ?? 0;
  const unit = data?.unit ?? '';
  const delta = data?.delta ?? 0;

  const deltaClass =
    delta > 0 ? 'delta-up' : delta < 0 ? 'delta-down' : 'delta-neutral';
  const arrow = delta > 0 ? '↑' : delta < 0 ? '↓' : '–';

  return (
    <div className="tech-pillar-cell">
      <span className={`pillar-label ${conf.cls}`}>{conf.label}</span>
      <div className="pillar-value-row">
        <span className={`index-score ${compact ? 'index-score-sm' : ''}`} style={{ color: conf.color }}>
          {formatValue(idx)}
        </span>
        {unit && (
          <span className="pillar-unit">{unit}</span>
        )}
      </div>
      <span className={`delta ${deltaClass}`}>
        {arrow} {Math.abs(delta).toFixed(1)}% in 10 yr
      </span>
      {data?.sparkline && (
        <SparklineChart data={data.sparkline} color={conf.hex} />
      )}
    </div>
  );
}
