import { Area, AreaChart, ResponsiveContainer, Tooltip } from "recharts";
import type { MetricSchemaItem } from "../types";

export interface SparklinePoint {
  index: number;
  ts: string;
  value: number | undefined;
}

interface MetricTileProps {
  item: MetricSchemaItem;
  value: number | undefined;
  series: SparklinePoint[];
  color: string;
}

function formatValue(value: number): string {
  if (Number.isInteger(value)) return value.toString();
  return value.toFixed(3);
}

function EndDot(props: any) {
  const { cx, cy, index, dataLength, color } = props;
  if (index !== dataLength - 1 || cx == null || cy == null) return null;
  return (
    <circle cx={cx} cy={cy} r={4} fill={color} stroke="var(--panel-bg)" strokeWidth={2} />
  );
}

export function MetricTile({ item, value, series, color }: MetricTileProps) {
  const hasData = series.some((p) => p.value !== undefined);
  const dataLength = series.length;

  return (
    <div className="metric-tile" title={item.description}>
      <div className="metric-tile-header">
        <span className="metric-label">{item.label}</span>
        <span className="metric-value">
          {value !== undefined ? formatValue(value) : "—"}
          <span className="metric-unit">{item.unit}</span>
        </span>
      </div>
      <div className="metric-sparkline">
        {hasData ? (
          <ResponsiveContainer width="100%" height={56}>
            <AreaChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id={`fill-${item.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip
                cursor={{ stroke: "var(--gridline)", strokeWidth: 1 }}
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const point = payload[0].payload as SparklinePoint;
                  if (point.value === undefined) return null;
                  return (
                    <div className="sparkline-tooltip">
                      <strong>{formatValue(point.value)}</strong>
                      <span>{item.unit}</span>
                      <div className="sparkline-tooltip-ts">
                        {new Date(point.ts).toLocaleTimeString()}
                      </div>
                    </div>
                  );
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                fill={`url(#fill-${item.key})`}
                isAnimationActive={false}
                connectNulls
                dot={(props) => (
                  <EndDot key={props.index} {...props} dataLength={dataLength} color={color} />
                )}
                activeDot={{ r: 4, fill: color, stroke: "var(--panel-bg)", strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="metric-sparkline-empty">計測待ち</div>
        )}
      </div>
    </div>
  );
}
