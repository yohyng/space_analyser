import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config";
import type { MetricSchemaItem } from "../types";

export function useMetricSchema() {
  const [schema, setSchema] = useState<MetricSchemaItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/metrics/schema`)
      .then((res) => {
        if (!res.ok) throw new Error(`schema fetch failed: ${res.status}`);
        return res.json() as Promise<MetricSchemaItem[]>;
      })
      .then((data) => {
        if (!cancelled) setSchema(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { schema, error };
}
