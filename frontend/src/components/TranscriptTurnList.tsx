import type { Turn } from "../pages/TranscriptViewer";

function roleColor(role: string) {
  switch (role) {
    case "system":
      return "border-white/10 text-chalk/50";
    case "user":
      return "border-sky-500/30 text-sky-200/80";
    case "assistant":
      return "border-moss-500/30 text-chalk";
    case "tool_call":
      return "border-ember-500/40 text-ember-400";
    case "tool_result":
      return "border-amber-500/30 text-amber-100/80";
    default:
      return "border-white/10";
  }
}

export default function TranscriptTurnList({
  turns,
  strategy,
}: {
  turns: Turn[];
  strategy?: string;
}) {
  return (
    <div className="space-y-3">
      {turns.map((t, i) => (
        <article
          key={i}
          className={`rounded-lg border bg-ink-900/40 p-3 ${roleColor(t.role)} ${
            t.label === "final_vote" || t.label === "self_selection" ? "ring-1 ring-moss-500/40" : ""
          }`}
        >
          <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wider mb-2 opacity-70">
            <span>{t.role}</span>
            {t.label && <span className="font-mono normal-case tracking-normal text-moss-400">{t.label}</span>}
            <span className="font-mono normal-case tracking-normal ml-auto">
              {t.tokens} tok
              {t.truncated ? " · TRUNC" : ""}
            </span>
          </div>
          <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed opacity-90">
            {t.content}
          </pre>
        </article>
      ))}
      {!turns.length && <p className="text-chalk/40 text-sm">Empty transcript.</p>}
      {strategy && (
        <p className="text-[10px] text-chalk/30">
          Strategy view hints: Self-Refine shows critique→revision chains; Majority-Vote groups samples
          then final_vote; ReAct shows tool_call / tool_result pairs.
        </p>
      )}
    </div>
  );
}
