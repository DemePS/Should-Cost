import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, type Job, type JobUnit } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { StepTracker } from "../components/StepTracker";
import { WaterfallChart } from "../components/WaterfallChart";
import { SensitivityTornado } from "../components/SensitivityTornado";
import { InventoryDrawer } from "../components/InventoryDrawer";

// Screens 2, 3 and 4 from the task brief ("Job progress", "Needs input", "Result") are
// one route here, not three — all three are views of the same GET /api/jobs/{id}
// resource, switched purely by job.status, which is also what the 3s polling already
// has to re-check on every tick. Splitting them into separate routes would mean
// duplicating that fetch/poll logic three times for no benefit.
export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [answer, setAnswer] = useState("");
  const queryClient = useQueryClient();

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 3000;
    },
  });

  const answerMutation = useMutation({
    mutationFn: () => api.answerJob(jobId!, answer),
    onSuccess: () => {
      setAnswer("");
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });

  if (jobQuery.isLoading) return <p style={{ padding: 24 }}>Loading…</p>;
  if (jobQuery.isError || !jobQuery.data) return <p style={{ padding: 24, color: "#c62828" }}>Could not load this job.</p>;

  const job = jobQuery.data;
  const supplierUnits = job.units.filter((u) => !u.is_rollup);

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ fontFamily: "monospace" }}>
          {job.material_id} <StatusBadge status={job.status} />
        </h1>
        <button onClick={() => setDrawerOpen(true)}>Inventory &amp; Sources</button>
      </div>

      {(job.status === "queued" || job.status === "running") && (
        <section style={{ margin: "24px 0" }}>
          <StepTracker currentStep={job.current_step} trace={job.trace} failed={false} />
          {supplierUnits.map((unit) => (
            <div key={unit.unit_id} style={{ marginTop: 16 }}>
              <strong>{unit.label}</strong>
              <StepTracker currentStep={unit.current_step} trace={unit.trace} failed={false} />
            </div>
          ))}
        </section>
      )}

      {job.status === "needs_input" && job.pending_question && (
        <section style={{ margin: "24px 0", padding: 16, border: "1px solid #b8860b", borderRadius: 8 }}>
          <h3>Input needed — {job.pending_question.reason.replace(/_/g, " ")}</h3>
          <p>{job.pending_question.question}</p>
          {job.pending_question.context && <p style={{ fontSize: 13, color: "#757575" }}>{job.pending_question.context}</p>}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (answer.trim()) answerMutation.mutate();
            }}
            style={{ display: "flex", gap: 8, marginTop: 12 }}
          >
            <input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Your answer…"
              style={{ flex: 1, padding: 8 }}
            />
            <button type="submit" disabled={!answer.trim() || answerMutation.isPending}>
              {answerMutation.isPending ? "Submitting…" : "Submit"}
            </button>
          </form>
        </section>
      )}

      {job.status === "failed" && (
        <section style={{ margin: "24px 0", padding: 16, border: "1px solid #c62828", borderRadius: 8 }}>
          <h3>Job failed</h3>
          <p>{job.failure_reason}</p>
        </section>
      )}

      {job.status === "done" && (
        <section style={{ margin: "24px 0" }}>
          {supplierUnits.length > 1 && job.cross_supplier_table.length > 0 && (
            <>
              <h2>Cross-supplier comparison</h2>
              <ComparisonTable rows={job.cross_supplier_table} />
            </>
          )}
          {supplierUnits.map((unit) => <ResultTabs key={unit.unit_id} job={job} unit={unit} />)}
        </section>
      )}

      {drawerOpen && <InventoryDrawer job={job} onClose={() => setDrawerOpen(false)} />}
    </div>
  );
}

function ComparisonTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  if (rows.length === 0) return null;
  const columns = Object.keys(rows[0]);
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24, fontSize: 13 }}>
      <thead>
        <tr style={{ borderBottom: "1px solid #ddd", textAlign: "left" }}>
          {columns.map((c) => (
            <th key={c} style={{ padding: 4 }}>
              {c.replace(/_/g, " ")}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #eee" }}>
            {columns.map((c) => (
              <td key={c} style={{ padding: 4 }}>
                {String(row[c])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ResultTabs({ job, unit }: { job: Job; unit: JobUnit }) {
  if (!unit.cost_build) return null;
  const sanity = unit.sanity_gate;

  return (
    <div style={{ marginBottom: 40, border: "1px solid #e0e0e0", borderRadius: 8, padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>{unit.label}</h2>

      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <Tile label="Current price" value={`€${unit.cost_build.current_price_eur?.toFixed(3)}`} />
        <Tile label="Should cost" value={`€${unit.cost_build.should_cost_eur?.toFixed(3)}`} />
        <Tile label="Impact / unit" value={`€${unit.cost_build.impact_eur?.toFixed(3)}`} />
        {sanity && <Tile label="Sanity" value={<StatusBadge status={sanity.overall_status} />} />}
      </div>

      <WaterfallChart costBuild={unit.cost_build} />

      {unit.chat_blocks?.block_d_input_table && (
        <>
          <h3>Inputs</h3>
          <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #ddd", textAlign: "left" }}>
                <th>#</th>
                <th>Parameter</th>
                <th>Unit</th>
                <th>Low</th>
                <th>Base</th>
                <th>High</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {unit.chat_blocks.block_d_input_table.map((row, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: "1px solid #f0f0f0",
                    backgroundColor: row.to_be_validated ? "#fff8e1" : undefined,
                  }}
                >
                  <td>{String(row.number)}</td>
                  <td>{String(row.parameter)}</td>
                  <td>{String(row.unit)}</td>
                  <td>{String(row.low)}</td>
                  <td>
                    <strong>{String(row.base)}</strong>
                  </td>
                  <td>{String(row.high)}</td>
                  <td>
                    {String(row.source)}
                    {row.to_be_validated ? " — to be validated" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {unit.chat_blocks?.block_e_sensitivity && unit.chat_blocks.block_e_sensitivity.length > 0 && (
        <>
          <h3>Sensitivity (top 5)</h3>
          <SensitivityTornado drivers={unit.chat_blocks.block_e_sensitivity as never} />
        </>
      )}

      {unit.insights && (
        <>
          <h3>Insights</h3>
          <ul>
            {unit.insights.self_critique.map((c, i) => (
              <li key={i}>{c.point}</li>
            ))}
          </ul>
          <h4>Negotiation levers</h4>
          <ol>
            {unit.insights.negotiation_levers.map((l, i) => (
              <li key={i}>
                {l.parameter}: {l.lever} (Δ €{l.delta_eur_per_unit.toFixed(3)}/unit)
              </li>
            ))}
          </ol>
          <p>
            <strong>Supplier question:</strong> {unit.insights.highest_information_gain_question}
          </p>
        </>
      )}

      {sanity && sanity.overall_status !== "green" && (
        <details open style={{ marginTop: 16 }}>
          <summary>Sanity gate details ({sanity.overall_status})</summary>
          <p>{sanity.reasonability_note}</p>
          <p>{sanity.action}</p>
        </details>
      )}

      <div style={{ marginTop: 16, display: "flex", gap: 12 }}>
        {unit.files.map((f) => (
          <a key={f.name} href={api.fileUrl(job.job_id, f.name)} download>
            Download {f.kind === "calc_model" ? "calculation model" : "slide values"}
          </a>
        ))}
        {unit.files.find((f) => f.sharepoint_url) && (
          <a href={unit.files.find((f) => f.sharepoint_url)!.sharepoint_url!} target="_blank" rel="noreferrer">
            Open in SharePoint
          </a>
        )}
      </div>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div style={{ padding: "8px 16px", border: "1px solid #e0e0e0", borderRadius: 6, minWidth: 120 }}>
      <div style={{ fontSize: 11, color: "#757575" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
