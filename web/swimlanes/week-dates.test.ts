import { describe, expect, it } from "vitest";
import {
  dateForWeekday,
  daysBetween,
  startOfWeek,
  viewedWeekStart,
} from "./week-dates";

describe("week-dates", () => {
  it("starts the week on Monday", () => {
    // Wednesday 7 Oct 2026
    const wednesday = new Date(2026, 9, 7, 15, 0, 0);
    const monday = startOfWeek(wednesday);
    expect(monday.getDay()).toBe(1);
    expect(monday.getDate()).toBe(5);
  });

  it("moves Monday by 7 days when weekOffset is 1", () => {
    const now = new Date(2026, 9, 7, 12, 0, 0);
    const thisMonday = viewedWeekStart(0, now);
    const nextMonday = viewedWeekStart(1, now);
    expect(daysBetween(thisMonday, nextMonday)).toBe(7);
    expect(dateForWeekday(1, 0, now).getTime()).toBe(nextMonday.getTime());
  });
});
