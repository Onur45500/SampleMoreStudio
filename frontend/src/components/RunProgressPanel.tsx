export default function RunProgressPanel({
  progress,
  pct,
}: {
  progress: Record<string, unknown> | null;
  pct: number;
}) {
  return (
    <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="text-sm">
          Status:{" "}
          <span className="font-mono text-moss-400">{String(progress?.status || "idle")}</span>
          {progress?.sweep_id ? (
            <span className="text-chalk/40 font-mono text-xs ml-2">{String(progress.sweep_id)}</span>
          ) : null}
        </div>
        <div className="font-mono text-sm text-chalk/70">
          {Number(progress?.completed || 0)} / {Number(progress?.total || 0)} ({pct}%)
          {progress?.eta_seconds != null ? (
            <span className="text-chalk/40 ml-2">
              ETA{" "}
              {(() => {
                const s = Math.round(Number(progress.eta_seconds));
                const h = Math.floor(s / 3600);
                const m = Math.floor((s % 3600) / 60);
                if (h > 0) return `${h}h ${m}m`;
                if (m > 0) return `${m}m`;
                return `${s}s`;
              })()}
            </span>
          ) : null}
        </div>
      </div>
      <div className="h-2 rounded-full bg-ink-800 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-moss-600 to-moss-400 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-3 grid sm:grid-cols-4 gap-2 text-xs text-chalk/60 font-mono">
        <div>model: {String(progress?.current_model || "—")}</div>
        <div>strategy: {String(progress?.current_strategy || "—")}</div>
        <div>task: {String(progress?.current_task || "—")}</div>
        <div>budget: {progress?.current_budget != null ? String(progress.current_budget) : "—"}</div>
      </div>
    </section>
  );
}
