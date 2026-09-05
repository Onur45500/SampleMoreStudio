export default function LiveLeaderboardTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) {
    return <p className="text-sm text-chalk/45">No results yet — start a sweep.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-chalk/40 border-b border-white/10">
            <th className="py-2 pr-3">Model</th>
            <th className="py-2 pr-3">Strategy</th>
            <th className="py-2 pr-3">Budget</th>
            <th className="py-2 pr-3">Accuracy</th>
            <th className="py-2 pr-3">N/K</th>
            <th className="py-2 pr-3">Trunc%</th>
            <th className="py-2 pr-3">Tokens</th>
            <th className="py-2">n</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 20).map((r, i) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/[0.03]">
              <td className="py-2 pr-3 font-mono text-xs">{String(r.model)}</td>
              <td className="py-2 pr-3">{String(r.strategy)}</td>
              <td className="py-2 pr-3 font-mono">{String(r.budget)}</td>
              <td className="py-2 pr-3 text-moss-400 font-mono">
                {(Number(r.accuracy) * 100).toFixed(1)}%
              </td>
              <td className="py-2 pr-3 font-mono text-xs">{String(r.n_or_k ?? "—")}</td>
              <td className="py-2 pr-3 font-mono text-xs">
                {(Number(r.truncation_rate || 0) * 100).toFixed(0)}%
              </td>
              <td className="py-2 pr-3 font-mono text-xs text-chalk/60">
                {Number(r.avg_tokens_spent || 0).toFixed(0)}/{Number(r.avg_target_budget || 0).toFixed(0)}
              </td>
              <td className="py-2 font-mono text-xs">{String(r.n_runs)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
