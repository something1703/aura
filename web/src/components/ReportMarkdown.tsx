"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Element } from "hast";
import { MermaidDiagram } from "./MermaidDiagram";

function textOf(node: Element): string {
  return node.children
    .map((child) => (child.type === "text" ? child.value : child.type === "element" ? textOf(child) : ""))
    .join("");
}

function findCodeChild(node?: Element): Element | undefined {
  return node?.children.find((child): child is Element => child.type === "element" && child.tagName === "code");
}

function classNamesOf(node?: Element): string[] {
  const value = node?.properties?.className;
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") return [value];
  return [];
}

export function ReportMarkdown({ markdown }: { markdown: string }) {
  return (
    <div className="prose prose-sm prose-zinc max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre({ node, children, ...rest }) {
            const codeNode = findCodeChild(node);
            if (codeNode && classNamesOf(codeNode).includes("language-mermaid")) {
              return <MermaidDiagram chart={textOf(codeNode)} />;
            }
            return <pre {...rest}>{children}</pre>;
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
