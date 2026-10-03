import {
  ALLOWED,
  BOARD_FIXTURE_URL,
  DEFAULT_STORE,
  FALLBACK_MOMENTS,
  RECOMMEND_FIXTURE_URL,
  STORE_ID,
  UNITS_FLOOR,
  WEEKDAY_NAMES,
} from "./constants";
import { dateForWeekday, isoDate } from "./week-dates";
import type {
  Board,
  BoardCell,
  BoardFixture,
  CategoryRow,
  FixturesBundle,
  RecommendFixture,
  RecommendPayload,
  SimulatePayload,
  StockRow,
  StoreMeta,
  SwimlaneMoment,
} from "./types";

async function tryFetchJson(url: string): Promise<unknown | null> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (error) {
    console.warn("fetch failed", { url, cause: error });
    return null;
  }
}

function normalizeMoment(raw: SwimlaneMoment): SwimlaneMoment {
  return {
    ...raw,
    time: String(raw.time || "").replace(/[–—]/g, "-"),
  };
}

export function emptyLaneDays(moments: SwimlaneMoment[]): Board {
  return moments.map(() =>
    WEEKDAY_NAMES.map(() => ({ s: 0, categories: [] as CategoryRow[] })),
  );
}

export function filterCategories(
  rows: Array<{ category?: string; group?: string; units?: number; units_per_week?: number }>,
): CategoryRow[] {
  return rows
    .filter((row) => ALLOWED.has(String(row.category || "").toLowerCase()))
    .map((row) => ({
      category: String(row.category),
      group: row.group || "",
      units: Number(row.units ?? row.units_per_week ?? 0),
    }))
    .filter((row) => row.units >= UNITS_FLOOR)
    .sort((a, b) => b.units - a.units);
}

export function momentIdFromName(name: string): string {
  const n = String(name || "").toLowerCase();
  if (n.includes("early") || n.includes("rush")) {
    return "early_rush";
  }
  if (n.includes("mid-morning") || n.includes("mid morning")) {
    return "mid_morning";
  }
  if (n.includes("lunch")) {
    return "quick_lunch";
  }
  if (n.includes("afternoon")) {
    return "afternoon_focus";
  }
  if (n.includes("evening") || n.includes("social")) {
    return "evening";
  }
  if (n.includes("late")) {
    return "late_night";
  }
  return "";
}

export function momentLabel(moment: SwimlaneMoment, weekday: number): string {
  if (moment.id === "evening" && weekday >= 5 && moment.weekendName) {
    return moment.weekendName;
  }
  return moment.name;
}

export function boardFromFixture(
  fixture: BoardFixture,
  moments: SwimlaneMoment[],
): Board {
  const board = emptyLaneDays(moments);
  for (const day of fixture.days || []) {
    const dayIndex = day.weekday;
    if (dayIndex < 0 || dayIndex > 6) {
      continue;
    }
    moments.forEach((moment, laneIndex) => {
      const cats = filterCategories(day.cells?.[moment.id] || []);
      board[laneIndex][dayIndex] = {
        s: cats[0] ? cats[0].units : 0,
        categories: cats,
      };
    });
  }
  return board;
}

export function boardFromSimulates(
  sims: Array<SimulatePayload | null>,
  moments: SwimlaneMoment[],
  store: StoreMeta,
): { board: Board; store: StoreMeta } {
  const board = emptyLaneDays(moments);
  let nextStore = store;

  sims.forEach((sim, dayIndex) => {
    if (!sim) {
      return;
    }
    const byMoment: Record<string, CategoryRow[]> = {};
    for (const cell of sim.cells || []) {
      const mid = momentIdFromName(String(cell.moment || ""));
      if (!mid || !ALLOWED.has(String(cell.category || "").toLowerCase())) {
        continue;
      }
      if (!byMoment[mid]) {
        byMoment[mid] = [];
      }
      byMoment[mid].push({
        category: String(cell.category),
        group: cell.group || "",
        units: Number(cell.units || 0),
      });
    }
    moments.forEach((moment, laneIndex) => {
      const cats = filterCategories(byMoment[moment.id] || []);
      board[laneIndex][dayIndex] = {
        s: cats[0] ? cats[0].units : 0,
        categories: cats,
      };
    });
    if (sim.location) {
      nextStore = {
        id: sim.location.id || STORE_ID,
        store_name: sim.location.store_name || nextStore.store_name,
        postcode: sim.location.postcode || nextStore.postcode,
        fascia: sim.location.fascia,
        format: sim.location.format,
        borough: sim.location.borough,
      };
    }
  });

  return { board, store: nextStore };
}

export async function loadFixtures(): Promise<FixturesBundle> {
  const [boardRaw, recommendRaw] = await Promise.all([
    tryFetchJson(BOARD_FIXTURE_URL),
    tryFetchJson(RECOMMEND_FIXTURE_URL),
  ]);
  if (!boardRaw || !recommendRaw) {
    throw new Error("fixture fetch failed");
  }
  const board = boardRaw as BoardFixture;
  const recommend = recommendRaw as RecommendFixture;
  const moments = (board.moments || FALLBACK_MOMENTS).map(normalizeMoment);
  const store = board.store
    ? { ...DEFAULT_STORE, ...board.store }
    : { ...DEFAULT_STORE };
  return { board, recommend, moments, store };
}

export async function buildBoardFromApi(
  weekOffset: number,
  moments: SwimlaneMoment[],
  store: StoreMeta,
): Promise<{ board: Board; store: StoreMeta } | null> {
  const sims = await Promise.all(
    WEEKDAY_NAMES.map((_, weekday) => {
      const date = isoDate(dateForWeekday(weekOffset, weekday));
      return tryFetchJson(
        `/api/simulate?station=${encodeURIComponent(STORE_ID)}&date=${date}`,
      ) as Promise<SimulatePayload | null>;
    }),
  );
  if (sims.every((sim) => !sim)) {
    return null;
  }
  return boardFromSimulates(sims, moments, store);
}

function fixtureTemplateKey(
  recommend: RecommendFixture,
  weekday: number,
  hour: number,
): string {
  const exact = `${weekday}-${hour}`;
  const slots = recommend.slots || {};
  if (slots[exact]) {
    return exact;
  }
  if (hour >= 17) {
    return "4-17";
  }
  return "0-8";
}

export function fixtureRecommend(
  recommend: RecommendFixture,
  weekday: number,
  hour: number,
  momentName: string,
): RecommendPayload | null {
  const slots = recommend.slots || {};
  const templateKey = fixtureTemplateKey(recommend, weekday, hour);
  const base = slots[templateKey] || Object.values(slots)[0];
  if (!base) {
    return null;
  }
  return {
    store: recommend.store,
    weeks: recommend.weeks,
    from: recommend.from,
    note_on_weeks: recommend.note_on_weeks,
    basis: recommend.basis,
    caveats: recommend.caveats,
    slot: {
      weekday: WEEKDAY_NAMES[weekday] || base.slot?.weekday || "",
      hour:
        `${String(hour).padStart(2, "0")}:00-`
        + `${String(hour + 1).padStart(2, "0")}:00`,
      moment: momentName || base.slot?.moment || "",
    },
    stock_most: base.stock_most,
    sells_unusually_well_in_this_slot: base.sells_unusually_well_in_this_slot,
    shoppers_in_this_slot: base.shoppers_in_this_slot,
    weeks_that_differ: base.weeks_that_differ,
  };
}

export function scopeRecommendToCell(
  payload: RecommendPayload,
  cell: BoardCell,
): RecommendPayload {
  const cellCats = cell.categories || [];
  const byName = new Map<string, StockRow>();
  for (const row of payload.stock_most || []) {
    byName.set(String(row.category).toLowerCase(), row);
  }
  for (const row of payload.sells_unusually_well_in_this_slot || []) {
    const key = String(row.category).toLowerCase();
    if (!byName.has(key)) {
      byName.set(key, row);
    }
  }

  const stock_most: StockRow[] = cellCats.map((cat) => {
    const hit = byName.get(String(cat.category).toLowerCase());
    const units = Number(cat.units || 0);
    if (hit) {
      return {
        ...hit,
        category: cat.category,
        group: cat.group || hit.group || "",
        units_per_week:
          hit.units_per_week != null ? hit.units_per_week : units,
      };
    }
    const low = Math.max(0, Math.floor(units * 0.7));
    const high = Math.ceil(units * 1.3);
    return {
      category: cat.category,
      group: cat.group || "",
      units_per_week: Math.round(units * 10) / 10,
      range: [low, high],
      stock: Math.max(1, Math.ceil(units * 1.15)),
      times_usual_share: null,
      bought_most_by: null,
      that_persona_share: null,
      lowest_week: low,
      highest_week: high,
      example_products: [],
    };
  });

  return { ...payload, stock_most };
}

export async function fetchRecommend(
  storeId: string,
  weekday: number,
  hour: number,
): Promise<RecommendPayload | null> {
  const raw = await tryFetchJson(
    `/api/recommend?store=${encodeURIComponent(storeId)}`
      + `&weekday=${weekday}&hour=${hour}&weeks=12`,
  );
  return raw as RecommendPayload | null;
}

export function maxUnits(board: Board): number {
  let max = 1;
  for (const days of board) {
    for (const cell of days) {
      if (cell.s > max) {
        max = cell.s;
      }
    }
  }
  return max;
}

export function placementsByStrength(board: Board): Array<{
  laneIndex: number;
  dayIndex: number;
  cell: BoardCell;
  s: number;
}> {
  const list: Array<{
    laneIndex: number;
    dayIndex: number;
    cell: BoardCell;
    s: number;
  }> = [];
  board.forEach((days, laneIndex) => {
    days.forEach((cell, dayIndex) => {
      if (!cell.categories.length || cell.s < UNITS_FLOOR) {
        return;
      }
      list.push({ laneIndex, dayIndex, cell, s: cell.s });
    });
  });
  list.sort((a, b) => b.s - a.s);
  return list;
}

export function cellFillPercent(units: number, peak: number): number {
  const strength = units / peak;
  return Math.round(18 + strength * 55);
}
