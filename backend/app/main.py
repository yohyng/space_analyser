from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import db
from .metrics import METRIC_DEFINITIONS, FrameAnalyzer

app = FastAPI(title="Space Analyser API")

_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
_allowed_origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/metrics/schema")
def metrics_schema() -> list[dict]:
    return [
        {
            "key": m.key,
            "label": m.label_ja,
            "unit": m.unit,
            "group": m.group,
            "description": m.description_ja,
        }
        for m in METRIC_DEFINITIONS
    ]


@app.get("/api/sessions")
def sessions() -> list[dict]:
    return db.fetch_sessions()


@app.get("/api/logs")
def logs(limit: int = 100, offset: int = 0, session_id: Optional[str] = None) -> list[dict]:
    limit = max(1, min(limit, 1000))
    return db.fetch_logs(limit=limit, offset=offset, session_id=session_id)


@app.get("/api/logs/export.csv")
def export_logs(session_id: Optional[str] = None) -> PlainTextResponse:
    csv_data = db.export_csv(session_id=session_id)
    return PlainTextResponse(
        csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=space_analyser_logs.csv"},
    )


def _decode_frame(image_data: str) -> Optional[np.ndarray]:
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    try:
        raw = base64.b64decode(image_data)
    except Exception:
        return None
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame


@app.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = str(uuid.uuid4())
    analyzer = FrameAnalyzer()
    await websocket.send_text(json.dumps({"type": "session", "session_id": session_id}))

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            if message.get("type") != "frame":
                continue

            frame = _decode_frame(message.get("image", ""))
            if frame is None:
                await websocket.send_text(json.dumps({"type": "error", "message": "invalid image"}))
                continue

            metrics = analyzer.analyze(frame)
            ts = datetime.now(timezone.utc).isoformat()

            should_log = message.get("log", True)
            log_id = None
            if should_log:
                log_id = db.insert_log(session_id, ts, metrics)

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "result",
                        "session_id": session_id,
                        "ts": ts,
                        "log_id": log_id,
                        "metrics": metrics,
                    }
                )
            )
    except WebSocketDisconnect:
        return
