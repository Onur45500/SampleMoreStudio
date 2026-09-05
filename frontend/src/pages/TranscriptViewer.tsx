import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { dataLayer } from "../lib/dataLayer";
import TranscriptTurnList from "../components/TranscriptTurnList";
import SideBySideCompare from "../components/SideBySideCompare";

type TranscriptPayload = {
  run_id?: string;
  transcript?: Turn[];
  final_answer?: string;
  expected_answer?: string;
  correct?: number;
  tokens_spent?: number;
  target_budget?: number;
  overshoot_flagged?: number;
  strategy?: string;
  model?: string;
  task_id?: string;
  budget?: number;
};

export type Turn = {
  role: string;
  content: string;
  tokens: number;
  label?: string | null;
  truncated?: boolean;
  prompt_tokens?: number;
};

export default function TranscriptViewer({ compare = false }: { compare?: boolean }) {
  const { runId } = useParams();
  const [params] = useSearchParams();
  const [data, setData] = useState<TranscriptPayload | null>(null);
  const [dataB, setDataB] = useState<TranscriptPayload | null>(null);

  useEffect(() => {
    if (compare) {
      const a = params.get("a");
      const b = params.get("b");
      if (a) dataLayer.transcript(a).then((d) => setData(d as TranscriptPayload));
      if (b) dataLayer.transcript(b).then((d) => setDataB(d as TranscriptPayload));
    } else if (runId) {
      dataLayer.transcript(runId).then((d) => setData(d as TranscriptPayload));
    }
  }, [runId, compare, params]);

  if (compare) {
    return (
      <div className="space-y-4">
        <h1 className="font-display text-3xl">Side-by-side compare</h1>
        <SideBySideCompare left={data} right={dataB} />
      </div>
    );
  }

  if (!data) return <p className="text-chalk/50">Loading transcript…</p>;

  const target = Number(data.target_budget || data.budget || 0);
  const spent = Number(data.tokens_spent || 0);
  const pct = target ? Math.min(100, Math.round((spent / target) * 100)) : 0;
  const over = Boolean(data.overshoot_flagged);

  return (
    <div className="space-y-4 max-w-4xl">
      <header>
        <h1 className="font-display text-3xl">Transcript</h1>
        <p className="text-sm text-chalk/50 mt-1 font-mono">
          {data.model} · {data.strategy} · {data.task_id} · B={data.budget}
        </p>
      </header>

      <div className="rounded-lg border border-white/10 bg-ink-900/50 p-4 flex flex-wrap gap-6 items-center">
        <div>
          <div className="text-xs text-chalk/40">Final / expected</div>
          <div className="font-mono text-sm">
            <span className={data.correct ? "text-moss-400" : "text-ember-400"}>
              {data.final_answer || "—"}
            </span>
            <span className="text-chalk/30"> / </span>
            <span>{data.expected_answer}</span>
            <span className="ml-2">{data.correct ? "✓" : "✗"}</span>
          </div>
        </div>
        <div className="flex-1 min-w-[180px]">
          <div className="text-xs text-chalk/40 mb-1">
            Tokens {spent} / {target} {over ? "(OVERSHOOT)" : ""}
          </div>
          <div className="h-2 rounded-full bg-ink-800 overflow-hidden">
            <div
              className={`h-full ${over ? "bg-ember-500" : "bg-moss-500"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>

      <TranscriptTurnList turns={data.transcript || []} strategy={data.strategy} />
    </div>
  );
}
