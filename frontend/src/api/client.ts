/**
 * Thin fetch wrapper against the backend's /api/* routes. Base path is relative
 * ("/api") per the task brief — "the same build works in every environment": in dev,
 * Vite's proxy (vite.config.ts) forwards it to localhost:8000; in production, FastAPI
 * serves both the API and this build from one origin (should_cost/main.py).
 *
 * Hand-written against should_cost/routes/jobs.py rather than generated, for now — see
 * `make openapi-client` (root Makefile) for the generated-client path once the schema
 * is stable; openapi-typescript's output can replace the types below without changing
 * any call site, since both describe the same wire shapes.
 */

const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body || response.statusText);
  }
  return response.json() as Promise<T>;
}

export type JobStatus = "queued" | "running" | "needs_input" | "done" | "failed";

export interface JobSummary {
  job_id: string;
  material_id: string;
  status: JobStatus;
  current_step: string;
  updated_at: string;
}

export interface PendingQuestion {
  reason: string;
  question: string;
  context?: string | null;
}

export interface StepEvent {
  step: string;
  status: "started" | "completed" | "failed" | "skipped";
  at: string;
  detail?: string | null;
}

export interface GeneratedFile {
  name: string;
  kind: "calc_model" | "slide_values";
  sharepoint_url?: string | null;
}

export interface SanityGateResult {
  overall_status: "green" | "yellow" | "red";
  reasonability_note: string;
  impact_pct: number;
  impact_status: "green" | "yellow" | "red";
  bucket_checks: Array<{ bucket: string; share_pct: number; status: "green" | "yellow" | "red" }>;
  calibration_checks: Array<{ rule_id: string; description: string; status: "green" | "yellow" | "red"; note: string }>;
  action: string;
}

export interface ChatBlocks {
  block_a_cost_build: Record<string, number>;
  block_b_header_info: Record<string, string>;
  block_c_key_results: Record<string, string>;
  block_d_input_table: Array<Record<string, unknown>>;
  block_e_sensitivity: Array<Record<string, unknown>>;
  block_f_key_insights: string[];
}

export interface Insights {
  self_critique: Array<{ point: string; why_uncertain: string; how_to_harden: string }>;
  negotiation_levers: Array<{
    parameter: string;
    current_value: string;
    should_cost_value: string;
    delta_eur_per_unit: number;
    lever: string;
  }>;
  non_negotiables: string[];
  highest_information_gain_question: string;
}

export interface JobUnit {
  unit_id: string;
  label: string;
  is_rollup: boolean;
  status: JobStatus;
  current_step: string;
  trace: StepEvent[];
  sanity_gate?: SanityGateResult | null;
  cost_build?: Record<string, number> | null;
  chat_blocks?: ChatBlocks | null;
  insights?: Insights | null;
  files: GeneratedFile[];
}

export interface SupplierRow {
  supplier_name: string;
  country?: string | null;
  hager_entity: string;
  unit_of_measure: string;
  annual_volume: number;
  annual_spend: number;
  current_avg_price: number;
  supplier_type: "manufacturer" | "distributor_trader" | "unknown";
  is_manual_override: boolean;
}

export interface SpendLookupResult {
  match_type: "exact" | "prefix_variant" | "not_found" | "manual_override";
  base_id: string;
  variants_found: string[];
  plausibility_note?: string | null;
  suppliers: SupplierRow[];
  source_filename?: string | null;
}

export interface Job {
  job_id: string;
  material_id: string;
  language: string;
  status: JobStatus;
  current_step: string;
  pending_question?: PendingQuestion | null;
  failure_reason?: string | null;
  spend_lookup?: SpendLookupResult | null;
  discovery_documents: Array<{ filename: string; text: string }>;
  units: JobUnit[];
  trace: StepEvent[];
  cross_supplier_table: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

export const api = {
  createJob: (material_id: string, language = "en") =>
    request<{ job_id: string }>("/jobs", { method: "POST", body: JSON.stringify({ material_id, language }) }),

  listJobs: () => request<JobSummary[]>("/jobs"),

  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),

  answerJob: (jobId: string, answer: string) =>
    request<{ status: string }>(`/jobs/${jobId}/answer`, { method: "POST", body: JSON.stringify({ answer }) }),

  fileUrl: (jobId: string, name: string) => `${API_BASE}/jobs/${jobId}/files/${encodeURIComponent(name)}`,
};
