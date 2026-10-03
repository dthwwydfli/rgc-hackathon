/**
 * Boundary parse for Moment Fit JSON payloads.
 * COMPROMISE(fe, 2026-10-03): lightweight shape checks only.
 * Ceiling: misses deep schema drift. Exit: shared JSON Schema when BE stabilises.
 */

export function assertObject(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

export function assertArray(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`);
  }
  return value;
}

export async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: HTTP ${response.status}`);
  }
  return response.json();
}

export function cellKey(personaId: string, momentId: string): string {
  return `${personaId}|${momentId}`;
}

export function formatPence(pricePence: number): string {
  if (!Number.isInteger(pricePence)) {
    throw new Error("price_pence must be an integer");
  }
  return `£${(pricePence / 100).toFixed(2)}`;
}

export function formatPct(pct: number, n: number): string {
  if (typeof pct !== "number" || typeof n !== "number") {
    throw new Error("formatPct requires pct and n");
  }
  return `${pct}% (n=${n})`;
}

export function shareToPct(share: number | undefined): number | null {
  if (typeof share !== "number") {
    return null;
  }
  return Math.round(share * 100);
}

export function evidenceTone(nReal: number): "solid" | "low" | "dashed" {
  if (nReal >= 5) {
    return "solid";
  }
  if (nReal > 0) {
    return "low";
  }
  return "dashed";
}

export function formatCostPence(costPence: number | null): string {
  if (costPence === null) {
    return "Cost unknown";
  }
  return formatPence(costPence);
}
