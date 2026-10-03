/**
 * One-shot seed densifier. Run: node scripts/densify-seed.mjs
 * Writes products/moments/results/predictions for a full week grid.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

const moments = [
  {
    id: "morning_rush",
    name: "Morning rush",
    time_window: "07:30–09:00",
    start_minute: 450,
    end_minute: 540,
    dwell_seconds: 90,
    dwell_label: "assumption: about 90 seconds",
    zones_reached: ["entrance_chiller", "till"],
    mission: "Fuel up before the commute",
    tested_live: true,
  },
  {
    id: "mid_morning",
    name: "Mid-morning top-up",
    time_window: "09:30–11:00",
    start_minute: 570,
    end_minute: 660,
    dwell_seconds: 120,
    dwell_label: "assumption: about 2 minutes",
    zones_reached: ["entrance_chiller", "snack_aisle"],
    mission: "Desk snack between meetings",
    tested_live: false,
  },
  {
    id: "quick_lunch",
    name: "Quick lunch",
    time_window: "12:00–14:00",
    start_minute: 720,
    end_minute: 840,
    dwell_seconds: 300,
    dwell_label: "assumption: about 5 minutes",
    zones_reached: ["entrance_chiller", "till", "snack_aisle"],
    mission: "Lunch that fits the break",
    tested_live: false,
  },
  {
    id: "afternoon_lull",
    name: "Afternoon lull",
    time_window: "14:30–16:00",
    start_minute: 870,
    end_minute: 960,
    dwell_seconds: 180,
    dwell_label: "assumption: about 3 minutes",
    zones_reached: ["snack_aisle", "till"],
    mission: "Fight the 3pm slump",
    tested_live: false,
  },
  {
    id: "commute_home",
    name: "Commute home",
    time_window: "16:30–17:45",
    start_minute: 990,
    end_minute: 1065,
    dwell_seconds: 90,
    dwell_label: "assumption: about 90 seconds",
    zones_reached: ["entrance_chiller", "till"],
    mission: "Grab something for the train",
    tested_live: true,
  },
  {
    id: "post_workout",
    name: "Post-workout",
    time_window: "18:00–20:00",
    start_minute: 1080,
    end_minute: 1200,
    dwell_seconds: 180,
    dwell_label: "assumption: about 3 minutes",
    zones_reached: ["entrance_chiller", "till", "snack_aisle"],
    mission: "Recover and refuel",
    tested_live: true,
  },
  {
    id: "evening_treat",
    name: "Evening treat",
    time_window: "20:00–21:00",
    start_minute: 1200,
    end_minute: 1260,
    dwell_seconds: 240,
    dwell_label: "assumption: about 4 minutes",
    zones_reached: ["snack_aisle", "till"],
    mission: "Reward after the day",
    tested_live: false,
  },
  {
    id: "late_night",
    name: "Late night",
    time_window: "21:00–23:00",
    start_minute: 1260,
    end_minute: 1380,
    dwell_seconds: 300,
    dwell_label: "assumption: about 5 minutes",
    zones_reached: ["entrance_chiller", "till", "snack_aisle"],
    mission: "Treat or top-up",
    tested_live: false,
  },
];

const products = [
  {
    id: "banana",
    name: "Bananas",
    brand: "Loose produce",
    barcode: "4056489697954",
    price_pence: 30,
    price_date: "2026-10-03",
    zone: "entrance_chiller",
    taste_score: 0.7,
    health_score: 0.95,
    convenience_score: 0.85,
    familiarity_score: 0.95,
    protein_g: 1.1,
    sugar_g: 12.0,
    kcal: 89,
    fop_claim: "Fairtrade",
    image_path: "assets/products/banana.jpg",
  },
  {
    id: "protein_bar",
    name: "Grenade High Protein Bar",
    brand: "Grenade",
    barcode: "5060811383254",
    price_pence: 250,
    price_date: "2026-10-03",
    zone: "snack_aisle",
    taste_score: 0.65,
    health_score: 0.75,
    convenience_score: 0.9,
    familiarity_score: 0.7,
    protein_g: 20.0,
    sugar_g: 1.5,
    kcal: 220,
    fop_claim: "High protein, low sugar",
    image_path: "assets/products/protein_bar.jpg",
  },
  {
    id: "croissant",
    name: "Croissants",
    brand: "Brioche Pasquier",
    barcode: "3256540000339",
    price_pence: 180,
    price_date: "2026-10-03",
    zone: "till",
    taste_score: 0.85,
    health_score: 0.25,
    convenience_score: 0.7,
    familiarity_score: 0.8,
    protein_g: 5.0,
    sugar_g: 6.0,
    kcal: 280,
    fop_claim: "Fresh bakery",
    image_path: "assets/products/croissant.jpg",
  },
  {
    id: "challenger",
    name: "Cocoa Hazelnut Protein Bar",
    brand: "Nakd",
    barcode: "5060088700112",
    price_pence: 199,
    price_date: "2026-10-03",
    zone: "snack_aisle",
    taste_score: 0.7,
    health_score: 0.8,
    convenience_score: 0.85,
    familiarity_score: 0.35,
    protein_g: 9.0,
    sugar_g: 18.0,
    kcal: 180,
    fop_claim: "100% natural ingredients",
    image_path: "assets/products/challenger.jpg",
  },
  {
    id: "oat_bar",
    name: "Nature Valley Oats & Honey",
    brand: "Nature Valley",
    barcode: "8410076470126",
    price_pence: 89,
    price_date: "2026-10-03",
    zone: "snack_aisle",
    taste_score: 0.72,
    health_score: 0.55,
    convenience_score: 0.88,
    familiarity_score: 0.85,
    protein_g: 4.0,
    sugar_g: 11.0,
    kcal: 190,
    fop_claim: "Wholegrain oats",
  },
  {
    id: "greek_yogurt",
    name: "Fage Total 0%",
    brand: "Fage",
    barcode: "5201054010015",
    price_pence: 120,
    price_date: "2026-10-03",
    zone: "entrance_chiller",
    taste_score: 0.6,
    health_score: 0.9,
    convenience_score: 0.65,
    familiarity_score: 0.75,
    protein_g: 10.0,
    sugar_g: 4.0,
    kcal: 97,
    fop_claim: "High protein",
  },
  {
    id: "apple",
    name: "Royal Gala Apples",
    brand: "Loose produce",
    barcode: "0000000001001",
    price_pence: 40,
    price_date: "2026-10-03",
    zone: "entrance_chiller",
    taste_score: 0.75,
    health_score: 0.95,
    convenience_score: 0.8,
    familiarity_score: 0.98,
    protein_g: 0.3,
    sugar_g: 10.0,
    kcal: 52,
    fop_claim: "Fresh fruit",
  },
  {
    id: "energy_gel",
    name: "SiS GO Isotonic Gel",
    brand: "Science in Sport",
    barcode: "5025322000011",
    price_pence: 175,
    price_date: "2026-10-03",
    zone: "snack_aisle",
    taste_score: 0.45,
    health_score: 0.5,
    convenience_score: 0.95,
    familiarity_score: 0.4,
    protein_g: 0.0,
    sugar_g: 22.0,
    kcal: 87,
    fop_claim: "Isotonic energy",
  },
  {
    id: "trail_mix",
    name: "Mixed Nuts & Raisins",
    brand: "Own brand",
    barcode: "0000000001002",
    price_pence: 150,
    price_date: "2026-10-03",
    zone: "snack_aisle",
    taste_score: 0.8,
    health_score: 0.7,
    convenience_score: 0.82,
    familiarity_score: 0.7,
    protein_g: 8.0,
    sugar_g: 14.0,
    kcal: 230,
    fop_claim: "No added sugar",
  },
  {
    id: "dark_chocolate",
    name: "Lindt Excellence 85%",
    brand: "Lindt",
    barcode: "7610400015001",
    price_pence: 220,
    price_date: "2026-10-03",
    zone: "till",
    taste_score: 0.9,
    health_score: 0.45,
    convenience_score: 0.85,
    familiarity_score: 0.8,
    protein_g: 9.0,
    sugar_g: 11.0,
    kcal: 250,
    fop_claim: "Cocoa solids 85%",
  },
  {
    id: "rice_cakes",
    name: "Kallo Lightly Salted Rice Cakes",
    brand: "Kallo",
    barcode: "5013665101011",
    price_pence: 110,
    price_date: "2026-10-03",
    zone: "snack_aisle",
    taste_score: 0.4,
    health_score: 0.65,
    convenience_score: 0.9,
    familiarity_score: 0.6,
    protein_g: 1.5,
    sugar_g: 0.2,
    kcal: 35,
    fop_claim: "Gluten free",
  },
  {
    id: "cold_brew",
    name: "Starbucks Cold Brew Can",
    brand: "Starbucks",
    barcode: "0120000010011",
    price_pence: 230,
    price_date: "2026-10-03",
    zone: "entrance_chiller",
    taste_score: 0.7,
    health_score: 0.35,
    convenience_score: 0.92,
    familiarity_score: 0.85,
    protein_g: 0.5,
    sugar_g: 8.0,
    kcal: 70,
    fop_claim: "Ready to drink",
  },
  {
    id: "hummus_pot",
    name: "Sabra Classic Hummus",
    brand: "Sabra",
    barcode: "0000000001003",
    price_pence: 160,
    price_date: "2026-10-03",
    zone: "entrance_chiller",
    taste_score: 0.75,
    health_score: 0.7,
    convenience_score: 0.55,
    familiarity_score: 0.65,
    protein_g: 6.0,
    sugar_g: 1.0,
    kcal: 170,
    fop_claim: "Plant protein",
  },
  {
    id: "protein_shake",
    name: "Puffy Protein Shake Vanilla",
    brand: "Puffy",
    barcode: "0000000001004",
    price_pence: 280,
    price_date: "2026-10-03",
    zone: "entrance_chiller",
    taste_score: 0.68,
    health_score: 0.8,
    convenience_score: 0.95,
    familiarity_score: 0.45,
    protein_g: 25.0,
    sugar_g: 3.0,
    kcal: 160,
    fop_claim: "25g protein",
  },
];

/** Best solid-win moment per product (spreads events across the day). */
const winnerByProduct = {
  banana: "morning_rush",
  croissant: "morning_rush",
  cold_brew: "mid_morning",
  oat_bar: "mid_morning",
  hummus_pot: "quick_lunch",
  greek_yogurt: "quick_lunch",
  apple: "afternoon_lull",
  rice_cakes: "afternoon_lull",
  trail_mix: "commute_home",
  energy_gel: "commute_home",
  challenger: "post_workout",
  protein_bar: "post_workout",
  protein_shake: "post_workout",
  dark_chocolate: "evening_treat",
};

const personas = ["gym_regular", "budget_shopper", "rushed_commuter"];

function defaultAction(productId, momentId) {
  return {
    next_step: `Test ${productId.replaceAll("_", " ")} in ${momentId.replaceAll("_", " ")}`,
    cost_pence: 500,
    owner: productId.includes("banana") || productId.includes("apple") ? "brand" : "retailer",
    expensive_action_avoided: "National TV burst before placement proof",
    effort: "S",
  };
}

function buildCell(personaId, momentId) {
  const predicted_shares = {};
  const real_shares = {};
  const verdict_by_product = {};
  const driver_by_product = {};
  const explanation_by_product = {};
  const actions_by_product = {};

  const winners = products.filter((p) => winnerByProduct[p.id] === momentId);
  const losers = products.filter((p) => winnerByProduct[p.id] !== momentId);

  let remaining = 1;
  for (const [index, product] of winners.entries()) {
    const share = winners.length === 1 ? 0.42 : index === 0 ? 0.28 : 0.18;
    predicted_shares[product.id] = share;
    real_shares[product.id] = share;
    remaining -= share;
    verdict_by_product[product.id] = "win";
    driver_by_product[product.id] = "health";
    explanation_by_product[product.id] = `${product.name} wins ${momentId} for ${personaId}.`;
    actions_by_product[product.id] = defaultAction(product.id, momentId);
  }

  const perLoser = losers.length > 0 ? remaining / losers.length : 0;
  for (const product of losers) {
    predicted_shares[product.id] = Number(perLoser.toFixed(4));
    real_shares[product.id] = Number((perLoser * 0.9).toFixed(4));
    verdict_by_product[product.id] = "lose";
    driver_by_product[product.id] = "visibility";
    explanation_by_product[product.id] = `${product.name} weaker in ${momentId}.`;
    actions_by_product[product.id] = defaultAction(product.id, momentId);
  }

  const nReal = winners.length > 0 ? 6 : 0;

  return {
    n_real: nReal,
    evidence: nReal >= 5 ? "solid" : "dashed",
    predicted_shares,
    real_shares,
    verdict_by_product,
    driver_by_product,
    explanation_by_product,
    nearly_chose: winners[0]
      ? [{ product_id: winners[0].id, reason: "Closest alternative", count: 2 }]
      : [],
    quotes: [
      {
        response_id: `mock-${personaId}-${momentId}`,
        text: `Went for something quick in ${momentId.replaceAll("_", " ")}.`,
      },
    ],
    actions_by_product,
  };
}

function buildResults() {
  const cells = {};
  for (const personaId of personas) {
    for (const moment of moments) {
      cells[`${personaId}|${moment.id}`] = buildCell(personaId, moment.id);
    }
  }

  const by_moment = {};
  for (const moment of moments) {
    by_moment[moment.id] = { pct: 48 + (moment.id.length % 7), n: 12 };
  }

  return {
    updated_at: "2026-10-03T15:00:00Z",
    source: "mock",
    note: "Dense placeholder results for FE week grid. Not validated.",
    n_scored: 96,
    n_other: 8,
    accuracy: {
      overall: { pct: 51, n: 96 },
      by_moment,
      by_persona: {
        gym_regular: { pct: 55, n: 32 },
        budget_shopper: { pct: 50, n: 32 },
        rushed_commuter: { pct: 48, n: 32 },
      },
    },
    baselines: {
      random: { pct: 7, n: 96 },
      cheapest_wins: { pct: 22, n: 96 },
    },
    cells,
    gaps: {
      say_vs_do: [
        {
          summary: "Said healthy, chose pastry at till",
          count: 4,
          response_ids: ["mock-g1", "mock-g2"],
        },
      ],
      familiarity_pick_share: { pct: 31, n: 96 },
    },
    calibration: {
      status: "insufficient",
      message: "Not enough held-out data to calibrate yet",
    },
  };
}

function buildPredictions() {
  const cells = {};
  for (const personaId of personas) {
    for (const moment of moments) {
      const cell = buildCell(personaId, moment.id);
      const top = Object.entries(cell.predicted_shares).sort((a, b) => b[1] - a[1])[0];
      cells[`${personaId}|${moment.id}`] = {
        persona_id: personaId,
        moment_id: moment.id,
        predicted_shares: cell.predicted_shares,
        top_pick: top[0],
        driver: cell.driver_by_product[top[0]],
        explanation: cell.explanation_by_product[top[0]],
      };
    }
  }
  return {
    locked_at: "2026-10-03T10:00:00Z",
    git_commit: "seed-dense-001",
    source: "mock",
    cells,
  };
}

function writeJson(relPath, data) {
  const full = path.join(root, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, `${JSON.stringify(data, null, 2)}\n`);
  console.log("wrote", relPath);
}

const productsPayload = {
  products: products.map((product) => ({
    ...product,
    taste_score_source: "team judgement",
    health_score_source: "team judgement",
    convenience_score_source: "team judgement",
    familiarity_score_source: "team judgement",
  })),
};

const momentsPayload = {
  visibility_by_zone: {
    label: "assumption",
    note: "Chance a shopper notices a product in that zone given dwell band.",
    zones: {
      till: { dwell_up_to_2_min: 0.95, dwell_over_2_min: 0.95 },
      entrance_chiller: { dwell_up_to_2_min: 0.9, dwell_over_2_min: 0.9 },
      snack_aisle: { dwell_up_to_2_min: 0.3, dwell_over_2_min: 0.8 },
    },
  },
  moments,
};

const results = buildResults();
const predictions = buildPredictions();

writeJson("config/products.json", productsPayload);
writeJson("config/moments.json", momentsPayload);
writeJson("web/mock/products.json", productsPayload);
writeJson("web/mock/moments.json", momentsPayload);
writeJson("web/mock/results.json", results);
writeJson("web/mock/predictions.json", predictions);
writeJson("out/results.json", { ...results, source: "seed" });
writeJson("out/predictions.json", { ...predictions, source: "seed" });
