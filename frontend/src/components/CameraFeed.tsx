import { useEffect, useRef } from "react";
import { useCamera } from "../hooks/useCamera";

interface CameraFeedProps {
  connected: boolean;
  intervalMs: number;
  logging: boolean;
  onFrame: (imageBase64: string, log: boolean) => void;
  onActiveChange: (active: boolean) => void;
}

export function CameraFeed({ connected, intervalMs, logging, onFrame, onActiveChange }: CameraFeedProps) {
  const { videoRef, active, error, start, stop } = useCamera();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    onActiveChange(active);
  }, [active, onActiveChange]);

  useEffect(() => {
    if (!active || !connected) {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    intervalRef.current = window.setInterval(() => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) return;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.75);
      onFrame(dataUrl, logging);
    }, intervalMs);

    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, connected, intervalMs, logging]);

  return (
    <div className="camera-feed">
      <video ref={videoRef} className="camera-video" muted playsInline />
      <canvas ref={canvasRef} style={{ display: "none" }} />
      <div className="camera-controls">
        {!active ? (
          <button onClick={start}>カメラ開始</button>
        ) : (
          <button onClick={stop}>カメラ停止</button>
        )}
        {error && <span className="camera-error">{error}</span>}
      </div>
    </div>
  );
}
