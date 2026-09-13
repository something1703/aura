import { Badge } from "./Badge";

const ENTRIES: { status: string; meaning: string }[] = [
  { status: "PASS", meaning: "meets the requirement" },
  { status: "WARN", meaning: "meets it, but with a caveat worth reading" },
  { status: "FAIL", meaning: "violates the requirement" },
  { status: "NOT_EVALUATED", meaning: "not applicable to this workload" },
];

export function Legend() {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-xs text-zinc-600">
      <span className="font-semibold text-zinc-700">Reading the badges:</span>
      {ENTRIES.map((e) => (
        <span key={e.status} className="flex items-center gap-1.5">
          <Badge status={e.status} />
          {e.meaning}
        </span>
      ))}
    </div>
  );
}
