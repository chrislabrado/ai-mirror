import type { Claim, Critique, GroundingStats, ReportBlockOut } from "@/types/api";

/**
 * Tolerant readers for the `structured` payload on report blocks.
 * The backend guarantees the shapes; these guards just keep the UI from
 * crashing on older reports that predate the claims schema.
 */

function structuredField(block: ReportBlockOut, key: string): unknown {
  const s = block.structured;
  if (!s || typeof s !== "object") return undefined;
  return (s as Record<string, unknown>)[key];
}

export function blockClaims(block: ReportBlockOut): Claim[] {
  const claims = structuredField(block, "claims");
  if (!Array.isArray(claims)) return [];
  return claims.filter(
    (c): c is Claim => !!c && typeof c === "object" && typeof (c as Claim).claim === "string",
  );
}

export function blockCritique(block: ReportBlockOut): Critique | null {
  const critique = structuredField(block, "critique");
  if (!critique || typeof critique !== "object") return null;
  const c = critique as Critique;
  return Array.isArray(c.verdicts) ? c : null;
}

export function blockGrounding(block: ReportBlockOut): GroundingStats | null {
  const grounding = structuredField(block, "grounding");
  if (!grounding || typeof grounding !== "object") return null;
  const g = grounding as GroundingStats;
  return typeof g.total_claims === "number" ? g : null;
}

export function isCritiqueBlock(block: ReportBlockOut): boolean {
  return block.block_type === "critique";
}

/** Report-level grounding stats live on the trailing critique block. */
export function reportGrounding(blocks: ReportBlockOut[]): GroundingStats | null {
  for (const block of blocks) {
    if (isCritiqueBlock(block)) {
      const g = blockGrounding(block);
      if (g) return g;
    }
  }
  return null;
}
