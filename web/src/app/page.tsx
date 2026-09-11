import { HowItWorks } from "@/components/HowItWorks";
import { AnalyzeDemo } from "@/components/AnalyzeDemo";

export default function Home() {
  return (
    <>
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-3.5">
          <div className="flex items-baseline gap-2.5">
            <span className="text-lg font-extrabold tracking-tight text-zinc-900">AURA</span>
            <span className="text-sm text-zinc-500">Design for success. Validate for failure.</span>
          </div>
          <nav className="flex gap-5 text-sm text-zinc-600">
            <a href="#how-it-works" className="hover:text-orange-800">
              How it works
            </a>
            <a href="#try-it" className="hover:text-orange-800">
              Try it
            </a>
            <a href="#results" className="hover:text-orange-800">
              Results
            </a>
          </nav>
        </div>
      </header>

      <main>
        <section className="border-b border-zinc-200 bg-gradient-to-b from-orange-50 to-[#f7f7f5]">
          <div className="mx-auto max-w-3xl px-5 py-20 text-center">
            <h1 className="text-3xl font-bold leading-tight text-zinc-900 sm:text-4xl">
              An architecture decision engine, not a service catalog.
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-base text-zinc-600">
              AURA converts a workload&apos;s business and non-functional requirements into
              candidate AWS architectures, evaluates them against hard constraints and weighted
              trade-offs, simulates eight failure scenarios per candidate, estimates cost across
              four load scenarios, and produces an evidence-backed recommendation with generated
              ADRs — all deterministic, all auditable, nothing fabricated.
            </p>
            <a
              href="#try-it"
              className="mt-7 inline-block rounded-full bg-orange-800 px-7 py-3 text-sm font-semibold text-white transition hover:opacity-90"
            >
              Run a live analysis ↓
            </a>
          </div>
        </section>

        <HowItWorks />
        <AnalyzeDemo />
      </main>

      <footer className="border-t border-zinc-200 px-5 py-8 text-center text-sm text-zinc-500">
        AURA — local, deterministic architecture analysis. Nothing on this page calls AWS or
        creates infrastructure.
      </footer>
    </>
  );
}
