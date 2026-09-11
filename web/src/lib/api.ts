const API_BASE = process.env.NEXT_PUBLIC_AURA_API_URL ?? "http://127.0.0.1:8000";

export interface NormalizedRequirement {
  value: unknown;
  raw: unknown;
  source: string;
  confidence: number;
  mandatory: boolean;
}

export interface Assumption {
  id: string;
  statement: string;
  confidence: number;
}

export interface Conflict {
  id: string;
  statement: string;
  severity: string;
}

export interface NormalizedRequirements {
  application_name: string;
  application_type: string;
  stateful: boolean;
  average_rps: NormalizedRequirement;
  peak_rps: NormalizedRequirement;
  peak_duration_seconds: NormalizedRequirement;
  growth_percent_per_month: number;
  availability_target: NormalizedRequirement;
  multi_az_required: NormalizedRequirement;
  rto_seconds: NormalizedRequirement;
  rpo_seconds: NormalizedRequirement;
  regional_disaster_required: NormalizedRequirement;
  consistency: Record<string, string>;
  primary_regions: string[];
  user_regions: string[];
  monthly_budget_usd: NormalizedRequirement;
  budget_hard_limit: boolean;
  deployment_frequency_per_day: number;
  downtime_allowed: NormalizedRequirement;
  rollback_target_seconds: NormalizedRequirement | null;
  internet_facing: boolean;
  data_classification: string;
  encryption_at_rest: boolean;
  encryption_in_transit: boolean;
  compliance_frameworks: string[];
  assumptions: Assumption[];
  conflicts: Conflict[];
  confidence: number;
}

export interface PatternSupport {
  availability_min: number;
  rto_max_seconds: number;
  rpo_max_seconds: number;
}

export interface Candidate {
  id: string;
  name: string;
  description: string;
  supports: PatternSupport;
  requires: string[];
  tradeoffs: string[];
  failure_modes_tolerated: string[];
  multi_region: boolean;
  regional_resilience: boolean;
  primary_region: string;
  secondary_region: string | null;
  secondary_region_assumed: boolean;
  topology: unknown;
  availability_model: string;
  scaling_model: string;
  data_strategy: string;
  failure_strategy: string;
  cost_assumptions: string[];
  known_limitations: string[];
  diagram: string;
}

export interface RuleResult {
  rule_id: string;
  status: "PASS" | "WARN" | "FAIL" | "NOT_EVALUATED";
  severity: string;
  observed: unknown;
  required: unknown;
  evidence: string;
  mandatory: boolean;
}

export interface DimensionScore {
  dimension: string;
  value: number;
  weight: number;
  evidence: string[];
}

export interface FailureEvent {
  type: string;
  target_az: string | null;
  target_region: string | null;
  target_component: string | null;
  severity: string;
  assumptions: Record<string, string>;
}

export interface FailureScenarioResult {
  event: FailureEvent;
  detection: string;
  affected_components: string[];
  affected_capabilities: string[];
  recovery_action: string;
  expected_recovery_seconds: number | null;
  rto_required_seconds: number;
  rto_status: "PASS" | "WARN" | "FAIL" | "NOT_EVALUATED";
  expected_data_loss_seconds: number | null;
  rpo_required_seconds: number;
  rpo_status: "PASS" | "WARN" | "FAIL" | "NOT_EVALUATED";
  blast_radius: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  confidence: number;
  evidence: "MODELLED" | "SIMULATED" | "MEASURED";
  notes: string[];
}

export interface CandidateFailureReport {
  candidate_id: string;
  scenarios: FailureScenarioResult[];
  worst_blast_radius: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  hard_failures: string[];
  survives_az_failure: boolean;
  survives_region_failure: boolean;
}

export interface CostLineItem {
  service: string;
  unit: string;
  quantity: number;
  utilization: number | null;
  unit_price_usd: number;
  monthly_cost_usd: number;
  assumption: string;
  confidence: "low" | "medium" | "high";
}

export interface CostEstimate {
  candidate_id: string;
  scenario: string;
  line_items: CostLineItem[];
  total_monthly_usd: number;
  confidence: "low" | "medium" | "high";
}

export interface CandidateScore {
  candidate_id: string;
  eligibility: "ELIGIBLE" | "INELIGIBLE";
  ineligibility_reasons: string[];
  rule_results: RuleResult[];
  dimension_scores: DimensionScore[];
  weighted_score: number | null;
  confidence: number;
  failure_report: CandidateFailureReport;
  cost_estimates: Record<string, CostEstimate>;
}

export interface AnalyzeResponse {
  workload: unknown;
  normalized: NormalizedRequirements;
  candidates: Candidate[];
  scores: CandidateScore[];
  recommendation_id: string | null;
  report_markdown: string;
  adrs: Record<string, string>;
}

interface ApiErrorBody {
  error: string;
  details?: string[];
}

export async function fetchExample(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/example`);
  if (!res.ok) {
    throw new Error(`Could not load the example workload (HTTP ${res.status}). Is \`aura serve\` running?`);
  }
  const data = (await res.json()) as { yaml_text: string };
  return data.yaml_text;
}

export async function analyzeWorkload(yamlText: string): Promise<AnalyzeResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml_text: yamlText }),
    });
  } catch {
    throw new Error(`Could not reach the AURA API at ${API_BASE}. Run \`aura serve\` in another terminal.`);
  }

  const data = await res.json();
  if (!res.ok) {
    const err = data as ApiErrorBody;
    const message = err.details?.length
      ? `${err.error}\n\n${err.details.map((d) => `- ${d}`).join("\n")}`
      : err.error ?? `Request failed (HTTP ${res.status}).`;
    throw new Error(message);
  }
  return data as AnalyzeResponse;
}
