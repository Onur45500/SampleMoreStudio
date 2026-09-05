import { useEffect, useRef, useState } from "react";

export default function LogTail({ logs }: { logs: { ts: number; msg: string }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (!paused && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [logs, paused]);

  return (
    <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm uppercase tracking-wider text-chalk/45">Log tail</h2>
        <span className="text-[10px] text-chalk/35">{paused ? "paused" : "auto-scroll"}</span>
      </div>
      <div
        ref={ref}
        onScroll={() => {
          const el = ref.current;
          if (!el) return;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
          setPaused(!atBottom);
        }}
        className="h-64 overflow-y-auto font-mono text-[11px] leading-relaxed text-chalk/65 space-y-1"
      >
        {logs.length === 0 && <div className="text-chalk/35">No log lines yet.</div>}
        {logs.map((l, i) => (
          <div key={i}>
            <span className="text-chalk/30">{new Date(l.ts * 1000).toLocaleTimeString()} </span>
            {l.msg}
          </div>
        ))}
      </div>
    </section>
  );
}
