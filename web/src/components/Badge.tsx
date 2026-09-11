const COLORS: Record<string, string> = {
  pass: "bg-emerald-100 text-emerald-800",
  eligible: "bg-emerald-100 text-emerald-800",
  low: "bg-emerald-100 text-emerald-800",
  high_confidence: "bg-emerald-100 text-emerald-800",
  warn: "bg-amber-100 text-amber-800",
  medium: "bg-amber-100 text-amber-800",
  fail: "bg-red-100 text-red-800",
  ineligible: "bg-red-100 text-red-800",
  critical: "bg-red-100 text-red-800",
  not_evaluated: "bg-zinc-100 text-zinc-600",
};

export function Badge({ status }: { status: string }) {
  const key = status.toLowerCase();
  const cls = COLORS[key] ?? "bg-zinc-100 text-zinc-600";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${cls}`}>
      {status}
    </span>
  );
}
