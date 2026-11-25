import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis, ResponsiveContainer } from "recharts";

interface TornadoRow {
  name: string;
  low: number;
  high: number;
  range: number;
}

// Block E — top-5 sensitivity drivers. Input shape matches
// should_cost/workflow/steps/sensitivity.py's compute_sensitivity output
// ({name, rows: [{scenario, sc_result}, ...]}).
export function SensitivityTornado({ drivers }: { drivers: Array<{ name: string; rows: Array<{ scenario: string; sc_result: number }> }> }) {
  const data: TornadoRow[] = drivers.map((d) => {
    const low = d.rows.find((r) => r.scenario === "Low")?.sc_result ?? 0;
    const high = d.rows.find((r) => r.scenario === "High")?.sc_result ?? 0;
    return { name: d.name, low: Math.min(low, high), high: Math.max(low, high), range: Math.abs(high - low) };
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ left: 24, right: 24 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" fontSize={12} />
        <YAxis type="category" dataKey="name" width={160} fontSize={12} />
        <Tooltip formatter={(v: number) => `€${v.toFixed(3)}`} />
        <Bar dataKey="low" stackId="range" fill="transparent" />
        <Bar dataKey="range" stackId="range" fill="#ef6c00" />
      </BarChart>
    </ResponsiveContainer>
  );
}
