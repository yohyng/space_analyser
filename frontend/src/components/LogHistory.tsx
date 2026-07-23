import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "../config";
import type { LogEntry, MetricSchemaItem } from "../types";

interface LogHistoryProps {
  sessionId: string | null;
  schema: MetricSchemaItem[];
  refreshSignal: number;
}

const SUMMARY_KEYS = ["mean_luminance", "openness_proxy", "spatial_clarity_proxy", "motion_level"];

export function LogHistory({ sessionId, schema, refreshSignal }: LogHistoryProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [onlyCurrentSession, setOnlyCurrentSession] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "50" });
    if (onlyCurrentSession && sessionId) params.set("session_id", sessionId);
    fetch(`${API_BASE_URL}/api/logs?${params.toString()}`)
      .then((res) => res.json() as Promise<LogEntry[]>)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, [sessionId, onlyCurrentSession]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshSignal, onlyCurrentSession]);

  const summaryLabel = (key: string) => schema.find((m) => m.key === key)?.label ?? key;

  const exportUrl = (() => {
    const params = new URLSearchParams();
    if (onlyCurrentSession && sessionId) params.set("session_id", sessionId);
    const qs = params.toString();
    return `${API_BASE_URL}/api/logs/export.csv${qs ? `?${qs}` : ""}`;
  })();

  return (
    <div className="log-history">
      <div className="log-history-header">
        <label>
          <input
            type="checkbox"
            checked={onlyCurrentSession}
            onChange={(e) => setOnlyCurrentSession(e.target.checked)}
          />
          現在のセッションのみ表示
        </label>
        <button onClick={load} disabled={loading}>
          {loading ? "更新中..." : "更新"}
        </button>
        <a href={exportUrl} target="_blank" rel="noreferrer">
          CSVエクスポート
        </a>
      </div>
      <div className="log-table-wrap">
        <table className="log-table">
          <thead>
            <tr>
              <th>時刻</th>
              {SUMMARY_KEYS.map((key) => (
                <th key={key}>{summaryLabel(key)}</th>
              ))}
              <th>spec</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{new Date(log.ts).toLocaleTimeString()}</td>
                {SUMMARY_KEYS.map((key) => (
                  <td key={key}>{log.metrics[key]?.toFixed(3) ?? "-"}</td>
                ))}
                <td className="log-spec-version">{log.spec_version ?? "-"}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={SUMMARY_KEYS.length + 2} className="hint">
                  ログがありません
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
