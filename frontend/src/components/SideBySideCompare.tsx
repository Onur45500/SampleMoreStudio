import TranscriptTurnList from "./TranscriptTurnList";
import type { Turn } from "../pages/TranscriptViewer";

type Payload = {
  transcript?: Turn[];
  final_answer?: string;
  expected_answer?: string;
  correct?: number;
  tokens_spent?: number;
  target_budget?: number;
  strategy?: string;
  model?: string;
  task_id?: string;
} | null;

function Panel({ title, data, accent }: { title: string; data: Payload; accent: string }) {
  if (!data) return <div className="text-chalk/40 p-4">Loading {title}…</div>;
  return (
    <div className="space-y-3">
      <div className={`rounded-lg border p-3 ${accent}`}>
        <div className="text-xs uppercase tracking-wider opacity-60">{title}</div>
        <div className="font-mono text-xs mt-1">
          {data.model} · {data.strategy} · {data.task_id}
        </div>
        <div className="mt-2 text-sm">
          <span className={data.correct ? "text-moss-400" : "text-ember-400"}>
            {data.final_answer || "—"} {data.correct ? "✓" : "✗"}
          </span>
          <span className="text-chalk/30"> vs </span>
          {data.expected_answer}
        </div>
        <div className="text-xs font-mono text-chalk/45 mt-1">
          tokens {data.tokens_spent}/{data.target_budget}
        </div>
      </div>
      <TranscriptTurnList turns={data.transcript || []} strategy={data.strategy} />
    </div>
  );
}

export default function SideBySideCompare({ left, right }: { left: Payload; right: Payload }) {
  return (
    <div className="grid lg:grid-cols-2 gap-4">
      <Panel title="Run A" data={left} accent="border-moss-500/40 bg-moss-600/5" />
      <Panel title="Run B" data={right} accent="border-ember-500/40 bg-ember-500/5" />
    </div>
  );
}
