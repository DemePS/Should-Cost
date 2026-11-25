import type { StepEvent } from "../api/client";

// Screen 2's step tracker, per the task brief: Inventory, Documents, Parameters, Price
// research, Excel build, Sanity gate, Insights — mapped from the backend's WorkflowStep
// enum (should_cost/models/job.py) to these human labels.
const STEP_LABELS: Array<{ keys: string[]; label: string }> = [
  { keys: ["step_0_discovery"], label: "Inventory" },
  { keys: ["step_1_extract_facts"], label: "Documents" },
  { keys: ["step_1_5_pre_build_reasoning", "step_2_propose_parameters", "step_2_5_deep_dive"], label: "Parameters" },
  { keys: ["step_3_research"], label: "Price research" },
  { keys: ["step_4_build_excel", "step_4_5_sanity_gate"], label: "Excel build" },
  { keys: ["step_4_5_sanity_gate"], label: "Sanity gate" },
  { keys: ["step_5_slide_values", "step_5_5_6_insights"], label: "Insights" },
];

function stepIndex(stepKey: string): number {
  const idx = STEP_LABELS.findIndex((s) => s.keys.includes(stepKey));
  return idx === -1 ? 0 : idx;
}

export function StepTracker({ currentStep, trace, failed }: { currentStep: string; trace: StepEvent[]; failed: boolean }) {
  const activeIndex = stepIndex(currentStep);
  const hasFailedEvent = trace.some((e) => e.status === "failed");

  return (
    <div style={{ display: "flex", gap: 4 }}>
      {STEP_LABELS.map((step, i) => {
        const state = i < activeIndex ? "done" : i === activeIndex ? (failed && hasFailedEvent ? "failed" : "active") : "pending";
        const color = state === "done" ? "#2e7d32" : state === "active" ? "#1565c0" : state === "failed" ? "#c62828" : "#bdbdbd";
        return (
          <div key={step.label} style={{ flex: 1, textAlign: "center" }}>
            <div style={{ height: 6, borderRadius: 3, backgroundColor: color, marginBottom: 4 }} />
            <div style={{ fontSize: 11, color: state === "pending" ? "#9e9e9e" : "#212121" }}>{step.label}</div>
          </div>
        );
      })}
    </div>
  );
}
