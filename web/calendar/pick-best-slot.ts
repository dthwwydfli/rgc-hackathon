import type { BestSlot, Moment, RankKind, ResultCell, ResultsPayload, Verdict } from "../data/types";
import { cellKey } from "../data/parse-json";

const RANK_ORDER: Record<RankKind, number> = {
  solid_win: 0,
  directional_win: 1,
  predicted_win: 2,
  best_share: 3,
};

const RANK_LABEL: Record<RankKind, string> = {
  solid_win: "Validated opportunity",
  directional_win: "Early signal",
  predicted_win: "Model-led opportunity",
  best_share: "Highest predicted share",
};

function rankKindFor(verdict: Verdict | undefined, nReal: number): RankKind | null {
  if (verdict === "win" && nReal >= 5) {
    return "solid_win";
  }
  if (verdict === "win" && nReal > 0) {
    return "directional_win";
  }
  if (verdict === "win") {
    return "predicted_win";
  }
  return null;
}

function formatRankLabel(kind: RankKind, predictedShare: number): string {
  if (kind === "best_share") {
    return `${RANK_LABEL[kind]} · ${Math.round(predictedShare * 100)}%`;
  }
  return RANK_LABEL[kind];
}

interface Candidate {
  momentId: string;
  kind: RankKind;
  nReal: number;
  predictedShare: number;
  momentIndex: number;
}

/**
 * Picks the single best moment slot for a product under one persona.
 * Returns null only when the product has no cells at all.
 */
export function pickBestSlot(args: {
  productId: string;
  personaId: string;
  moments: Moment[];
  results: ResultsPayload;
}): BestSlot | null {
  const { productId, personaId, moments, results } = args;
  const candidates: Candidate[] = [];

  for (const [momentIndex, moment] of moments.entries()) {
    const key = cellKey(personaId, moment.id);
    const cell: ResultCell | undefined = results.cells[key];
    if (!cell) {
      continue;
    }

    const nReal = cell.n_real ?? 0;
    const predictedShare = cell.predicted_shares?.[productId] ?? 0;
    const verdict = cell.verdict_by_product?.[productId];
    const winKind = rankKindFor(verdict, nReal);

    if (winKind) {
      candidates.push({
        momentId: moment.id,
        kind: winKind,
        nReal,
        predictedShare,
        momentIndex,
      });
      continue;
    }

    candidates.push({
      momentId: moment.id,
      kind: "best_share",
      nReal,
      predictedShare,
      momentIndex,
    });
  }

  if (candidates.length === 0) {
    return null;
  }

  candidates.sort((a, b) => {
    const rankDiff = RANK_ORDER[a.kind] - RANK_ORDER[b.kind];
    if (rankDiff !== 0) {
      return rankDiff;
    }
    if (b.nReal !== a.nReal) {
      return b.nReal - a.nReal;
    }
    if (b.predictedShare !== a.predictedShare) {
      return b.predictedShare - a.predictedShare;
    }
    return a.momentIndex - b.momentIndex;
  });

  const winner = candidates[0];
  return {
    momentId: winner.momentId,
    personaId,
    productId,
    rankKind: winner.kind,
    rankLabel: formatRankLabel(winner.kind, winner.predictedShare),
    nReal: winner.nReal,
    predictedShare: winner.predictedShare,
  };
}
