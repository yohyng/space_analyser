export interface MetricSchemaItem {
  key: string;
  label: string;
  unit: string;
  group: string;
  description: string;
  core: boolean;
}

export type MetricsRecord = Record<string, number>;

export interface WsSessionMessage {
  type: "session";
  session_id: string;
}

export interface WsResultMessage {
  type: "result";
  session_id: string;
  ts: string;
  log_id: number | null;
  spec_version: string;
  metrics: MetricsRecord;
}

export interface WsErrorMessage {
  type: "error";
  message: string;
}

export type WsMessage = WsSessionMessage | WsResultMessage | WsErrorMessage;

export interface LogEntry {
  id: number;
  session_id: string;
  ts: string;
  spec_version: string | null;
  metrics: MetricsRecord;
}

export interface SessionSummary {
  session_id: string;
  count: number;
  started_at: string;
  ended_at: string;
}
