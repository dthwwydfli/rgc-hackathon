import type { ActionLines, StockRow, WeekThatDiffers } from "./types";

export function zoneCue(category: string): string {
  const name = category.toLowerCase();
  if (name.includes("coffee") || name.includes("tea") || name.includes("breakfast")) {
    return "chiller / hot drinks bay";
  }
  if (name.includes("energy") || name.includes("sports")) {
    return "chiller near till";
  }
  if (name.includes("crisp") || name.includes("snack") || name.includes("confection")) {
    return "snack aisle at eye level";
  }
  return "main aisle facing";
}

function hasHolidayWeek(weeksThatDiffer: WeekThatDiffers[]): boolean {
  return weeksThatDiffer.some((week) =>
    /christmas|holiday|run-up/i.test(String(week.calendar || "")),
  );
}

function shelfVerb(share: number): string {
  if (Number.isFinite(share) && share >= 1.35) {
    return "Add facings before this hour";
  }
  if (Number.isFinite(share) && share >= 1.05) {
    return "Hold current facings";
  }
  if (Number.isFinite(share) && share > 0) {
    return "Light face only";
  }
  return "Review fill";
}

/**
 * Playbook lines for a stock card. Stats already show order qty, share, and
 * persona, so those values are not repeated here.
 */
export function suggestAction(
  row: Pick<StockRow, "category" | "times_usual_share">,
  weeksThatDiffer: WeekThatDiffers[] = [],
): ActionLines {
  const category = row.category || "this category";
  const share = Number(row.times_usual_share);
  const online =
    Number.isFinite(share) && share < 1.05
      ? `Do not lead the daypart tile with ${category}`
      : `Feature ${category} on this daypart tile`;

  return {
    shelf: shelfVerb(share),
    zone: zoneCue(category),
    online,
    season: hasHolidayWeek(weeksThatDiffer)
      ? "Christmas / holiday weeks lift confectionery - lean in"
      : null,
  };
}
