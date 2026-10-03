/** Types for the Moments week swimlanes board and recommend panel. */

export interface SwimlaneMoment {
  id: string;
  name: string;
  hour: number;
  time: string;
  weekendName?: string;
}

export interface CategoryRow {
  category: string;
  group: string;
  units: number;
}

export interface BoardCell {
  s: number;
  categories: CategoryRow[];
}

export type Board = BoardCell[][];

export interface StoreMeta {
  id: string;
  store_name: string;
  postcode: string;
  fascia?: string;
  format?: string;
  borough?: string;
  retailer?: string;
}

export interface ExampleProduct {
  name: string;
  brand: string;
}

export interface StockRow {
  category: string;
  group: string;
  units_per_week: number;
  range?: [number, number];
  stock?: number | null;
  times_usual_share?: number | null;
  bought_most_by?: string | null;
  that_persona_share?: number | null;
  lowest_week?: number | null;
  highest_week?: number | null;
  example_products?: ExampleProduct[];
}

export interface WeekThatDiffers {
  week: number;
  date: string;
  calendar?: string;
  vs_typical_week?: number | null;
}

export interface RecommendSlot {
  weekday: string;
  hour: string;
  moment: string;
}

export interface RecommendPayload {
  store?: StoreMeta;
  weeks?: number;
  from?: string;
  note_on_weeks?: string;
  basis?: {
    horizon?: string;
    what?: string;
    when_and_who?: string;
    volume?: string;
  };
  caveats?: string[];
  slot?: RecommendSlot;
  stock_most?: StockRow[];
  sells_unusually_well_in_this_slot?: StockRow[];
  shoppers_in_this_slot?: Record<string, number>;
  weeks_that_differ?: WeekThatDiffers[];
}

export interface BoardFixture {
  store?: StoreMeta;
  moments?: SwimlaneMoment[];
  days?: Array<{
    weekday: number;
    cells?: Record<string, Array<{ category?: string; group?: string; units?: number }>>;
  }>;
}

export interface RecommendFixture {
  store?: StoreMeta;
  weeks?: number;
  from?: string;
  note_on_weeks?: string;
  basis?: RecommendPayload["basis"];
  caveats?: string[];
  neighbourhood?: unknown[];
  slots?: Record<string, RecommendPayload>;
}

export interface SimulateCell {
  moment?: string;
  category?: string;
  group?: string;
  units?: number;
}

export interface SimulatePayload {
  cells?: SimulateCell[];
  location?: StoreMeta & { id?: string };
}

export interface ActionLines {
  shelf: string;
  zone: string;
  online: string;
  season: string | null;
}

export interface FixturesBundle {
  board: BoardFixture;
  recommend: RecommendFixture;
  moments: SwimlaneMoment[];
  store: StoreMeta;
}
