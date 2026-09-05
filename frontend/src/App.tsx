import { NavLink, Route, Routes } from "react-router-dom";
import { usePhase, type PhaseFilter } from "./lib/phaseContext";
import Dashboard from "./pages/Dashboard";
import Leaderboard from "./pages/Leaderboard";
import DeltaCharts from "./pages/DeltaCharts";
import BudgetCurves from "./pages/BudgetCurves";
import RunExplorer from "./pages/RunExplorer";
import TranscriptViewer from "./pages/TranscriptViewer";
import TaskBrowser from "./pages/TaskBrowser";

const nav = [
  { to: "/", label: "Live Monitor" },
  { to: "/leaderboard", label: "Leaderboard" },
  { to: "/delta", label: "Delta Charts" },
  { to: "/budget-curves", label: "Budget Curves" },
  { to: "/runs", label: "Run Explorer" },
  { to: "/tasks", label: "Tasks" },
];

const phases: { id: PhaseFilter; label: string }[] = [
  { id: "phase1_reasoning", label: "Phase 1" },
  { id: "phase2_agent", label: "Phase 2" },
  { id: "combined", label: "Combined" },
];

export default function App() {
  const { phase, setPhase } = usePhase();

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-white/10 bg-ink-900/80 backdrop-blur-md p-4 flex flex-col gap-6">
        <div>
          <div className="font-display text-xl tracking-tight text-moss-400">SampleMore</div>
          <div className="font-display text-lg text-chalk/80 -mt-1">Studio</div>
          <p className="text-xs text-chalk/50 mt-2 leading-snug">
            Sample more, reflect less — equal-cost strategy benchmark
          </p>
        </div>

        <div>
          <div className="text-[10px] uppercase tracking-widest text-chalk/40 mb-2">Phase</div>
          <div className="flex flex-col gap-1">
            {phases.map((p) => (
              <button
                key={p.id}
                onClick={() => setPhase(p.id)}
                className={`text-left text-sm px-2 py-1.5 rounded transition ${
                  phase === p.id ? "bg-moss-600/30 text-moss-400" : "text-chalk/70 hover:bg-white/5"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          <div className="text-[10px] uppercase tracking-widest text-chalk/40 mb-2">Views</div>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `text-sm px-2 py-1.5 rounded transition ${
                  isActive ? "bg-white/10 text-chalk" : "text-chalk/65 hover:bg-white/5"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto text-[10px] text-chalk/35 font-mono">v0.1 · MIT</div>
      </aside>

      <main className="flex-1 min-w-0 p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/delta" element={<DeltaCharts />} />
          <Route path="/budget-curves" element={<BudgetCurves />} />
          <Route path="/runs" element={<RunExplorer />} />
          <Route path="/runs/:runId" element={<TranscriptViewer />} />
          <Route path="/compare" element={<TranscriptViewer compare />} />
          <Route path="/tasks" element={<TaskBrowser />} />
        </Routes>
      </main>
    </div>
  );
}
