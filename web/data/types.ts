/** Shared domain types for Moment Fit FE. */

export type Verdict = "win" | "lose" | "neutral";

export type Effort = "S" | "M" | "L";

export type ActionOwner = "brand" | "retailer";

export type EvidenceTone = "solid" | "low" | "dashed";

export interface Product {
  id: string;
  name: string;
  brand: string;
  price_pence: number;
  zone: string;
  image_path?: string;
  image?: string;
  fop_claim?: string;
}

export interface Persona {
  id: string;
  name: string;
  excluded_from_scoring: boolean;
}

export interface Moment {
  id: string;
  name: string;
  time_window: string;
  start_minute: number;
  end_minute: number;
  dwell_seconds: number;
  dwell_label: string;
  zones_reached: string[];
  mission: string;
  tested_live: boolean;
}

export interface ProductAction {
  next_step: string;
  cost_pence: number | null;
  owner: ActionOwner;
  expensive_action_avoided: string;
  effort: Effort;
}

export interface ResultCell {
  n_real: number;
  evidence: string;
  predicted_shares: Record<string, number>;
  real_shares: Record<string, number>;
  verdict_by_product: Record<string, Verdict>;
  driver_by_product: Record<string, string>;
  explanation_by_product: Record<string, string>;
  nearly_chose: Array<{ product_id: string; reason: string; count: number }>;
  quotes: Array<{ response_id: string; text: string }>;
  actions_by_product: Record<string, ProductAction>;
}

export interface ResultsPayload {
  updated_at?: string;
  source?: string;
  note?: string;
  n_scored: number;
  n_other: number;
  accuracy: {
    overall: { pct: number; n: number };
    by_moment: Record<string, { pct: number; n: number }>;
    by_persona: Record<string, { pct: number; n: number }>;
  };
  baselines: {
    random: { pct: number; n: number };
    cheapest_wins: { pct: number; n: number };
  };
  cells: Record<string, ResultCell>;
  gaps?: unknown;
  calibration: {
    status: string;
    message?: string;
    locked_heldout_pct?: number | null;
    calibrated_heldout_pct?: number | null;
    n?: number;
  };
}

export interface PredictionsPayload {
  locked_at?: string;
  git_commit?: string;
  source?: string;
  cells: Record<string, {
    persona_id: string;
    moment_id: string;
    predicted_shares: Record<string, number>;
    top_pick: string;
    driver: string;
    explanation: string;
  }>;
}

export type RankKind = "solid_win" | "directional_win" | "predicted_win" | "best_share";

export interface BestSlot {
  momentId: string;
  personaId: string;
  productId: string;
  rankKind: RankKind;
  rankLabel: string;
  nReal: number;
  predictedShare: number;
}

export interface AppPaths {
  products: string;
  personas: string;
  moments: string;
  predictions: string;
  results: string;
  mockProducts: string;
  mockPersonas: string;
  mockMoments: string;
  mockPredictions: string;
  mockResults: string;
}
