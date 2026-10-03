import { describe, expect, it } from "vitest";
import { pickBestSlot } from "./pick-best-slot";
import type { Moment, ResultsPayload } from "../data/types";

const moments: Moment[] = [
  {
    id: "morning_rush",
    name: "Morning rush",
    time_window: "07:30–09:00",
    start_minute: 450,
    end_minute: 540,
    dwell_seconds: 90,
    dwell_label: "90s",
    zones_reached: [],
    mission: "",
    tested_live: true,
  },
  {
    id: "post_workout",
    name: "Post-workout",
    time_window: "18:00–20:00",
    start_minute: 1080,
    end_minute: 1200,
    dwell_seconds: 180,
    dwell_label: "3m",
    zones_reached: [],
    mission: "",
    tested_live: true,
  },
  {
    id: "quick_lunch",
    name: "Quick lunch",
    time_window: "12:00–14:00",
    start_minute: 720,
    end_minute: 840,
    dwell_seconds: 300,
    dwell_label: "5m",
    zones_reached: [],
    mission: "",
    tested_live: false,
  },
];

function emptyCell(overrides: Partial<ResultsPayload["cells"][string]> = {}) {
  return {
    n_real: 0,
    evidence: "dashed",
    predicted_shares: { challenger: 0.2 },
    real_shares: {},
    verdict_by_product: { challenger: "neutral" as const },
    driver_by_product: { challenger: "health" },
    explanation_by_product: { challenger: "" },
    nearly_chose: [],
    quotes: [],
    actions_by_product: {},
    ...overrides,
  };
}

describe("pickBestSlot", () => {
  it("prefers solid win over predicted win", () => {
    const results: ResultsPayload = {
      n_scored: 1,
      n_other: 0,
      accuracy: { overall: { pct: 0, n: 0 }, by_moment: {}, by_persona: {} },
      baselines: { random: { pct: 25, n: 0 }, cheapest_wins: { pct: 0, n: 0 } },
      calibration: { status: "insufficient" },
      cells: {
        "gym_regular|morning_rush": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "win" },
          predicted_shares: { challenger: 0.4 },
        }),
        "gym_regular|post_workout": emptyCell({
          n_real: 7,
          verdict_by_product: { challenger: "win" },
          predicted_shares: { challenger: 0.25 },
        }),
        "gym_regular|quick_lunch": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "neutral" },
          predicted_shares: { challenger: 0.5 },
        }),
      },
    };

    const slot = pickBestSlot({
      productId: "challenger",
      personaId: "gym_regular",
      moments,
      results,
    });

    expect(slot?.momentId).toBe("post_workout");
    expect(slot?.rankKind).toBe("solid_win");
    expect(slot?.rankLabel).toContain("Validated opportunity");
  });

  it("falls back to best predicted share when there is no win", () => {
    const results: ResultsPayload = {
      n_scored: 1,
      n_other: 0,
      accuracy: { overall: { pct: 0, n: 0 }, by_moment: {}, by_persona: {} },
      baselines: { random: { pct: 25, n: 0 }, cheapest_wins: { pct: 0, n: 0 } },
      calibration: { status: "insufficient" },
      cells: {
        "gym_regular|morning_rush": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "lose" },
          predicted_shares: { challenger: 0.12 },
        }),
        "gym_regular|post_workout": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "lose" },
          predicted_shares: { challenger: 0.2 },
        }),
        "gym_regular|quick_lunch": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "neutral" },
          predicted_shares: { challenger: 0.28 },
        }),
      },
    };

    const slot = pickBestSlot({
      productId: "challenger",
      personaId: "gym_regular",
      moments,
      results,
    });

    expect(slot?.momentId).toBe("quick_lunch");
    expect(slot?.rankKind).toBe("best_share");
    expect(slot?.rankLabel).toContain("28%");
  });

  it("labels n=0 win as predicted win", () => {
    const results: ResultsPayload = {
      n_scored: 1,
      n_other: 0,
      accuracy: { overall: { pct: 0, n: 0 }, by_moment: {}, by_persona: {} },
      baselines: { random: { pct: 25, n: 0 }, cheapest_wins: { pct: 0, n: 0 } },
      calibration: { status: "insufficient" },
      cells: {
        "gym_regular|morning_rush": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "win" },
          predicted_shares: { challenger: 0.3 },
        }),
        "gym_regular|post_workout": emptyCell({
          n_real: 0,
          verdict_by_product: { challenger: "neutral" },
          predicted_shares: { challenger: 0.4 },
        }),
      },
    };

    const slot = pickBestSlot({
      productId: "challenger",
      personaId: "gym_regular",
      moments: moments.slice(0, 2),
      results,
    });

    expect(slot?.rankKind).toBe("predicted_win");
    expect(slot?.momentId).toBe("morning_rush");
  });

  it("breaks ties with moment order", () => {
    const results: ResultsPayload = {
      n_scored: 1,
      n_other: 0,
      accuracy: { overall: { pct: 0, n: 0 }, by_moment: {}, by_persona: {} },
      baselines: { random: { pct: 25, n: 0 }, cheapest_wins: { pct: 0, n: 0 } },
      calibration: { status: "insufficient" },
      cells: {
        "gym_regular|morning_rush": emptyCell({
          n_real: 7,
          verdict_by_product: { challenger: "win" },
          predicted_shares: { challenger: 0.3 },
        }),
        "gym_regular|post_workout": emptyCell({
          n_real: 7,
          verdict_by_product: { challenger: "win" },
          predicted_shares: { challenger: 0.3 },
        }),
      },
    };

    const slot = pickBestSlot({
      productId: "challenger",
      personaId: "gym_regular",
      moments: moments.slice(0, 2),
      results,
    });

    expect(slot?.momentId).toBe("morning_rush");
  });
});
