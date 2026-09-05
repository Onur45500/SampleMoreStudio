import { useEffect, useRef, useState } from "react";
import { dataLayer } from "../lib/dataLayer";
import { usePhase } from "../lib/phaseContext";
import LiveLeaderboardTable from "../components/LiveLeaderboardTable";
import LogTail from "../components/LogTail";
import RunProgressPanel from "../components/RunProgressPanel";

function formatEta(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

export default function Dashboard() {
  const { apiPhase } = usePhase();
  const [progress, setProgress] = useState<Record<string, unknown> | null>(null);
  const [cost, setCost] = useState<Record<string, unknown> | null>(null);
  const [leaderboard, setLeaderboard] = useState<unknown[]>([]);
  const [presets, setPresets] = useState<Record<string, Record<string, unknown>>>({});
  const [preset, setPreset] = useState("phase0");
  const [starting, setStarting] = useState(false);
  const timer = useRef<number | null>(null);

  const refresh = async () => {
    try {
      const [p, c, lb] = await Promise.all([
        dataLayer.progress(),
        dataLayer.costSummary(),
        dataLayer.leaderboard({ phase: apiPhase }),
      ]);
      setProgress(p);
      setCost(c);
      setLeaderboard(lb as unknown[]);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    dataLayer.sweepPresets().then((p) => {
      const obj = p as Record<string, Record<string, unknown>>;
      setPresets(obj);
      if (obj.phase0) setPreset("phase0");
      else {
        const keys = Object.keys(obj);
        if (keys.length) setPreset(keys[0]);
      }
    });
  }, []);

  useEffect(() => {
    refresh();
    timer.current = window.setInterval(refresh, 2000);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [apiPhase]);

  const startSweep = async () => {
    setStarting(true);
    try {
      await dataLayer.startSweep({ preset });
      await refresh();
    } catch (e) {
      alert(String(e));
    } finally {
      setStarting(false);
    }
  };

  const stopSweep = async () => {
    const id = String(progress?.sweep_id || "current");
    await dataLayer.stopSweep(id);
    await refresh();
  };

  const completed = Number(progress?.completed || 0);
  const total = Number(progress?.total || 0);
  const pct = total ? Math.round((completed / total) * 100) : 0;
  const eta = formatEta(progress?.eta_seconds as number | undefined);
  const presetDesc = presets[preset]?.description
    ? String(presets[preset].description)
    : "";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-chalk">Live Run Monitor</h1>
          <p className="text-chalk/55 text-sm mt-1">
            Polling every 2s · ETA {eta} · equal-cost strategy sweeps
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={preset}
            onChange={(e) => setPreset(e.target.value)}
            className="bg-ink-800 border border-white/10 rounded px-2 py-1.5 text-sm"
            disabled={progress?.status === "running"}
          >
            {Object.keys(presets).map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <button
            onClick={startSweep}
            disabled={starting || progress?.status === "running" || dataLayer.isStatic}
            className="px-3 py-1.5 rounded bg-moss-600 text-white text-sm disabled:opacity-40"
          >
            Start preset
          </button>
          <button
            onClick={stopSweep}
            disabled={progress?.status !== "running"}
            className="px-3 py-1.5 rounded border border-ember-500/50 text-ember-400 text-sm disabled:opacity-40"
          >
            Stop
          </button>
        </div>
      </header>

      {presetDesc && <p className="text-xs text-chalk/45 -mt-3">{presetDesc}</p>}

      <RunProgressPanel progress={progress} pct={pct} />

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4">
            <h2 className="text-sm uppercase tracking-wider text-chalk/45 mb-3">Live leaderboard</h2>
            <LiveLeaderboardTable rows={leaderboard as Record<string, unknown>[]} />
          </section>
        </div>
        <div className="space-y-4">
          <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4">
            <h2 className="text-sm uppercase tracking-wider text-chalk/45 mb-3">Cost / tokens</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-chalk/40 text-xs">Completion toks</dt>
                <dd className="font-mono text-moss-400">
                  {Number(cost?.total_completion_tokens || 0).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-chalk/40 text-xs">Prompt toks</dt>
                <dd className="font-mono">{Number(cost?.total_prompt_tokens || 0).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-chalk/40 text-xs">Est. API $</dt>
                <dd className="font-mono text-ember-400">${Number(cost?.total_cost || 0).toFixed(4)}</dd>
              </div>
              <div>
                <dt className="text-chalk/40 text-xs">Local / API</dt>
                <dd className="font-mono">
                  {Number(cost?.local_runs || 0)} / {Number(cost?.api_runs || 0)}
                </dd>
              </div>
            </dl>
          </section>
          <LogTail logs={(progress?.log_tail as { ts: number; msg: string }[]) || []} />
        </div>
      </div>
    </div>
  );
}
