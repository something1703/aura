"use client";

import { useEffect, useState } from "react";
import {
  analyzeWorkload,
  fetchExample,
  type AnalyzeResponse,
  type Candidate,
  type CandidateScore,
} from "@/lib/api";
import { Badge } from "./Badge";
import { MermaidDiagram } from "./MermaidDiagram";
import { ReportMarkdown } from "./ReportMarkdown";

export function AnalyzeDemo() {
  const [yamlText, setYamlText] = useState("");
  const [loadingExample, setLoadingExample] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    void loadExample();
  }, []);

  async function loadExample() {
    setLoadingExample(true);
    setError(null);
    try {
      setYamlText(await fetchExample());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingExample(false);
    }
  }

  async function runAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      const data = await analyzeWorkload(yamlText);
      setResult(data);
      setSelectedId(data.recommendation_id ?? data.scores[0]?.candidate_id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAnalyzing(false);
    }
  }

  const selectedCandidate = result?.candidates.find((c) => c.id === selectedId) ?? null;
  const selectedScore = result?.scores.find((s) => s.candidate_id === selectedId) ?? null;
  const recommendationScore =
    result?.scores.find((s) => s.candidate_id === result.recommendation_id) ?? null;
  const recommendationCandidate =
    result?.candidates.find((c) => c.id === result.recommendation_id) ?? null;

  return (
    <>
      <section id="try-it" className="mx-auto max-w-5xl px-5 py-16">
        <h2 className="text-2xl font-semibold text-zinc-900">Try it</h2>
        <p className="mt-1 max-w-2xl text-zinc-600">
          Edit the workload below (or use the pre-loaded flash-sale example) and run a real
          analysis against the AURA engine.
        </p>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-[1fr_220px]">
          <textarea
            value={yamlText}
            onChange={(e) => setYamlText(e.target.value)}
            spellCheck={false}
            placeholder={loadingExample ? "Loading example workload…" : undefined}
            className="min-h-[380px] w-full resize-y rounded-xl border border-zinc-200 bg-white p-4 font-mono text-[13px] leading-relaxed text-zinc-900 shadow-sm focus:border-orange-700 focus:outline-none"
          />
          <div className="flex flex-col items-start gap-3">
            <button
              onClick={() => void runAnalyze()}
              disabled={analyzing || loadingExample}
              className="w-full rounded-full bg-orange-800 px-6 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            >
              {analyzing ? "Analyzing…" : "Analyze"}
            </button>
            <button
              onClick={() => void loadExample()}
              className="w-full rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-700 hover:border-orange-700 hover:text-orange-800"
            >
              Reset to example
            </button>
            {result && (
              <p className="text-sm text-zinc-500">
                Done — {result.candidates.length} candidate(s) evaluated.
              </p>
            )}
          </div>
        </div>

        {error && (
          <pre className="mt-5 whitespace-pre-wrap rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </pre>
        )}
      </section>

      {result && (
        <section id="results" className="mx-auto max-w-5xl px-5 py-16">
          <RecommendationBanner candidate={recommendationCandidate} score={recommendationScore} />

          <h2 className="mt-10 text-2xl font-semibold text-zinc-900">Candidate comparison</h2>
          <CandidateTable
            scores={result.scores}
            candidates={result.candidates}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />

          {selectedCandidate && selectedScore && (
            <>
              <h2 className="mt-12 text-2xl font-semibold text-zinc-900">
                Selected candidate: {selectedCandidate.name}
              </h2>
              <div className="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-[1.1fr_1fr]">
                <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
                  <MermaidDiagram chart={selectedCandidate.diagram} />
                </div>
                <StrategyCard candidate={selectedCandidate} />
              </div>

              <h3 className="mt-9 text-lg font-semibold text-zinc-900">Scoring breakdown</h3>
              <ScoringTable score={selectedScore} />

              <h3 className="mt-9 text-lg font-semibold text-zinc-900">Rule evaluation</h3>
              <RulesTable score={selectedScore} />

              <h3 className="mt-9 text-lg font-semibold text-zinc-900">Failure analysis</h3>
              <FailureTable score={selectedScore} />

              <h3 className="mt-9 text-lg font-semibold text-zinc-900">Cost analysis</h3>
              <CostTables score={selectedScore} />
            </>
          )}

          <h3 className="mt-9 text-lg font-semibold text-zinc-900">Rejected candidates</h3>
          <RejectedPanel scores={result.scores} />

          <h3 className="mt-9 text-lg font-semibold text-zinc-900">Architecture Decision Records</h3>
          <AdrPanel adrs={result.adrs} />

          <h3 className="mt-9 text-lg font-semibold text-zinc-900">Full report</h3>
          <details className="mt-3 rounded-xl border border-zinc-200 bg-white shadow-sm">
            <summary className="cursor-pointer select-none px-5 py-3 font-medium text-zinc-800">
              Show the full Markdown report
            </summary>
            <div className="border-t border-zinc-200 px-5 py-6">
              <ReportMarkdown markdown={result.report_markdown} />
            </div>
          </details>
        </section>
      )}
    </>
  );
}

function RecommendationBanner({
  candidate,
  score,
}: {
  candidate: Candidate | null;
  score: CandidateScore | null;
}) {
  if (!candidate || !score) {
    return (
      <div className="rounded-xl border border-red-300 border-l-4 bg-white p-5 shadow-sm">
        <div className="text-lg font-bold text-zinc-900">No eligible candidate</div>
        <p className="mt-1 text-sm text-zinc-600">
          Every generated candidate failed at least one mandatory constraint. See the candidate
          comparison and rejected candidates below for the reasons.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-zinc-200 border-l-4 border-l-emerald-600 bg-white p-5 shadow-sm">
      <div className="text-lg font-bold text-zinc-900">Recommendation: {candidate.name}</div>
      <div className="mt-1 text-sm text-zinc-500">
        Weighted score {score.weighted_score}/100 &middot; confidence {score.confidence} &middot;
        primary region {candidate.primary_region}
        {candidate.secondary_region ? ` + ${candidate.secondary_region}` : ""}
      </div>
      <p className="mt-2 text-sm text-zinc-700">{candidate.description}</p>
    </div>
  );
}

function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
      <table className="w-full border-collapse text-left text-sm">{children}</table>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="border-b border-zinc-200 bg-zinc-50 px-3 py-2 font-semibold text-zinc-700">
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="border-b border-zinc-100 px-3 py-2 align-top text-zinc-800">{children}</td>;
}

function CandidateTable({
  scores,
  candidates,
  selectedId,
  onSelect,
}: {
  scores: CandidateScore[];
  candidates: Candidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Candidate</Th>
          <Th>Eligibility</Th>
          <Th>Score</Th>
          <Th>Confidence</Th>
          <Th>Blast radius</Th>
          <Th>AZ survives</Th>
          <Th>Region survives</Th>
        </tr>
      </thead>
      <tbody>
        {scores.map((s) => {
          const candidate = candidates.find((c) => c.id === s.candidate_id);
          if (!candidate) return null;
          const selected = s.candidate_id === selectedId;
          return (
            <tr
              key={s.candidate_id}
              onClick={() => onSelect(s.candidate_id)}
              className={`cursor-pointer hover:bg-orange-50 ${selected ? "bg-orange-50/70" : ""}`}
            >
              <Td>{candidate.name}</Td>
              <Td>
                <Badge status={s.eligibility} />
              </Td>
              <Td>{s.weighted_score ?? "—"}</Td>
              <Td>{s.confidence}</Td>
              <Td>
                <Badge status={s.failure_report.worst_blast_radius} />
              </Td>
              <Td>{s.failure_report.survives_az_failure ? "yes" : "no"}</Td>
              <Td>{s.failure_report.survives_region_failure ? "yes" : "no"}</Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function StrategyCard({ candidate }: { candidate: Candidate }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="font-semibold text-zinc-500">Availability model</dt>
          <dd className="mt-0.5 text-zinc-800">{candidate.availability_model}</dd>
        </div>
        <div>
          <dt className="font-semibold text-zinc-500">Scaling model</dt>
          <dd className="mt-0.5 text-zinc-800">{candidate.scaling_model}</dd>
        </div>
        <div>
          <dt className="font-semibold text-zinc-500">Data strategy</dt>
          <dd className="mt-0.5 text-zinc-800">{candidate.data_strategy}</dd>
        </div>
        <div>
          <dt className="font-semibold text-zinc-500">Failure strategy</dt>
          <dd className="mt-0.5 text-zinc-800">{candidate.failure_strategy}</dd>
        </div>
        <div>
          <dt className="font-semibold text-zinc-500">Known limitations</dt>
          <dd className="mt-0.5 text-zinc-800">
            {candidate.known_limitations.length ? (
              <ul className="list-disc space-y-0.5 pl-4">
                {candidate.known_limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            ) : (
              "none declared"
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function ScoringTable({ score }: { score: CandidateScore }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Dimension</Th>
          <Th>Score</Th>
          <Th>Weight</Th>
          <Th>Evidence</Th>
        </tr>
      </thead>
      <tbody>
        {score.dimension_scores.map((d) => (
          <tr key={d.dimension}>
            <Td>{d.dimension}</Td>
            <Td>{d.value}</Td>
            <Td>{d.weight.toFixed(1)}%</Td>
            <Td>{d.evidence.join("; ")}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function RulesTable({ score }: { score: CandidateScore }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Rule</Th>
          <Th>Status</Th>
          <Th>Mandatory</Th>
          <Th>Evidence</Th>
        </tr>
      </thead>
      <tbody>
        {score.rule_results.map((r) => (
          <tr key={r.rule_id}>
            <Td>{r.rule_id}</Td>
            <Td>
              <Badge status={r.status} />
            </Td>
            <Td>{r.mandatory ? "yes" : "no"}</Td>
            <Td>{r.evidence}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function FailureTable({ score }: { score: CandidateScore }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Scenario</Th>
          <Th>Blast radius</Th>
          <Th>RTO</Th>
          <Th>RPO</Th>
          <Th>Expected recovery</Th>
          <Th>Recovery action</Th>
        </tr>
      </thead>
      <tbody>
        {score.failure_report.scenarios.map((s) => (
          <tr key={s.event.type}>
            <Td>{s.event.type}</Td>
            <Td>
              <Badge status={s.blast_radius} />
            </Td>
            <Td>
              <Badge status={s.rto_status} />
            </Td>
            <Td>
              <Badge status={s.rpo_status} />
            </Td>
            <Td>{s.expected_recovery_seconds !== null ? `${s.expected_recovery_seconds}s` : "no recovery path"}</Td>
            <Td>{s.recovery_action}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function CostTables({ score }: { score: CandidateScore }) {
  const peak = score.cost_estimates["peak_load"];
  return (
    <>
      <Table>
        <thead>
          <tr>
            <Th>Scenario</Th>
            <Th>Total monthly (USD)</Th>
            <Th>Confidence</Th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(score.cost_estimates).map(([key, estimate]) => (
            <tr key={key}>
              <Td>{key}</Td>
              <Td>${estimate.total_monthly_usd.toFixed(2)}</Td>
              <Td>
                <Badge status={estimate.confidence} />
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>

      <p className="mt-4 text-sm font-medium text-zinc-700">Peak-load line items</p>
      <Table>
        <thead>
          <tr>
            <Th>Service</Th>
            <Th>Quantity</Th>
            <Th>Unit</Th>
            <Th>Monthly (USD)</Th>
            <Th>Assumption</Th>
          </tr>
        </thead>
        <tbody>
          {(peak?.line_items ?? []).map((item) => (
            <tr key={item.service}>
              <Td>{item.service}</Td>
              <Td>{item.quantity}</Td>
              <Td>{item.unit}</Td>
              <Td>${item.monthly_cost_usd.toFixed(2)}</Td>
              <Td>{item.assumption}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </>
  );
}

function RejectedPanel({ scores }: { scores: CandidateScore[] }) {
  const rejected = scores.filter((s) => s.eligibility === "INELIGIBLE");
  if (!rejected.length) {
    return <p className="mt-3 text-sm text-zinc-600">No candidates were rejected.</p>;
  }
  return (
    <div className="mt-3 space-y-3">
      {rejected.map((s) => (
        <div
          key={s.candidate_id}
          className="rounded-xl border border-zinc-200 border-l-4 border-l-red-600 bg-white p-4 shadow-sm"
        >
          <div className="font-semibold text-zinc-900">{s.candidate_id}</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-zinc-600">
            {s.ineligibility_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function AdrPanel({ adrs }: { adrs: Record<string, string> }) {
  const entries = Object.entries(adrs);
  if (!entries.length) {
    return (
      <p className="mt-3 text-sm text-zinc-600">
        No ADRs generated: no candidate was eligible for recommendation.
      </p>
    );
  }
  return (
    <div className="mt-3 space-y-3">
      {entries.map(([filename, content]) => (
        <details key={filename} className="rounded-xl border border-zinc-200 bg-white shadow-sm">
          <summary className="cursor-pointer select-none px-5 py-3 font-medium text-zinc-800">
            {filename}
          </summary>
          <div className="border-t border-zinc-200 px-5 py-5">
            <ReportMarkdown markdown={content} />
          </div>
        </details>
      ))}
    </div>
  );
}
