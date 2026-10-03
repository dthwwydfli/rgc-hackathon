import type { AppPaths, ProductAction, ResultsPayload } from "./types";
import { assertObject, fetchJson } from "./parse-json";

const OWNERS = new Set(["brand", "retailer"]);
const EFFORTS = new Set(["S", "M", "L"]);

function parseProductAction(raw: unknown, label: string): ProductAction {
  const action = assertObject(raw, label);
  if (typeof action.next_step !== "string" || action.next_step.length === 0) {
    throw new Error(`${label}.next_step must be a non-empty string`);
  }
  if (action.cost_pence !== null && !Number.isInteger(action.cost_pence)) {
    throw new Error(`${label}.cost_pence must be integer or null`);
  }
  if (typeof action.owner !== "string" || !OWNERS.has(action.owner)) {
    throw new Error(`${label}.owner must be brand or retailer`);
  }
  if (typeof action.expensive_action_avoided !== "string") {
    throw new Error(`${label}.expensive_action_avoided must be a string`);
  }
  if (typeof action.effort !== "string" || !EFFORTS.has(action.effort)) {
    throw new Error(`${label}.effort must be S, M, or L`);
  }
  return {
    next_step: action.next_step,
    cost_pence: action.cost_pence as number | null,
    owner: action.owner as ProductAction["owner"],
    expensive_action_avoided: action.expensive_action_avoided,
    effort: action.effort as ProductAction["effort"],
  };
}

function parseResults(raw: unknown): ResultsPayload {
  const root = assertObject(raw, "results.json");
  const cells = assertObject(root.cells, "results.cells");
  assertObject(root.accuracy, "results.accuracy");
  assertObject(root.baselines, "results.baselines");
  assertObject(root.calibration, "results.calibration");
  if (typeof root.n_scored !== "number" || typeof root.n_other !== "number") {
    throw new Error("results.json requires n_scored and n_other");
  }

  for (const [key, cellRaw] of Object.entries(cells)) {
    const cell = assertObject(cellRaw, `results.cells.${key}`);
    const byProduct = assertObject(cell.actions_by_product, `results.cells.${key}.actions_by_product`);
    for (const [productId, actionRaw] of Object.entries(byProduct)) {
      byProduct[productId] = parseProductAction(
        actionRaw,
        `results.cells.${key}.actions_by_product.${productId}`,
      );
    }
  }

  return root as unknown as ResultsPayload;
}

export async function loadResults(paths: AppPaths) {
  try {
    const results = parseResults(await fetchJson(paths.results));
    return { results, usedMock: false, source: results.source || "live" };
  } catch (liveError) {
    const results = parseResults(await fetchJson(paths.mockResults));
    return {
      results,
      usedMock: true,
      source: "mock",
      liveError: liveError instanceof Error ? liveError.message : String(liveError),
    };
  }
}

export function startResultsRefresh(
  paths: AppPaths,
  onUpdate: (payload: Awaited<ReturnType<typeof loadResults>>) => void,
  intervalMs = 30000,
): () => void {
  const timerId = window.setInterval(async () => {
    try {
      const payload = await loadResults(paths);
      onUpdate(payload);
    } catch (error) {
      console.warn("results refresh failed", {
        cause: error instanceof Error ? error.message : String(error),
      });
    }
  }, intervalMs);

  return () => window.clearInterval(timerId);
}
