/**
 * COMPROMISE(fe, 2026-10-03): client-side what-if uses a visibility heuristic,
 * not the Python Stage 1+2 engine.
 * Ceiling: diverges from locked sim once weights or sampling change.
 * Exit: call sim/engine.py (or a thin HTTP wrapper) and delete this function.
 */
export function simulateWhatIfShares(args: {
  baseShares: Record<string, number>;
  productId: string;
  fromZone: string;
  toZone: string;
  pricePence: number;
  basePricePence: number;
}): Record<string, number> {
  const { baseShares, productId, fromZone, toZone, pricePence, basePricePence } = args;
  const shares = { ...baseShares };
  const zoneBoost: Record<string, number> = {
    snack_aisle: 0,
    entrance_chiller: 0.08,
    till: 0.15,
  };
  const boost = (zoneBoost[toZone] || 0) - (zoneBoost[fromZone] || 0);
  const priceDelta = (basePricePence - pricePence) / 1000;

  let focus = shares[productId] || 0;
  focus = Math.min(0.95, Math.max(0.01, focus + boost + priceDelta));

  const others = Object.keys(shares).filter((id) => id !== productId);
  const otherTotal = others.reduce((sum, id) => sum + shares[id], 0) || 1;
  const remaining = 1 - focus;
  const next: Record<string, number> = { [productId]: focus };
  for (const id of others) {
    next[id] = (shares[id] / otherTotal) * remaining;
  }
  return next;
}
