import type { MetricSchemaItem, MetricsRecord } from "../types";

interface MetricsDashboardProps {
  schema: MetricSchemaItem[];
  metrics: MetricsRecord | null;
}

function formatValue(value: number): string {
  if (Number.isInteger(value)) return value.toString();
  return value.toFixed(3);
}

export function MetricsDashboard({ schema, metrics }: MetricsDashboardProps) {
  if (schema.length === 0) {
    return <p className="hint">指標スキーマを読み込み中...</p>;
  }

  const groups = Array.from(new Set(schema.map((m) => m.group)));

  return (
    <div className="metrics-dashboard">
      {groups.map((group) => (
        <section key={group} className="metric-group">
          <h3>{group}</h3>
          <div className="metric-cards">
            {schema
              .filter((m) => m.group === group)
              .map((m) => (
                <div key={m.key} className="metric-card" title={m.description}>
                  <div className="metric-label">{m.label}</div>
                  <div className="metric-value">
                    {metrics ? formatValue(metrics[m.key] ?? 0) : "—"}
                    <span className="metric-unit">{m.unit}</span>
                  </div>
                </div>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}
