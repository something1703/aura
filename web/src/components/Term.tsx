"use client";

import { useEffect, useRef, useState } from "react";
import { GLOSSARY, type GlossaryTerm } from "@/lib/glossary";

const POPOVER_WIDTH = 260;

/**
 * An inline "what does this mean" trigger for a glossary term. Renders its
 * popover with `position: fixed` (computed from the trigger's own
 * bounding rect) rather than absolutely inside the DOM tree, since these
 * are used inside `overflow-x-auto` table wrappers that would otherwise
 * clip the popover.
 */
export function Term({ term, children }: { term: GlossaryTerm; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function place() {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const left = Math.min(Math.max(12, rect.left), window.innerWidth - POPOVER_WIDTH - 12);
      setCoords({ top: rect.bottom + 6, left });
    }

    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="underline decoration-dotted decoration-zinc-400 underline-offset-2 hover:decoration-orange-700"
      >
        {children}
      </button>
      {open && coords && (
        <div
          ref={popoverRef}
          style={{ position: "fixed", top: coords.top, left: coords.left, width: POPOVER_WIDTH }}
          className="z-50 rounded-lg border border-zinc-200 bg-white p-3 text-xs font-normal normal-case leading-relaxed text-zinc-700 shadow-lg"
        >
          {GLOSSARY[term]}
        </div>
      )}
    </>
  );
}
