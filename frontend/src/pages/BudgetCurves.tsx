import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { dataLayer } from "../lib/dataLayer";
import { usePhase } from "../lib/phaseContext";

const COLORS = ["#6b8f71", "#d4843a", "#5b8fb8", "#c45c6a", "#9a7b4f", "#7dba8a", "#a78bfa"];

export default function BudgetCurves() {
  const { apiPhase } = usePhase();
  const [curves, setCurves] = useState<Record<string, { budget: number; accuracy: number }[]>>({});

  useEffect(() => {
    dataLayer.budgetCurves({ phase: apiPhase }).then((c) => setCurves(c as typeof curves));
  }, [apiPhase]);

  const chartData = useMemo(() => {
    const budgets = new Set<number>();
    Object.values(curves).forEach((pts) => pts.forEach((p) => budgets.add(p.budget)));
    return [...budgets]
      .sort((a, b) => a - b)
      .map((b) => {
        const row: Record<string, number> = { budget: b };
        for (const [strat, pts] of Object.entries(curves)) {
          const hit = pts.find((p) => p.budget === b);
          if (hit) row[strat] = hit.accuracy * 100;
        }
        return row;
      });
  }, [curves]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="font-display text-3xl">Budget Curves</h1>
        <p className="text-sm text-chalk/50 mt-1">
          Does sampling-beats-reflecting hold as budget grows?
        </p>
      </header>
      <section className="rounded-lg border border-white/10 bg-ink-900/50 p-4 h-96">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff15" />
            <XAxis dataKey="budget" stroke="#ffffff60" tick={{ fontSize: 11 }} />
            <YAxis stroke="#ffffff60" tick={{ fontSize: 11 }} unit="%" />
            <Tooltip contentStyle={{ background: "#1a2621", border: "1px solid #ffffff20" }} />
            <Legend />
            {Object.keys(curves).map((s, i) => (
              <Line
                key={s}
                type="monotone"
                dataKey={s}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}
