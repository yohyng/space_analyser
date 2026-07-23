import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MetricSchemaItem, MetricsRecord } from "../types";

export interface HistoryPoint {
  index: number;
  ts: string;
  metrics: MetricsRecord;
}

interface MetricsChartProps {
  schema: MetricSchemaItem[];
  history: HistoryPoint[];
  selectedKeys: string[];
  onToggleKey: (key: string) => void;
}

const COLORS = ["#4f8ef7", "#f7734f", "#4ff79b", "#c74ff7", "#f7cf4f", "#4ff7ec"];

export function MetricsChart({ schema, history, selectedKeys, onToggleKey }: MetricsChartProps) {
  const ranges: Record<string, { min: number; max: number }> = {};
  for (const key of selectedKeys) {
    let min = Infinity;
    let max = -Infinity;
    for (const point of history) {
      const v = point.metrics[key];
      if (v === undefined) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    ranges[key] = { min: Number.isFinite(min) ? min : 0, max: Number.isFinite(max) ? max : 1 };
  }

  const chartData = history.map((point) => {
    const row: Record<string, number | string> = { index: point.index };
    for (const key of selectedKeys) {
      const raw = point.metrics[key];
      if (raw === undefined) continue;
      const { min, max } = ranges[key];
      row[key] = max > min ? (raw - min) / (max - min) : 0.5;
    }
    return row;
  });

  return (
    <div className="metrics-chart">
      <div className="chart-key-picker">
        {schema.map((m) => (
          <label key={m.key} className={selectedKeys.includes(m.key) ? "chip chip-active" : "chip"}>
            <input
              type="checkbox"
              checked={selectedKeys.includes(m.key)}
              onChange={() => onToggleKey(m.key)}
            />
            {m.label}
          </label>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="index" tick={false} label={{ value: "時間 →", position: "insideBottom", offset: -2 }} />
          <YAxis domain={[0, 1]} tick={false} label={{ value: "正規化値", angle: -90, position: "insideLeft" }} />
          <Tooltip
            formatter={(value, key) => {
              const label = schema.find((m) => m.key === key)?.label ?? String(key);
              return [typeof value === "number" ? value.toFixed(3) : String(value), label];
            }}
          />
          <Legend formatter={(key: string) => schema.find((m) => m.key === key)?.label ?? key} />
          {selectedKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <p className="hint">※ 各指標はグラフ表示のためウィンドウ内の最小～最大値で 0〜1 に正規化しています。実数値は上のカードを参照してください。</p>
    </div>
  );
}
