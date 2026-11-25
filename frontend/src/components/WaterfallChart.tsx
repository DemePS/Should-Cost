import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis, ResponsiveContainer } from "recharts";

const ORDER = [
  "material_eur",
  "conversion_eur",
  "manufacturing_costs_eur",
  "pl_eur",
  "overheads_eur",
  "margin_eur",
  "should_cost_eur",
  "impact_eur",
  "current_price_eur",
];
const LABELS: Record<string, string> = {
  material_eur: "Material",
  conversion_eur: "Conversion",
  manufacturing_costs_eur: "Mfg Costs",
  pl_eur: "Packaging & Logistics",
  overheads_eur: "Overheads",
  margin_eur: "Margin",
  should_cost_eur: "Should Cost",
  impact_eur: "Impact",
  current_price_eur: "Current Price",
};

// Block A — the 5-bucket waterfall, in fixed SKILL.md order. Deliberately a bar chart,
// not a true floating waterfall, to keep this dependency-light (recharts has no native
// waterfall type); each bucket's bar height is still read left-to-right in the same
// order the skill specifies.
export function WaterfallChart({ costBuild }: { costBuild: Record<string, number> }) {
  const data = ORDER.filter((key) => key in costBuild).map((key) => ({ name: LABELS[key], value: costBuild[key] }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 40, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" angle={-30} textAnchor="end" height={60} fontSize={12} />
        <YAxis fontSize={12} />
        <Tooltip formatter={(v: number) => `€${v.toFixed(3)}`} />
        <Bar dataKey="value" fill="#1565c0" />
      </BarChart>
    </ResponsiveContainer>
  );
}
