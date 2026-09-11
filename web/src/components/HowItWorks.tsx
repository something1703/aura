const STAGES = [
  {
    n: 1,
    title: "Requirements",
    body: 'Parses the workload YAML into a typed model, normalizes units ("99.99%", "$15k", "5m"), and detects contradictory requirements instead of silently picking one.',
  },
  {
    n: 2,
    title: "Architecture",
    body: "Generates one candidate per catalog pattern — single-region multi-AZ, active-passive, warm-standby, active-active, event-driven-buffered — each with a concrete, typed topology graph placed in real regions.",
  },
  {
    n: 3,
    title: "Failure",
    body: "Simulates 8 failure scenarios per candidate (instance, AZ, region, database, network, traffic spike, bad deployment, dependency) by removing graph nodes and tracing which business capabilities become unreachable.",
  },
  {
    n: 4,
    title: "Cost",
    body: "Estimates 4 load scenarios (average, peak, sustained-peak, failure-mode) as itemized, assumption-labelled line items — never presented as an invoice.",
  },
  {
    n: 5,
    title: "Evaluation",
    body: "Runs 9 rules against every candidate. A mandatory rule failure makes a candidate ineligible no matter how high its score would be. Eligible candidates get an 8-dimension weighted score.",
  },
  {
    n: 6,
    title: "Decision",
    body: "Picks the top eligible candidate, renders a full Markdown report and ADRs for the key decisions — compute, data, region, deployment, scaling, and recovery strategy.",
  },
];

const PRINCIPLES = [
  {
    title: "Rule-based, not generative.",
    body: "Every eligibility check and score is deterministic and reproducible — the same input always yields the same decision.",
  },
  {
    title: "Hard constraints win.",
    body: "A candidate scoring 90/100 that violates a mandatory RTO is still rejected.",
  },
  {
    title: "Evidence over confidence.",
    body: "Every failure result is tagged MODELLED (graph reasoning, not a real test) and confidence drops when assumptions stack up.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="mx-auto max-w-5xl px-5 py-16">
      <h2 className="text-2xl font-semibold text-zinc-900">How it works</h2>
      <p className="mt-1 max-w-2xl text-zinc-600">
        Every request below runs the same six engines the <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-[0.9em]">aura</code> CLI
        uses — this page is a browser front end over the real pipeline, not a mockup.
      </p>

      <div className="mt-8 flex gap-1 overflow-x-auto pb-2">
        {STAGES.map((stage, i) => (
          <div key={stage.n} className="flex items-stretch">
            <div className="min-w-[190px] flex-1 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
              <div className="mb-2.5 flex h-6 w-6 items-center justify-center rounded-full bg-orange-800 text-xs font-bold text-white">
                {stage.n}
              </div>
              <h3 className="text-sm font-semibold text-zinc-900">{stage.title}</h3>
              <p className="mt-1.5 text-[13px] leading-snug text-zinc-600">{stage.body}</p>
            </div>
            {i < STAGES.length - 1 && (
              <div className="flex items-center px-1.5 text-lg text-zinc-400">→</div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        {PRINCIPLES.map((p) => (
          <div
            key={p.title}
            className="rounded-lg border border-zinc-200 border-l-[3px] border-l-orange-800 bg-white p-4 text-sm text-zinc-600 shadow-sm"
          >
            <strong className="text-zinc-900">{p.title}</strong> {p.body}
          </div>
        ))}
      </div>
    </section>
  );
}
