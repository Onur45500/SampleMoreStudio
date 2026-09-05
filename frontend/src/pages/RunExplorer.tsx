import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { dataLayer } from "../lib/dataLayer";
import { usePhase } from "../lib/phaseContext";

type Row = Record<string, unknown>;

export default function RunExplorer() {
  const { apiPhase } = usePhase();
  const [rows, setRows] = useState<Row[]>([]);
  const [strategy, setStrategy] = useState("");
  const [correct, setCorrect] = useState<string>("");
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");

  useEffect(() => {
    dataLayer
      .runs({
        phase: apiPhase,
        strategy: strategy || undefined,
        correct: correct === "" ? undefined : correct === "1",
        limit: 300,
      })
      .then((r) => setRows(r as Row[]));
  }, [apiPhase, strategy, correct]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl">Run Explorer</h1>
          <p className="text-sm text-chalk/50 mt-1">Every individual run — click to open transcript</p>
        </div>
        <div className="flex gap-2 text-sm">
          <input
            placeholder="strategy filter"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="bg-ink-800 border border-white/10 rounded px-2 py-1"
          />
          <select
            value={correct}
            onChange={(e) => setCorrect(e.target.value)}
            className="bg-ink-800 border border-white/10 rounded px-2 py-1"
          >
            <option value="">all</option>
            <option value="1">correct</option>
            <option value="0">incorrect</option>
          </select>
          {compareA && compareB && (
            <Link
              to={`/compare?a=${compareA}&b=${compareB}`}
              className="px-3 py-1 rounded bg-moss-600/40 text-moss-400"
            >
              Compare A/B
            </Link>
          )}
        </div>
      </header>

      <div className="overflow-x-auto rounded-lg border border-white/10 bg-ink-900/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-chalk/40 border-b border-white/10">
              <th className="py-2 px-2">A/B</th>
              <th className="py-2 px-2">Model</th>
              <th className="py-2 px-2">Strategy</th>
              <th className="py-2 px-2">Task</th>
              <th className="py-2 px-2">Budget</th>
              <th className="py-2 px-2">Correct</th>
              <th className="py-2 px-2">Tokens</th>
              <th className="py-2 px-2">Flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const id = String(r.id);
              return (
                <tr key={id} className="border-b border-white/5 hover:bg-white/[0.03]">
                  <td className="py-2 px-2">
                    <button
                      className={`text-xs mr-1 ${compareA === id ? "text-moss-400" : "text-chalk/40"}`}
                      onClick={() => setCompareA(id)}
                    >
                      A
                    </button>
                    <button
                      className={`text-xs ${compareB === id ? "text-ember-400" : "text-chalk/40"}`}
                      onClick={() => setCompareB(id)}
                    >
                      B
                    </button>
                  </td>
                  <td className="py-2 px-2 font-mono text-xs">
                    <Link to={`/runs/${id}`} className="hover:text-moss-400">
                      {String(r.model)}
                    </Link>
                  </td>
                  <td className="py-2 px-2">{String(r.strategy)}</td>
                  <td className="py-2 px-2 font-mono text-xs">{String(r.task_id)}</td>
                  <td className="py-2 px-2 font-mono">{String(r.budget)}</td>
                  <td className="py-2 px-2">{r.correct ? "✓" : "✗"}</td>
                  <td className="py-2 px-2 font-mono text-xs">
                    {String(r.tokens_spent)}/{String(r.target_budget)}
                  </td>
                  <td className="py-2 px-2 text-xs text-ember-400">
                    {r.overshoot_flagged ? "overshoot " : ""}
                    {r.budget_exhausted ? "exhausted " : ""}
                    {r.truncated_any ? "trunc" : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
