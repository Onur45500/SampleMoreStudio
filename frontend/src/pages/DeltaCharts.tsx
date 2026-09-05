import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { dataLayer } from "../lib/dataLayer";
import { usePhase } from "../lib/phaseContext";

const PHASE1 = ["cot", "self_refine", "best_of_n", "majority_vote"];
const PHASE2 = ["react", "plan_then_act", "reflexion", "majority_of_n_agent"];
const COLORS = ["#6b8f71", "#d4843a", "#5b8fb8", "#c45c6a", "#9a7b4f", "#7dba8a"];

export default function DeltaCharts() {
  const { phase, apiPhase } = usePhase();
  const [budget, setBudget] = useState(512);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [showRefine, setShowRefine] = useState(false);

  useEffect(() => {
    dataLayer
      .delta({
        phase: apiPhase,
        budget,
        strategy_a: phase === "phase2_agent" ? "majority_of_n_agent" : "majority_vote",
        strategy_b: phase === "phase2_agent" ? "reflexion" : "self_refine",
      })
      .then(setData);
  }, [apiPhase, budget, phase]);

  const strategies = phase === "phase2_agent" ? PHASE2 : PHASE1;

  const chartData = useMemo(() => {
    const accs = (data?.strategy_accuracies as Record<string, unknown>[]) || [];
    const byModel: Record<string, Record<string, number>> = {};
    for (const a of accs) {
      const m = String(a.model);
      byModel[m] = byModel[m] || { model: m } as unknown as Record<string, number>;
      (byModel[m] as Record<string, unknown>)[String(a.strategy)] = Number(a.accuracy) * 100;
    }
    return Object.values(byModel);
  }, [data]);

  const paired = data?.paired_delta as Record<string, number> | undefined;
  const refine = data?.refine_before_after as Record<string, number> | undefined;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Delta Charts</h1>
          <p className="text-sm text-chalk/50 mt-1">The signature “reflect loses” view</p>
        </div>
        <label className="text-sm text-chalk/60">
          Budget{" "}
          <select
            className="ml-2 bg-ink-800 border border-white/10 rounded px-2 py-1"
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
          >
            {[256, 512, 1024, 2048].map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>
      </header>

      {paired && (
        <div className="rounded-lg border border-moss-500/30 bg-moss-600/10 p-5">
          <div className="text-[10px] uppercase tracking-widest text-moss-400 mb-1">Hero Δ</div>
          <p className="font-display text-xl text-chalk leading-snug">{String(data?.hero || "")}</p>
          <p className="text-xs text-chalk/45 mt-2 font-mono">
            Δ = {Number(paired.delta_pp).toFixed(1)} pp · 95% CI [{Number(paired.ci_low_pp).toFixed(1)},{" "}
            {Number(paired.ci_high_pp).toFixed(1)}] · pairs={paired.n_pairs}
          </p>
        </div>
      )}

      <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4 h-96">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff15" />
            <XAxis dataKey="model" stroke="#ffffff60" tick={{ fontSize: 11 }} />
            <YAxis stroke="#ffffff60" tick={{ fontSize: 11 }} unit="%" />
            <Tooltip
              contentStyle={{ background: "#1a2621", border: "1px solid #ffffff20" }}
              formatter={(v: number) => [`${v.toFixed(1)}%`, ""]}
            />
            <Legend />
            {strategies.map((s, i) => (
              <Bar key={s} dataKey={s} fill={COLORS[i % COLORS.length]} radius={[2, 2, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setShowRefine(!showRefine)}
          className="text-sm px-3 py-1.5 border border-white/15 rounded hover:bg-white/5"
        >
          {showRefine ? "Hide" : "Show"} refine before/after
        </button>
      </div>

      {showRefine && refine && (
        <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4">
          <h2 className="text-sm uppercase tracking-wider text-chalk/45 mb-3">
            Does self-refine improve over its own initial draft?
          </h2>
          <div className="grid sm:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xs text-chalk/40">Initial draft</div>
              <div className="font-display text-2xl text-ember-400">
                {(Number(refine.initial_accuracy) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-chalk/40">After refine</div>
              <div className="font-display text-2xl text-moss-400">
                {(Number(refine.final_accuracy) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-chalk/40">Δpp</div>
              <div className="font-display text-2xl">{Number(refine.delta_pp).toFixed(1)}</div>
              <div className="text-xs text-chalk/40">n={refine.n}</div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
