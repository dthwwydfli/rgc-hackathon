import type { AppPaths, PredictionsPayload } from "./types";
import { assertObject, fetchJson } from "./parse-json";

function parsePredictions(raw: unknown): PredictionsPayload {
  const root = assertObject(raw, "predictions.json");
  assertObject(root.cells, "predictions.cells");
  return root as unknown as PredictionsPayload;
}

export async function loadPredictions(paths: AppPaths) {
  try {
    const predictions = parsePredictions(await fetchJson(paths.predictions));
    return { predictions, usedMock: false, source: predictions.source || "live" };
  } catch (liveError) {
    const predictions = parsePredictions(await fetchJson(paths.mockPredictions));
    return {
      predictions,
      usedMock: true,
      source: "mock",
      liveError: liveError instanceof Error ? liveError.message : String(liveError),
    };
  }
}
