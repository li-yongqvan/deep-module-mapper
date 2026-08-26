/**
 * Naive deep-module scoring (D2).
 *
 * Heuristic: a module is *deep* when its interface is small relative to its
 * implementation. We approximate implementation thickness with the largest
 * port `line` number (the parser has no LOC field — audit M3), and interface
 * size with the port count:
 *
 *   ratio = maxLine / portCount        (portCount > 0)
 *
 * KNOWN BIAS (documented per audit M3 / handoff §4):
 *  - A big file whose public ports all live near the top is scored shallow
 *    even though its implementation is thick.
 *  - A tiny file with a single port near the bottom is scored deep.
 *
 * THRESHOLDS ARE NAIVE AND TENTATIVE. Refine in a follow-up issue after
 * collecting the real distribution (§8.4 / appendix A of the design doc).
 */
export type DepthScore = 'deep' | 'moderate' | 'shallow';

/** Interface-to-implementation ratio at or above which a module is "deep". */
export const DEPTH_THRESHOLD_DEEP = 50;
/** Ratio at or above which a module is "moderate" (below it -> shallow). */
export const DEPTH_THRESHOLD_MODERATE = 15;

export interface PortLike {
  line: number;
}

/** Score a module from its public ports. Zero-port modules are shallow. */
export function depthScore(ports: PortLike[]): DepthScore {
  if (ports.length === 0) return 'shallow';
  const maxLine = Math.max(...ports.map((p) => p.line));
  const ratio = maxLine / ports.length;
  if (ratio >= DEPTH_THRESHOLD_DEEP) return 'deep';
  if (ratio >= DEPTH_THRESHOLD_MODERATE) return 'moderate';
  return 'shallow';
}

/** Traffic-light color token for a score (matches prototype palette §2.6). */
export function scoreColor(score: DepthScore): string {
  switch (score) {
    case 'deep':
      return '#34d399'; // --good
    case 'moderate':
      return '#fbbf24'; // --mid
    case 'shallow':
      return '#f87171'; // --warn
  }
}
