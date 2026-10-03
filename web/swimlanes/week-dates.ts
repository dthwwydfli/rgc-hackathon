const DAY_MS = 24 * 60 * 60 * 1000;

/** Monday 00:00 local for the calendar containing `date`. */
export function startOfWeek(date: Date): Date {
  const next = new Date(date);
  const weekday = (next.getDay() + 6) % 7;
  next.setHours(0, 0, 0, 0);
  next.setDate(next.getDate() - weekday);
  return next;
}

/** Monday of the week at `weekOffset` from the current week (0 = this week). */
export function viewedWeekStart(weekOffset: number, now = new Date()): Date {
  const start = startOfWeek(now);
  start.setDate(start.getDate() + weekOffset * 7);
  return start;
}

/** Date for weekday 0=Mon … 6=Sun in the viewed week. */
export function dateForWeekday(
  weekOffset: number,
  weekday: number,
  now = new Date(),
): Date {
  const start = viewedWeekStart(weekOffset, now);
  const next = new Date(start);
  next.setDate(next.getDate() + weekday);
  return next;
}

export function isoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function todayWeekdayIndex(now = new Date()): number {
  return (now.getDay() + 6) % 7;
}

/** Days between two Monday starts; used in tests. */
export function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}
