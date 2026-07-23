import { useMemo } from "react";
import { MetricTile } from "./MetricTile";
import type { MetricSchemaItem, MetricsRecord } from "../types";

export interface HistoryPoint {
  index: number;
  ts: string;
  metrics: MetricsRecord;
}

interface MetricsGridProps {
  schema: MetricSchemaItem[];
  latestMetrics: MetricsRecord | null;
  history: HistoryPoint[];
}

const GROUP_COLORS = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)", "var(--cat-6)"];

export function MetricsGrid({ schema, latestMetrics, history }: MetricsGridProps) {
  const groups = useMemo(() => Array.from(new Set(schema.map((m) => m.group))), [schema]);

  const seriesByKey = useMemo(() => {
    const map: Record<string, { index: number; ts: string; value: number | undefined }[]> = {};
    for (const item of schema) {
      map[item.key] = history.map((point) => ({
        index: point.index,
        ts: point.ts,
        value: point.metrics[item.key],
      }));
    }
    return map;
  }, [schema, history]);

  if (schema.length === 0) {
    return <p className="hint">指標スキーマを読み込み中...</p>;
  }

  return (
    <div className="metrics-grid">
      {groups.map((group, groupIndex) => (
        <section key={group} className="metric-group" style={{ ["--group-color" as string]: GROUP_COLORS[groupIndex % GROUP_COLORS.length] }}>
          <h3>{group}</h3>
          <div className="metric-tiles">
            {schema
              .filter((m) => m.group === group)
              .map((item) => (
                <MetricTile
                  key={item.key}
                  item={item}
                  value={latestMetrics?.[item.key]}
                  series={seriesByKey[item.key]}
                  color={GROUP_COLORS[groupIndex % GROUP_COLORS.length]}
                />
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}
