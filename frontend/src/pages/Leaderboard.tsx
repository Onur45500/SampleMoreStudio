import { useEffect, useMemo, useState } from "react";
import { dataLayer } from "../lib/dataLayer";
import { usePhase } from "../lib/phaseContext";

type Row = Record<string, unknown>;

export default function Leaderboard() {
  const { apiPhase } = usePhase();
  const [rows, setRows] = useState<Row[]>([]);
  const [sortKey, setSortKey] = useState("accuracy");
  const [asc, setAsc] = useState(false);

  useEffect(() => {
    dataLayer.leaderboard({ phase: apiPhase }).then((r) => setRows(r as Row[]));
  }, [apiPhase]);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = Number(a[sortKey] ?? 0);
      const bv = Number(b[sortKey] ?? 0);
      if (typeof a[sortKey] === "string") {
        return asc
          ? String(a[sortKey]).localeCompare(String(b[sortKey]))
          : String(b[sortKey]).localeCompare(String(a[sortKey]));
      }
      return asc ? av - bv : bv - av;
    });
    return copy;
  }, [rows, sortKey, asc]);

  const exportCsv = () => {
    const headers = [
      "phase",
      "model",
      "strategy",
      "budget",
      "accuracy",
      "n_runs",
      "avg_tokens_spent",
      "avg_tool_calls",
      "truncation_rate",
      "n_or_k",
      "per_sample_cap",
    ];
    const lines = [headers.join(",")].concat(
      sorted.map((r) => headers.map((h) => JSON.stringify(r[h] ?? "")).join(","))
    );
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "leaderboard.csv";
    a.click();
  };

  const clickSort = (k: string) => {
    if (sortKey === k) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(false);
    }
  };

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl">Leaderboard</h1>
          <p className="text-sm text-chalk/50 mt-1">One row per (model, strategy, budget)</p>
        </div>
        <button onClick={exportCsv} className="text-sm px-3 py-1.5 border border-white/15 rounded hover:bg-white/5">
          CSV export
        </button>
      </header>
      <div className="overflow-x-auto rounded-lg border border-white/10 bg-ink-900/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-chalk/40 border-b border-white/10">
              {[
                "model",
                "strategy",
                "phase",
                "budget",
                "accuracy",
                "avg_tokens_spent",
                "n_or_k",
                "per_sample_cap",
                "truncation_rate",
                "avg_tool_calls",
                "n_runs",
                "n_overshoot",
              ].map((k) => (
                  <th key={k} className="py-2 px-3 cursor-pointer" onClick={() => clickSort(k)}>
                    {k.replace(/_/g, " ")}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={i} className="border-b border-white/5">
                <td className="py-2 px-3 font-mono text-xs">{String(r.model)}</td>
                <td className="py-2 px-3">{String(r.strategy)}</td>
                <td className="py-2 px-3 text-xs text-chalk/50">{String(r.phase)}</td>
                <td className="py-2 px-3 font-mono">{String(r.budget)}</td>
                <td className="py-2 px-3 font-mono text-moss-400">{(Number(r.accuracy) * 100).toFixed(1)}%</td>
                <td className="py-2 px-3 font-mono text-xs">
                  {Number(r.avg_tokens_spent || 0).toFixed(0)} / {Number(r.avg_target_budget || 0).toFixed(0)}
                </td>
                <td className="py-2 px-3 font-mono text-xs">{String(r.n_or_k ?? "—")}</td>
                <td className="py-2 px-3 font-mono text-xs">{String(r.per_sample_cap ?? "—")}</td>
                <td className="py-2 px-3 font-mono text-xs">
                  {(Number(r.truncation_rate || 0) * 100).toFixed(0)}%
                </td>
                <td className="py-2 px-3 font-mono text-xs">{Number(r.avg_tool_calls || 0).toFixed(1)}</td>
                <td className="py-2 px-3 font-mono text-xs">{String(r.n_runs)}</td>
                <td className="py-2 px-3 font-mono text-xs text-ember-400">{String(r.n_overshoot || 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
