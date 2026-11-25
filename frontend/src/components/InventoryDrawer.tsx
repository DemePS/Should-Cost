import type { Job } from "../api/client";

// Screen 5 — files read, how spend data was found, match type, open items. Rendered as
// a slide-out drawer from JobDetailPage rather than a separate route, since it's always
// scoped to "this job" and never navigated to independently.
export function InventoryDrawer({ job, onClose }: { job: Job; onClose: () => void }) {
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: 420,
        height: "100%",
        backgroundColor: "#fff",
        boxShadow: "-4px 0 16px rgba(0,0,0,0.15)",
        padding: 20,
        overflowY: "auto",
        zIndex: 50,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Inventory &amp; Sources</h3>
        <button onClick={onClose}>Close</button>
      </div>

      <section style={{ marginTop: 16 }}>
        <h4>Spend data</h4>
        {job.spend_lookup ? (
          <>
            <p>
              Match type: <strong>{job.spend_lookup.match_type.replace(/_/g, " ")}</strong>
              {job.spend_lookup.source_filename && <> — {job.spend_lookup.source_filename}</>}
            </p>
            {job.spend_lookup.variants_found.length > 0 && (
              <p>Variants aggregated: {job.spend_lookup.variants_found.join(", ")}</p>
            )}
            {job.spend_lookup.plausibility_note && <p style={{ color: "#b8860b" }}>{job.spend_lookup.plausibility_note}</p>}
            <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                  <th>Supplier</th>
                  <th>Country</th>
                  <th>Type</th>
                  <th>Volume</th>
                  <th>Price</th>
                </tr>
              </thead>
              <tbody>
                {job.spend_lookup.suppliers.map((s) => (
                  <tr key={s.supplier_name} style={{ borderBottom: "1px solid #eee" }}>
                    <td>{s.supplier_name}</td>
                    <td>{s.country ?? "—"}</td>
                    <td>{s.supplier_type.replace("_", " ")}</td>
                    <td>{s.annual_volume.toLocaleString()}</td>
                    <td>
                      €{s.current_avg_price.toFixed(3)}
                      {s.is_manual_override && " (manual)"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p>Not available yet.</p>
        )}
      </section>

      <section style={{ marginTop: 16 }}>
        <h4>Documents read ({job.discovery_documents.length})</h4>
        <ul style={{ paddingLeft: 18 }}>
          {job.discovery_documents.map((d) => (
            <li key={d.filename} style={{ fontSize: 13 }}>
              {d.filename}
            </li>
          ))}
          {job.discovery_documents.length === 0 && <li style={{ fontSize: 13, color: "#757575" }}>None yet.</li>}
        </ul>
      </section>

      {job.pending_question && (
        <section style={{ marginTop: 16 }}>
          <h4>Open item</h4>
          <p style={{ fontSize: 13 }}>{job.pending_question.question}</p>
        </section>
      )}
    </div>
  );
}
