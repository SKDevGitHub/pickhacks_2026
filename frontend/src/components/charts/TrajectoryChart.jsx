import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';

/**
 * Multi-layer trajectory chart: solid historical → dotted projected + confidence band.
 *
 * @param {{
 *   historical: { month: number, value: number }[],
 *   projected: { month: number, value: number, upper: number, lower: number }[],
 *   color: string,
 *   label: string,
 * }} props
 */
export default function TrajectoryChart({
  historical = [],
  projected = [],
  color = '#6b8aad',
  label = '',
}) {
  // Merge into a single series; projected points include upper/lower for the band
  const merged = [
    ...historical.map((d) => ({
      month: d.month,
      observed: d.value,
      forecast: null,
      upper: null,
      lower: null,
    })),
    // Bridge point — last historical links to first projected
    ...(historical.length && projected.length
      ? [
          {
            month: 0,
            observed: historical[historical.length - 1].value,
            forecast: projected[0].value,
            upper: projected[0].upper,
            lower: projected[0].lower,
          },
        ]
      : []),
    ...projected.map((d) => ({
      month: d.month,
      observed: null,
      forecast: d.value,
      upper: d.upper,
      lower: d.lower,
    })),
  ];

  const fillColor = color + '18'; // 10% opacity hex

  return (
    <div style={{ width: '100%', height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={merged} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
            vertical={false}
          />
          <XAxis
            dataKey="month"
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
            axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
            tickLine={false}
            tickFormatter={(v) => (v === 0 ? 'Now' : `${v > 0 ? '+' : ''}${v}m`)}
          />
          <YAxis
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: '#1e1e1e',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              fontSize: 12,
              color: 'rgba(255,255,255,0.8)',
            }}
            labelFormatter={(v) =>
              v === 0 ? 'Present' : `${v > 0 ? '+' : ''}${v} months`
            }
          />

          {/* Confidence band */}
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill={fillColor}
            fillOpacity={1}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill="var(--bg-card)"
            fillOpacity={1}
            isAnimationActive={false}
          />

          {/* Now reference line */}
          <ReferenceLine
            x={0}
            stroke="rgba(255,255,255,0.12)"
            strokeDasharray="4 4"
            label={{
              value: 'Now',
              position: 'top',
              fill: 'rgba(255,255,255,0.3)',
              fontSize: 10,
            }}
          />

          {/* Historical — solid */}
          <Line
            type="monotone"
            dataKey="observed"
            stroke={color}
            strokeWidth={2}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />

          {/* Projected — dotted */}
          <Line
            type="monotone"
            dataKey="forecast"
            stroke={color}
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
