"use client";

import { useEffect, useId, useRef } from "react";
import mermaid from "mermaid";

let mermaidInitialized = false;

function ensureMermaidInitialized() {
  if (!mermaidInitialized) {
    mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
    mermaidInitialized = true;
  }
}

/**
 * Renders a Mermaid diagram string to SVG. The chart text always comes from
 * our own backend (a generated topology, never third-party/user input), so
 * injecting mermaid's own SVG output is safe.
 */
export function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const renderId = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;

  useEffect(() => {
    let cancelled = false;
    ensureMermaidInitialized();

    mermaid
      .render(renderId, chart)
      .then(({ svg }) => {
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      })
      .catch((err: unknown) => {
        if (!cancelled && containerRef.current) {
          containerRef.current.textContent = `Diagram error: ${String(err)}`;
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chart, renderId]);

  return <div ref={containerRef} className="mermaid-diagram overflow-x-auto" />;
}
