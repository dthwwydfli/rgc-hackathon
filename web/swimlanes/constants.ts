import type { SwimlaneMoment, StoreMeta } from "./types";

export const STORE_ID = "1010023674";
export const FILL_MS = 100;
export const UNITS_FLOOR = 5;

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export const WEEKDAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

export const TONES = [
  "#b8f000",
  "#53cdc5",
  "#6a6ae2",
  "#9c6dba",
  "#22a651",
  "#b8f000",
] as const;

export const ALLOWED = new Set([
  "coffee",
  "tea",
  "confectionery",
  "crisps & savoury snacks",
  "breakfast foods",
  "sports & energy drinks",
]);

export const FALLBACK_MOMENTS: SwimlaneMoment[] = [
  { id: "early_rush", name: "early / rush", hour: 8, time: "05:00-10:00" },
  { id: "mid_morning", name: "mid-morning", hour: 10, time: "10:00-12:00" },
  { id: "quick_lunch", name: "quick lunch", hour: 12, time: "12:00-14:00" },
  { id: "afternoon_focus", name: "afternoon focus", hour: 15, time: "14:00-17:00" },
  {
    id: "evening",
    name: "weekday evening",
    weekendName: "social evening",
    hour: 17,
    time: "17:00-21:00",
  },
  { id: "late_night", name: "late night", hour: 21, time: "21:00-24:00" },
];

export const DEFAULT_STORE: StoreMeta = {
  id: STORE_ID,
  store_name: "Tesco Express Camden High Street",
  postcode: "NW1 7JN",
};

/** Caveats that only restate the dropped US/London source line. */
export const SOURCE_CAVEAT_PATTERN =
  /US households in 2017|London Tesco levels \(2015\)/i;

export const BOARD_FIXTURE_URL = "./mock/swimlanes-board.json";
export const RECOMMEND_FIXTURE_URL = "./mock/recommend-panel.json";
