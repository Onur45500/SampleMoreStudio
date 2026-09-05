import { useEffect, useState } from "react";
import { dataLayer } from "../lib/dataLayer";
import { usePhase } from "../lib/phaseContext";

type Task = {
  id: string;
  category: string;
  prompt: string;
  pass_rate: number | null;
  n_runs: number;
  phase: string;
};

export default function TaskBrowser() {
  const { apiPhase } = usePhase();
  const [tasks, setTasks] = useState<Task[]>([]);

  useEffect(() => {
    dataLayer.tasks({ phase: apiPhase }).then((t) => setTasks(t as Task[]));
  }, [apiPhase]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="font-display text-3xl">Task Browser</h1>
        <p className="text-sm text-chalk/50 mt-1">{tasks.length} tasks · pass-rate across runs</p>
      </header>
      <div className="overflow-x-auto rounded-lg border border-white/10 bg-ink-900/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-chalk/40 border-b border-white/10">
              <th className="py-2 px-3">ID</th>
              <th className="py-2 px-3">Category</th>
              <th className="py-2 px-3">Prompt</th>
              <th className="py-2 px-3">Pass rate</th>
              <th className="py-2 px-3">n</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id} className="border-b border-white/5 align-top">
                <td className="py-2 px-3 font-mono text-xs whitespace-nowrap">{t.id}</td>
                <td className="py-2 px-3 text-xs">{t.category}</td>
                <td className="py-2 px-3 text-xs text-chalk/70 max-w-xl">
                  {t.prompt.slice(0, 140)}
                  {t.prompt.length > 140 ? "…" : ""}
                </td>
                <td className="py-2 px-3 font-mono text-xs">
                  {t.pass_rate == null ? "—" : `${(t.pass_rate * 100).toFixed(0)}%`}
                  <div className="mt-1 h-1.5 w-20 rounded bg-ink-800 overflow-hidden">
                    <div
                      className="h-full bg-moss-500"
                      style={{ width: `${(t.pass_rate || 0) * 100}%` }}
                    />
                  </div>
                </td>
                <td className="py-2 px-3 font-mono text-xs">{t.n_runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
