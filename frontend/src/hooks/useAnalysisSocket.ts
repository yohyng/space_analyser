import { useCallback, useRef, useState } from "react";
import { WS_URL } from "../config";
import type { WsMessage, WsResultMessage } from "../types";

export type SocketStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface UseAnalysisSocketOptions {
  onResult: (result: WsResultMessage) => void;
}

export function useAnalysisSocket({ onResult }: UseAnalysisSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<SocketStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
      return;
    }
    setStatus("connecting");
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setStatus("open");
    ws.onerror = () => setStatus("error");
    ws.onclose = () => {
      setStatus("closed");
      wsRef.current = null;
    };
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WsMessage;
        if (message.type === "session") {
          setSessionId(message.session_id);
        } else if (message.type === "result") {
          onResultRef.current(message);
        }
      } catch {
        // ignore malformed messages
      }
    };
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("closed");
    setSessionId(null);
  }, []);

  const sendFrame = useCallback((imageBase64: string, log: boolean) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ type: "frame", image: imageBase64, log }));
    return true;
  }, []);

  return { status, sessionId, connect, disconnect, sendFrame };
}
