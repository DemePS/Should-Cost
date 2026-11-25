const COLORS: Record<string, string> = {
  green: "#2e7d32",
  yellow: "#b8860b",
  red: "#c62828",
  queued: "#616161",
  running: "#1565c0",
  needs_input: "#b8860b",
  done: "#2e7d32",
  failed: "#c62828",
};

export function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] ?? "#616161";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
        color: "#fff",
        backgroundColor: color,
        textTransform: "uppercase",
        letterSpacing: 0.3,
      }}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
