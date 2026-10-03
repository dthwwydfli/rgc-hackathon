import { describe, expect, it } from "vitest";
import { groupProductsByMoment, type CalendarEvent } from "./WeekCalendar";
import type { BestSlot, Moment, Product } from "../data/types";

function fakeProduct(id: string, name: string): Product {
  return {
    id,
    name,
    brand: "Test",
    price_pence: 100,
    zone: "till",
  };
}

function fakeMoment(id: string, name: string, start: number, end: number): Moment {
  return {
    id,
    name,
    time_window: `${start}–${end}`,
    start_minute: start,
    end_minute: end,
    dwell_seconds: 60,
    dwell_label: "1m",
    zones_reached: [],
    mission: "",
    tested_live: false,
  };
}

function fakeSlot(productId: string, momentId: string): BestSlot {
  return {
    momentId,
    personaId: "gym_regular",
    productId,
    rankKind: "solid_win",
    rankLabel: "Solid win",
    nReal: 6,
    predictedShare: 0.4,
  };
}

function event(
  productId: string,
  productName: string,
  moment: Moment,
): CalendarEvent {
  return {
    product: fakeProduct(productId, productName),
    moment,
    slot: fakeSlot(productId, moment.id),
  };
}

describe("groupProductsByMoment", () => {
  it("groups two products in the same moment into one block", () => {
    const morning = fakeMoment("morning_rush", "Morning rush", 450, 540);
    const lunch = fakeMoment("quick_lunch", "Quick lunch", 720, 840);

    const blocks = groupProductsByMoment([
      event("banana", "Bananas", morning),
      event("croissant", "Croissants", morning),
      event("hummus", "Hummus", lunch),
    ]);

    expect(blocks).toHaveLength(2);
    expect(blocks[0].moment.id).toBe("morning_rush");
    expect(blocks[0].products.map((item) => item.product.name)).toEqual([
      "Bananas",
      "Croissants",
    ]);
    expect(blocks[1].moment.id).toBe("quick_lunch");
    expect(blocks[1].products).toHaveLength(1);
  });

  it("sorts blocks by start time", () => {
    const late = fakeMoment("late_night", "Late night", 1260, 1380);
    const morning = fakeMoment("morning_rush", "Morning rush", 450, 540);

    const blocks = groupProductsByMoment([
      event("choc", "Chocolate", late),
      event("banana", "Bananas", morning),
    ]);

    expect(blocks.map((block) => block.moment.id)).toEqual([
      "morning_rush",
      "late_night",
    ]);
  });
});
