import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type PhaseFilter = "phase1_reasoning" | "phase2_agent" | "combined";

type Ctx = {
  phase: PhaseFilter;
  setPhase: (p: PhaseFilter) => void;
  apiPhase: string | undefined;
};

const PhaseContext = createContext<Ctx | null>(null);

export function PhaseProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<PhaseFilter>("phase1_reasoning");
  const apiPhase = phase === "combined" ? undefined : phase;
  const value = useMemo(() => ({ phase, setPhase, apiPhase }), [phase, apiPhase]);
  return <PhaseContext.Provider value={value}>{children}</PhaseContext.Provider>;
}

export function usePhase() {
  const ctx = useContext(PhaseContext);
  if (!ctx) throw new Error("usePhase outside provider");
  return ctx;
}
