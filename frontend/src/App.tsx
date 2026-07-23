import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { CameraFeed } from "./components/CameraFeed";
import { LogHistory } from "./components/LogHistory";
import { MetricsGrid, type HistoryPoint } from "./components/MetricsGrid";
import { useAnalysisSocket } from "./hooks/useAnalysisSocket";
import { useMetricSchema } from "./hooks/useMetricSchema";
import type { MetricsRecord, WsResultMessage } from "./types";

const MAX_HISTORY = 200;
const INTERVAL_OPTIONS = [
  { label: "0.2秒", value: 200 },
  { label: "0.5秒", value: 500 },
  { label: "1秒", value: 1000 },
  { label: "2秒", value: 2000 },
];

function App() {
  const { schema } = useMetricSchema();
  const [latestMetrics, setLatestMetrics] = useState<MetricsRecord | null>(null);
  const [specVersion, setSpecVersion] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [cameraActive, setCameraActive] = useState(false);
  const [intervalMs, setIntervalMs] = useState(500);
  const [logging, setLogging] = useState(true);
  const [refreshSignal, setRefreshSignal] = useState(0);
  const indexRef = useRef(0);

  const handleResult = useCallback((result: WsResultMessage) => {
    setLatestMetrics(result.metrics);
    setSpecVersion(result.spec_version);
    setHistory((prev) => {
      const next = [...prev, { index: indexRef.current++, ts: result.ts, metrics: result.metrics }];
      return next.length > MAX_HISTORY ? next.slice(next.length - MAX_HISTORY) : next;
    });
  }, []);

  const { status, sessionId, connect, disconnect, sendFrame } = useAnalysisSocket({ onResult: handleResult });

  useEffect(() => {
    if (cameraActive) {
      connect();
    } else {
      disconnect();
    }
  }, [cameraActive, connect, disconnect]);

  useEffect(() => {
    if (status !== "open") return;
    const timer = window.setInterval(() => setRefreshSignal((s) => s + 1), 5000);
    return () => window.clearInterval(timer);
  }, [status]);

  const connected = status === "open";
  const statusLabel: Record<string, string> = {
    idle: "未接続",
    connecting: "接続中...",
    open: "接続済み",
    closed: "切断",
    error: "エラー",
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Space Analyser</h1>
        <p className="hint">
          カメラ映像から空間の定量指標をリアルタイムに解析・記録します。カメラを開始すると自動的に解析サーバーへ接続します。
        </p>
      </header>

      <div className="top-grid">
        <CameraFeed
          connected={connected}
          intervalMs={intervalMs}
          logging={logging}
          onFrame={sendFrame}
          onActiveChange={setCameraActive}
        />

        <div className="control-panel">
          <div className="status-row">
            <span className={`status-dot status-${status}`} />
            解析サーバー: {statusLabel[status]}
            {specVersion && <span className="spec-version">spec: {specVersion}</span>}
            {sessionId && <span className="session-id">session: {sessionId.slice(0, 8)}</span>}
          </div>
          <label className="control-row">
            送信間隔
            <select value={intervalMs} onChange={(e) => setIntervalMs(Number(e.target.value))}>
              {INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="control-row">
            <input type="checkbox" checked={logging} onChange={(e) => setLogging(e.target.checked)} />
            結果をログに記録する
          </label>
        </div>
      </div>

      <section>
        <h2>指標</h2>
        <MetricsGrid schema={schema} latestMetrics={latestMetrics} history={history} />
      </section>

      <section>
        <h2>ログ履歴</h2>
        <LogHistory sessionId={sessionId} schema={schema} refreshSignal={refreshSignal} />
      </section>
    </div>
  );
}

export default App;
