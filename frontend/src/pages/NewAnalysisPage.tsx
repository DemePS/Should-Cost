import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
];

export function NewAnalysisPage() {
  const [materialId, setMaterialId] = useState("");
  const [language, setLanguage] = useState("en");
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const recentJobs = useQuery({ queryKey: ["jobs"], queryFn: api.listJobs, refetchInterval: 5000 });

  const createJob = useMutation({
    mutationFn: () => api.createJob(materialId.trim(), language),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/jobs/${data.job_id}`);
    },
  });

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <h1>New Should-Cost Analysis</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (materialId.trim()) createJob.mutate();
        }}
        style={{ display: "flex", gap: 12, alignItems: "flex-end", marginBottom: 32 }}
      >
        <div style={{ flex: 1 }}>
          <label htmlFor="material-id" style={{ display: "block", fontSize: 13, marginBottom: 4 }}>
            Material ID
          </label>
          <input
            id="material-id"
            value={materialId}
            onChange={(e) => setMaterialId(e.target.value)}
            placeholder="e.g. 0M5200, 1D0488"
            style={{ width: "100%", padding: 8, fontSize: 14 }}
          />
        </div>
        <div>
          <label htmlFor="language" style={{ display: "block", fontSize: 13, marginBottom: 4 }}>
            Language
          </label>
          <select id="language" value={language} onChange={(e) => setLanguage(e.target.value)} style={{ padding: 8 }}>
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" disabled={!materialId.trim() || createJob.isPending} style={{ padding: "8px 20px" }}>
          {createJob.isPending ? "Starting…" : "Start"}
        </button>
      </form>

      {createJob.isError && <p style={{ color: "#c62828" }}>Could not start the analysis: {String(createJob.error)}</p>}

      <h2>Recent jobs</h2>
      {recentJobs.isLoading && <p>Loading…</p>}
      {recentJobs.data?.length === 0 && <p>No analyses yet.</p>}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          {recentJobs.data?.map((job) => (
            <tr
              key={job.job_id}
              onClick={() => navigate(`/jobs/${job.job_id}`)}
              style={{ cursor: "pointer", borderBottom: "1px solid #e0e0e0" }}
            >
              <td style={{ padding: "8px 4px", fontFamily: "monospace" }}>{job.material_id}</td>
              <td style={{ padding: "8px 4px" }}>
                <StatusBadge status={job.status} />
              </td>
              <td style={{ padding: "8px 4px", color: "#757575", fontSize: 13 }}>
                {new Date(job.updated_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
