/** Data access layer — live API or static JSON export (identical shapes). */

const STATIC = (import.meta as ImportMeta & { env: Record<string, string> }).env.VITE_STATIC_MODE === "1";
const STATIC_BASE = (import.meta as ImportMeta & { env: Record<string, string> }).env.VITE_STATIC_BASE || "/data";

type ApiEnvelope<T> = { data: T; error: string | null };

async function getLive<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as ApiEnvelope<T>;
  if (body.error) throw new Error(body.error);
  return body.data;
}

async function getStatic<T>(name: string): Promise<T> {
  const res = await fetch(`${STATIC_BASE}/${name}.json`);
  if (!res.ok) throw new Error(`Static missing: ${name}`);
  const body = (await res.json()) as ApiEnvelope<T> | T;
  if (body && typeof body === "object" && "data" in (body as object)) {
    return (body as ApiEnvelope<T>).data;
  }
  return body as T;
}

function qsKey(params?: Record<string, unknown>) {
  if (!params) return "default";
  return Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${k}=${v}`)
    .join("&") || "default";
}

export const dataLayer = {
  isStatic: STATIC,

  async leaderboard(params?: { phase?: string; model?: string; strategy?: string; budget?: number }) {
    if (STATIC) return getStatic<unknown[]>("leaderboard");
    return getLive<unknown[]>("/api/leaderboard", params);
  },

  async delta(params?: { phase?: string; budget?: number; strategy_a?: string; strategy_b?: string }) {
    if (STATIC) return getStatic<Record<string, unknown>>("delta");
    return getLive<Record<string, unknown>>("/api/delta", params as Record<string, string | number | undefined>);
  },

  async budgetCurves(params?: { phase?: string; model?: string }) {
    if (STATIC) return getStatic<Record<string, unknown>>("budget_curves");
    return getLive<Record<string, unknown>>("/api/budget-curves", params);
  },

  async runs(params?: Record<string, string | number | boolean | undefined>) {
    if (STATIC) {
      const all = await getStatic<unknown[]>("runs");
      return all;
    }
    return getLive<unknown[]>("/api/runs", params);
  },

  async run(runId: string) {
    if (STATIC) {
      const all = await getStatic<Array<{ id: string }>>("runs_full");
      return all.find((r) => r.id === runId) || null;
    }
    return getLive<Record<string, unknown>>(`/api/runs/${runId}`);
  },

  async transcript(runId: string) {
    if (STATIC) {
      const all = await getStatic<Record<string, unknown>>("transcripts");
      return (all as Record<string, unknown>)[runId] || null;
    }
    return getLive<Record<string, unknown>>(`/api/runs/${runId}/transcript`);
  },

  async tasks(params?: { phase?: string }) {
    if (STATIC) return getStatic<unknown[]>("tasks");
    return getLive<unknown[]>("/api/tasks", params);
  },

  async progress() {
    if (STATIC) return { status: "exported", completed: 0, total: 0, log_tail: [] };
    return getLive<Record<string, unknown>>("/api/progress");
  },

  async costSummary() {
    if (STATIC) return getStatic<Record<string, unknown>>("cost_summary");
    return getLive<Record<string, unknown>>("/api/cost/summary");
  },

  async strategies(params?: { phase?: string }) {
    if (STATIC) return getStatic<unknown[]>("strategies");
    return getLive<unknown[]>("/api/strategies", params);
  },

  async startSweep(body: Record<string, unknown>) {
    if (STATIC) throw new Error("Cannot start sweep in static mode");
    const res = await fetch("/api/sweeps/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async stopSweep(sweepId: string) {
    if (STATIC) throw new Error("Cannot stop sweep in static mode");
    const res = await fetch(`/api/sweeps/${sweepId}/stop`, { method: "POST" });
    return res.json();
  },

  async sweepPresets() {
    if (STATIC) return getStatic<Record<string, unknown>>("sweep_presets");
    return getLive<Record<string, unknown>>("/api/sweeps/presets");
  },
};

export { qsKey };
