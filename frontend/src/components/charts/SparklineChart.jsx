import {
  ResponsiveContainer,
  LineChart,
  Line,
  YAxis,
} from 'recharts';

/**
 * Compact sparkline chart for index scores.
 * @param {{ data: number[], color: string }} props
 */
export default function SparklineChart({ data = [], color = '#6b8aad' }) {
  const chartData = data.map((v, i) => ({ i, v }));

  return (
    <div style={{ width: '100%', height: 32 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <YAxis domain={['dataMin - 5', 'dataMax + 5']} hide />
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
