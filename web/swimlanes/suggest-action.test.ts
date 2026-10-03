import { describe, expect, it } from "vitest";
import { suggestAction, zoneCue } from "./suggest-action";

describe("zoneCue", () => {
  it("maps coffee to the chiller bay", () => {
    expect(zoneCue("coffee")).toBe("chiller / hot drinks bay");
  });

  it("maps crisps to the snack aisle", () => {
    expect(zoneCue("Crisps & Savoury Snacks")).toBe("snack aisle at eye level");
  });
});

describe("suggestAction", () => {
  it("uses add-facings verb for high share without repeating order qty or persona", () => {
    const lines = suggestAction({
      category: "coffee",
      times_usual_share: 1.42,
    });
    expect(lines.shelf).toBe("Add facings before this hour");
    expect(lines.zone).toBe("chiller / hot drinks bay");
    expect(lines.online).toContain("Feature coffee");
    expect(lines.shelf).not.toMatch(/\d/);
    expect(lines.online).not.toContain("Mission");
    expect(lines.season).toBeNull();
  });

  it("uses light-face verb for weak share", () => {
    const lines = suggestAction({
      category: "tea",
      times_usual_share: 0.9,
    });
    expect(lines.shelf).toBe("Light face only");
    expect(lines.online).toContain("Do not lead");
  });

  it("adds a season line when a holiday week is present", () => {
    const lines = suggestAction(
      { category: "confectionery", times_usual_share: 1.2 },
      [{ week: 51, date: "2026-12-21", calendar: "Christmas run-up" }],
    );
    expect(lines.season).toMatch(/Christmas \/ holiday/);
    expect(lines.shelf).toBe("Hold current facings");
  });
});
