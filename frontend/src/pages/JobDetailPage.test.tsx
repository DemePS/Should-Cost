import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { JobDetailPage } from "./JobDetailPage";
import { api, type Job } from "../api/client";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { ...actual.api, getJob: vi.fn(), answerJob: vi.fn() } };
});

function renderAt(jobId: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/jobs/${jobId}`]}>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BASE_JOB: Job = {
  job_id: "job-1",
  material_id: "0T0001",
  language: "en",
  status: "needs_input",
  current_step: "step_0_discovery",
  pending_question: { reason: "no_spend_row", question: "Please provide Volume, Spend, Price manually." },
  failure_reason: null,
  discovery_documents: [],
  units: [],
  trace: [],
  cross_supplier_table: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("JobDetailPage — needs_input screen", () => {
  it("shows the pending question and submits an answer", async () => {
    vi.mocked(api.getJob).mockResolvedValue(BASE_JOB);
    vi.mocked(api.answerJob).mockResolvedValue({ status: "resuming" });

    renderAt("job-1");

    expect(await screen.findByText(/Please provide Volume, Spend, Price manually/)).toBeInTheDocument();
    expect(screen.getByText(/no spend row/i)).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Your answer…");
    await userEvent.type(input, "500000,25000,0.05");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => expect(api.answerJob).toHaveBeenCalledWith("job-1", "500000,25000,0.05"));
  });
});

describe("JobDetailPage — result screen", () => {
  it("renders the cost build tiles and download links once done", async () => {
    const doneJob: Job = {
      ...BASE_JOB,
      status: "done",
      pending_question: null,
      units: [
        {
          unit_id: "u1",
          label: "Fastener Fabrik GmbH",
          is_rollup: false,
          status: "done",
          current_step: "done",
          trace: [],
          sanity_gate: {
            overall_status: "green",
            reasonability_note: "Should Cost is within range.",
            impact_pct: 12.3,
            impact_status: "green",
            bucket_checks: [],
            calibration_checks: [],
            action: "Proceed.",
          },
          cost_build: {
            material_eur: 0.005,
            conversion_eur: 0.001,
            manufacturing_costs_eur: 0.006,
            pl_eur: 0.001,
            overheads_eur: 0.001,
            margin_eur: 0.001,
            should_cost_eur: 0.009,
            impact_eur: 0.001,
            current_price_eur: 0.01,
          },
          chat_blocks: {
            block_a_cost_build: {},
            block_b_header_info: {},
            block_c_key_results: {},
            block_d_input_table: [],
            block_e_sensitivity: [],
            block_f_key_insights: [],
          },
          insights: {
            self_critique: [{ point: "Wire rod price assumption", why_uncertain: "spot volatility", how_to_harden: "confirm RFQ" }],
            negotiation_levers: [
              { parameter: "Machine rate", current_value: "n/a", should_cost_value: "5", delta_eur_per_unit: 0.001, lever: "show derivation" },
            ],
            non_negotiables: ["Steel index price"],
            highest_information_gain_question: "What is your actual cycle rate?",
          },
          files: [{ name: "Should_Cost_0T0001_FastenerFabrik_20260101_v01.xlsx", kind: "calc_model" }],
        },
      ],
    };
    vi.mocked(api.getJob).mockResolvedValue(doneJob);

    renderAt("job-1");

    expect(await screen.findByText("Fastener Fabrik GmbH")).toBeInTheDocument();
    expect(screen.getByText("€0.009")).toBeInTheDocument();
    expect(screen.getByText(/Download calculation model/)).toBeInTheDocument();
    expect(screen.getByText(/What is your actual cycle rate\?/)).toBeInTheDocument();
  });
});
