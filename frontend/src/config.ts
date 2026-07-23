const rawApiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const API_BASE_URL = rawApiBase.replace(/\/$/, "");
export const WS_URL = `${API_BASE_URL.replace(/^http/, "ws")}/ws/analyze`;
