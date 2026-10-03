import { useEffect, useMemo, useRef, useState } from "react";
import {
  addDays,
  format,
  isSameDay,
  startOfWeek,
} from "date-fns";
import type { BestSlot, Moment, Product } from "../data/types";
import { cn } from "../lib/cn";

export const GRID_START_MINUTE = 7 * 60;
export const GRID_END_MINUTE = 23 * 60;
export const HOUR_HEIGHT_PX = 48;

const MOMENT_PALETTE = [
  {
    bg: "rgba(184, 240, 0, 0.28)",
    border: "var(--action-green)",
  },
  {
    bg: "rgba(83, 205, 197, 0.22)",
    border: "var(--evidence-teal)",
  },
  {
    bg: "rgba(106, 106, 226, 0.16)",
    border: "var(--model-indigo)",
  },
  {
    bg: "rgba(156, 109, 186, 0.18)",
    border: "var(--risk-purple)",
  },
] as const;

export interface CalendarEvent {
  product: Product;
  slot: BestSlot;
  moment: Moment;
}

export interface MomentBlock {
  moment: Moment;
  products: CalendarEvent[];
}

interface WeekCalendarProps {
  weekStart: Date;
  momentBlocks: MomentBlock[];
  statusMessage: string | null;
  isError?: boolean;
  onOpenEvent: (args: {
    productId: string;
    momentId: string;
    personaId: string;
    focusReturnId: string;
  }) => void;
}

function minuteToTop(minute: number): number {
  return ((minute - GRID_START_MINUTE) / 60) * HOUR_HEIGHT_PX;
}

function durationHeight(startMinute: number, endMinute: number): number {
  return Math.max(((endMinute - startMinute) / 60) * HOUR_HEIGHT_PX, 28);
}

function formatHourLabel(minute: number): string {
  const hour = minute / 60;
  const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
  const suffix = hour >= 12 ? "PM" : "AM";
  return `${displayHour} ${suffix}`;
}

function nowLineTop(): number | null {
  const now = new Date();
  const minute = now.getHours() * 60 + now.getMinutes();
  if (minute < GRID_START_MINUTE || minute > GRID_END_MINUTE) {
    return null;
  }
  return minuteToTop(minute);
}

/**
 * Groups product best-slots into one block per shopper moment.
 */
export function groupProductsByMoment(events: CalendarEvent[]): MomentBlock[] {
  const byMoment = new Map<string, MomentBlock>();

  for (const event of events) {
    const existing = byMoment.get(event.moment.id);
    if (existing) {
      existing.products.push(event);
      continue;
    }
    byMoment.set(event.moment.id, {
      moment: event.moment,
      products: [event],
    });
  }

  return [...byMoment.values()].sort(
    (a, b) => a.moment.start_minute - b.moment.start_minute,
  );
}

export function WeekCalendar({
  weekStart,
  momentBlocks,
  statusMessage,
  isError = false,
  onOpenEvent,
}: WeekCalendarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const nowLineRef = useRef<HTMLDivElement>(null);
  const [openBlockKey, setOpenBlockKey] = useState<string | null>(null);

  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));
  }, [weekStart]);

  const hours = useMemo(() => {
    const labels: number[] = [];
    for (let minute = GRID_START_MINUTE; minute < GRID_END_MINUTE; minute += 60) {
      labels.push(minute);
    }
    return labels;
  }, []);

  const gridHeight = ((GRID_END_MINUTE - GRID_START_MINUTE) / 60) * HOUR_HEIGHT_PX;
  const lineTop = nowLineTop();
  const today = new Date();

  useEffect(() => {
    if (nowLineRef.current) {
      nowLineRef.current.scrollIntoView({ block: "center" });
    }
  }, [weekStart]);

  useEffect(() => {
    if (!openBlockKey) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (target.closest("[data-moment-menu]")) {
        return;
      }
      setOpenBlockKey(null);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [openBlockKey]);

  if (statusMessage) {
    return (
      <p className={cn("p-6 text-sm", isError ? "text-red-600" : "text-[var(--muted)]")}>
        {statusMessage}
      </p>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="grid shrink-0 grid-cols-[56px_1fr] border-b border-[var(--line)]">
        <div className="border-r border-[var(--line)]" aria-hidden="true" />
        <div className="grid grid-cols-7">
          {days.map((day) => {
            const isToday = isSameDay(day, today);
            return (
              <div
                key={day.toISOString()}
                className="flex flex-col items-center gap-1 border-r border-[var(--line)] py-2 last:border-r-0"
              >
                <span className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                  {format(day, "EEE")}
                </span>
                <span
                  className={cn(
                    "inline-flex h-10 w-10 items-center justify-center rounded-full font-[family-name:var(--font-display)] text-2xl",
                    isToday
                      ? "bg-[var(--action-green)] font-medium text-white"
                      : "text-[var(--ink)]",
                  )}
                >
                  {format(day, "d")}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto">
        <div className="grid grid-cols-[56px_1fr]" style={{ height: gridHeight }}>
          <div className="relative border-r border-[var(--line)]" aria-hidden="true">
            {hours.map((minute) => (
              <div
                key={minute}
                className="relative"
                style={{ height: HOUR_HEIGHT_PX }}
              >
                <span className="absolute -top-2 right-2 font-[family-name:var(--font-data)] text-[10px] text-[var(--muted)]">
                  {formatHourLabel(minute)}
                </span>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7" role="grid" aria-label="Week">
            {days.map((day, dayIndex) => {
              const isToday = isSameDay(day, today);
              return (
                <div
                  key={day.toISOString()}
                  className="relative border-r border-[var(--line)] last:border-r-0"
                  style={{ height: gridHeight }}
                  role="gridcell"
                >
                  {hours.map((minute) => (
                    <div
                      key={minute}
                      className="absolute right-0 left-0 border-t border-[var(--line)]"
                      style={{ top: minuteToTop(minute) }}
                    />
                  ))}

                  {isToday && lineTop !== null ? (
                    <div
                      ref={dayIndex === 0 ? nowLineRef : undefined}
                      className="pointer-events-none absolute right-0 left-0 z-20"
                      style={{ top: lineTop }}
                    >
                      <div className="relative">
                        <span className="absolute -left-1.5 top-1/2 h-3 w-3 -translate-y-1/2 rounded-full bg-[var(--now)]" />
                        <div className="h-0.5 bg-[var(--now)]" />
                      </div>
                    </div>
                  ) : null}

                  {momentBlocks.map((block, blockIndex) => {
                    const { moment, products } = block;
                    const blockKey = `${moment.id}-d${dayIndex}`;
                    const isOpen = openBlockKey === blockKey;
                    const palette = MOMENT_PALETTE[blockIndex % MOMENT_PALETTE.length];
                    const productLabel =
                      products.length === 1
                        ? "1 product"
                        : `${products.length} products`;

                    return (
                      <div
                        key={blockKey}
                        className="absolute z-10"
                        style={{
                          top: minuteToTop(moment.start_minute),
                          height: durationHeight(moment.start_minute, moment.end_minute),
                          left: 4,
                          right: 4,
                        }}
                        data-moment-menu
                      >
                        <button
                          type="button"
                          id={blockKey}
                          aria-expanded={isOpen}
                          aria-label={`${moment.name}, ${moment.time_window}, ${productLabel}`}
                          onClick={() => {
                            setOpenBlockKey(isOpen ? null : blockKey);
                          }}
                          className="h-full w-full overflow-hidden rounded-sm border-0 border-l-[3px] border-solid px-2 py-1 text-left text-[var(--ink)] hover:brightness-95 focus-visible:z-30"
                          style={{
                            backgroundColor: palette.bg,
                            borderLeftColor: palette.border,
                          }}
                        >
                          <span className="block truncate text-xs font-medium">
                            {moment.name}
                          </span>
                          <span className="block truncate text-[10px] text-[var(--muted)]">
                            {moment.time_window} · {productLabel}
                          </span>
                        </button>

                        {isOpen ? (
                          <ul className="absolute top-full left-0 z-40 mt-1 max-h-56 min-w-[12rem] overflow-auto rounded border border-[var(--line)] bg-white py-1 shadow-lg">
                            {products.map((item) => {
                              const focusReturnId = `moment-product-${item.product.id}-d${dayIndex}`;
                              return (
                                <li key={item.product.id}>
                                  <button
                                    type="button"
                                    id={focusReturnId}
                                    className="block w-full truncate px-3 py-1.5 text-left text-xs text-[var(--ink)] hover:bg-black/5"
                                    onClick={() => {
                                      setOpenBlockKey(null);
                                      onOpenEvent({
                                        productId: item.product.id,
                                        momentId: item.slot.momentId,
                                        personaId: item.slot.personaId,
                                        focusReturnId,
                                      });
                                    }}
                                  >
                                    {item.product.name}
                                  </button>
                                </li>
                              );
                            })}
                          </ul>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export function weekStartingMonday(anchor: Date): Date {
  return startOfWeek(anchor, { weekStartsOn: 1 });
}
