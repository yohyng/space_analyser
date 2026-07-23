import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import { GROUP_COLORS } from "../groupColors";
import type { MetricSchemaItem, MetricsRecord } from "../types";

interface MetricsRadarProps {
  schema: MetricSchemaItem[];
  latestMetrics: MetricsRecord | null;
}

interface RadarDatum {
  key: string;
  label: string;
  group: string;
  color: string;
  value: number;
}

interface AngleTickProps {
  x?: number | string;
  y?: number | string;
  textAnchor?: React.SVGProps<SVGTextElement>["textAnchor"];
  payload?: { value: string };
  colorByLabel: Record<string, string>;
}

function AngleTick({ x, y, textAnchor, payload, colorByLabel }: AngleTickProps) {
  if (!payload) return null;
  const color = colorByLabel[payload.value] ?? "var(--text)";
  return (
    <text x={x} y={y} textAnchor={textAnchor} fill={color} fontSize={9.5} dy={3}>
      {payload.value}
    </text>
  );
}

export function MetricsRadar({ schema, latestMetrics }: MetricsRadarProps) {
  if (schema.length === 0) {
    return <p className="hint">指標スキーマを読み込み中...</p>;
  }
  if (!latestMetrics) {
    return <p className="hint metrics-radar-empty">計測を開始すると表示されます</p>;
  }

  const groups = Array.from(new Set(schema.map((m) => m.group)));
  const groupColor = (group: string) => GROUP_COLORS[groups.indexOf(group) % GROUP_COLORS.length];

  const data: RadarDatum[] = schema.map((item) => ({
    key: item.key,
    label: item.label,
    group: item.group,
    color: groupColor(item.group),
    value: latestMetrics[item.key] ?? 0,
  }));

  const colorByLabel = Object.fromEntries(data.map((d) => [d.label, d.color]));

  return (
    <div className="metrics-radar">
      <ResponsiveContainer width="100%" height={560}>
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="var(--gridline)" />
          <PolarAngleAxis
            dataKey="label"
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            tick={((p: any) => <AngleTick {...p} colorByLabel={colorByLabel} />) as never}
          />
          <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const d = payload[0].payload as RadarDatum;
              return (
                <div className="sparkline-tooltip">
                  <strong>{d.value.toFixed(3)}</strong>
                  <div className="sparkline-tooltip-ts">
                    {d.group} ・ {d.label}
                  </div>
                </div>
              );
            }}
          />
          <Radar
            dataKey="value"
            stroke="var(--accent)"
            fill="var(--accent)"
            fillOpacity={0.18}
            strokeWidth={2}
            isAnimationActive={false}
            dot={{ r: 2, fill: "var(--accent)", strokeWidth: 0 }}
            activeDot={{ r: 4 }}
          />
        </RadarChart>
      </ResponsiveContainer>
      <div className="radar-legend">
        {groups.map((group, i) => (
          <span key={group} className="chip">
            <span className="chip-dot" style={{ background: GROUP_COLORS[i % GROUP_COLORS.length] }} />
            {group}
          </span>
        ))}
      </div>
      <p className="hint">※ 全指標は0〜1の範囲に正規化済みのため、そのままレーダーの半径として表示しています。</p>
    </div>
  );
}
