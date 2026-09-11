"use client";

import { useEffect, useRef, useState } from "react";
import type { CandidateFailureReport, FailureScenarioResult } from "@/lib/api";
import { Badge } from "./Badge";

const STEP_DELAY_MS = 900;

type LogEntry = {
  scenario: FailureScenarioResult;
  phase: "injecting" | "detecting" | "resolved";
};

function outcomeOf(scenario: FailureScenarioResult): "recovered" | "degraded" | "hard-failure" {
  if (scenario.rto_status === "FAIL") return "hard-failure";
  if (scenario.rto_status === "WARN" || scenario.blast_radius !== "LOW") return "degraded";
  return "recovered";
}

const OUTCOME_STYLE: Record<string, { label: string; className: string }> = {
  recovered: { label: "RECOVERED", className: "text-emerald-700" },
  degraded: { label: "DEGRADED", className: "text-amber-700" },
  "hard-failure": { label: "HARD FAILURE", className: "text-red-700" },
};

/**
 * The parent renders this with `key={report.candidate_id}` so switching the
 * selected candidate fully remounts it (fresh state) instead of needing an
 * effect to reset internal state on prop change.
 */
export function BreakEverything({
  candidateName,
  report,
}: {
  candidateName: string;
  report: CandidateFailureReport;
}) {
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const logRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [entries]);

  function stop() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    setRunning(false);
  }

  function start() {
    stop();
    setEntries([]);
    setStep(0);
    setRunning(true);
    runStep(0, "injecting");
  }

  function runStep(index: number, phase: LogEntry["phase"]) {
    if (index >= report.scenarios.length) {
      setRunning(false);
      return;
    }
    const scenario = report.scenarios[index];
    setEntries((prev) => [...prev.filter((e) => e.scenario !== scenario), { scenario, phase }]);
    setStep(index);

    timeoutRef.current = setTimeout(() => {
      if (phase === "injecting") {
        runStep(index, "detecting");
      } else if (phase === "detecting") {
        runStep(index, "resolved");
      } else {
        runStep(index + 1, "injecting");
      }
    }, STEP_DELAY_MS);
  }

  const finished = !running && entries.length === report.scenarios.length;
  const worstSoFar = entries.reduce<string>((worst, e) => {
    const order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
    return order.indexOf(e.scenario.blast_radius) > order.indexOf(worst) ? e.scenario.blast_radius : worst;
  }, "LOW");
  const recoveredCount = entries.filter((e) => e.phase === "resolved" && outcomeOf(e.scenario) === "recovered").length;

  return (
    <div className="mt-3 rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-5 py-3.5">
        <div>
          <p className="text-sm font-semibold text-zinc-900">
            Chaos run: {candidateName}
          </p>
          <p className="text-xs text-zinc-500">
            Replays the 8 modelled failure scenarios already computed for this candidate — live,
            one at a time. Nothing here touches AWS; it dramatizes real MODELLED data from the
            analysis above.
          </p>
        </div>
        <button
          onClick={start}
          disabled={running}
          className="shrink-0 rounded-full bg-red-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {running ? `Breaking things… (${step + 1}/${report.scenarios.length})` : "💥 Break Everything"}
        </button>
      </div>

      {entries.length > 0 && (
        <>
          <div ref={logRef} className="max-h-80 overflow-y-auto px-5 py-4 font-mono text-[13px] leading-relaxed">
            {entries.map((e) => (
              <LogLine key={`${e.scenario.event.type}-${e.phase}`} entry={e} />
            ))}
            {running && <div className="animate-pulse text-zinc-400">▌</div>}
          </div>

          {finished && (
            <div className="flex flex-wrap items-center gap-4 border-t border-zinc-200 bg-zinc-50 px-5 py-3.5 text-sm">
              <span>
                Worst blast radius reached: <Badge status={worstSoFar} />
              </span>
              <span className="text-zinc-600">
                {recoveredCount}/{report.scenarios.length} scenarios recovered within RTO
              </span>
              <span className="text-zinc-600">
                AZ failure survived: <strong>{report.survives_az_failure ? "yes" : "no"}</strong>
              </span>
              <span className="text-zinc-600">
                Region failure survived: <strong>{report.survives_region_failure ? "yes" : "no"}</strong>
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const { scenario, phase } = entry;
  if (phase === "injecting") {
    return (
      <div className="text-zinc-800">
        <span className="text-red-700">💥 INJECTING</span> {scenario.event.type}
        {scenario.event.target_az ? ` @ ${scenario.event.target_az}` : ""}
        {scenario.event.target_region ? ` @ ${scenario.event.target_region}` : ""}
      </div>
    );
  }
  if (phase === "detecting") {
    return (
      <div className="pl-5 text-zinc-500">
        <span className="text-amber-700">🔍 detecting</span> via {scenario.detection.toLowerCase()}
      </div>
    );
  }
  const outcome = OUTCOME_STYLE[outcomeOf(scenario)];
  return (
    <div className="pl-5 pb-2 text-zinc-700">
      <span className={`font-semibold ${outcome.className}`}>{outcome.label}</span>
      {" — "}
      {scenario.expected_recovery_seconds !== null
        ? `recovered in ${scenario.expected_recovery_seconds}s`
        : "no recovery path"}
      {". "}
      {scenario.recovery_action}
      {scenario.affected_capabilities.length > 0 && (
        <span className="text-zinc-500"> (affected: {scenario.affected_capabilities.join(", ")})</span>
      )}
    </div>
  );
}
