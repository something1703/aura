import type { CandidateScore } from "./api";

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** A one-sentence, data-driven "why this candidate" summary. */
export function explainRecommendation(score: CandidateScore): string {
  const withContribution = score.dimension_scores.map((d) => ({
    ...d,
    contribution: (d.value * d.weight) / 100,
  }));

  const byContribution = [...withContribution].sort((a, b) => b.contribution - a.contribution);
  const strengths = byContribution
    .slice(0, 2)
    .map((d) => `${titleCase(d.dimension)} (${d.value}/100)`)
    .join(" and ");

  const weakest = [...withContribution].sort((a, b) => a.value - b.value)[0];

  let sentence = `Weighted highest by ${strengths}.`;
  if (weakest && weakest.value < 70) {
    sentence += ` Its weakest dimension is ${titleCase(weakest.dimension)} (${weakest.value}/100).`;
  }
  return sentence;
}
