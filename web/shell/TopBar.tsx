import { format } from "date-fns";
import { ChevronLeft, ChevronRight, Menu } from "lucide-react";

interface TopBarProps {
  weekStart: Date;
  weekEnd: Date;
  onToggleDrawer: () => void;
  onToday: () => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
}

function rangeLabel(weekStart: Date, weekEnd: Date): string {
  const sameMonth = weekStart.getMonth() === weekEnd.getMonth();
  if (sameMonth) {
    return format(weekStart, "MMM yyyy");
  }
  const sameYear = weekStart.getFullYear() === weekEnd.getFullYear();
  if (sameYear) {
    return `${format(weekStart, "MMM")} – ${format(weekEnd, "MMM yyyy")}`;
  }
  return `${format(weekStart, "MMM yyyy")} – ${format(weekEnd, "MMM yyyy")}`;
}

export function TopBar({
  weekStart,
  weekEnd,
  onToggleDrawer,
  onToday,
  onPrevWeek,
  onNextWeek,
}: TopBarProps) {
  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-[var(--line)] px-2 sm:px-3">
      <button
        type="button"
        onClick={onToggleDrawer}
        aria-label="Main menu"
        className="inline-flex h-12 w-12 items-center justify-center rounded-full text-[var(--ink)] hover:bg-black/5"
      >
        <Menu size={24} strokeWidth={1.75} aria-hidden="true" />
      </button>

      <span className="mr-2 hidden font-[family-name:var(--font-display)] text-xl tracking-tight text-[var(--ink)] sm:mr-6 sm:inline">
        Moments
      </span>

      <button
        type="button"
        onClick={onToday}
        className="h-9 rounded-full border border-[var(--line)] px-4 text-sm font-medium text-[var(--ink)] hover:bg-black/5"
      >
        Today
      </button>

      <div className="flex items-center">
        <button
          type="button"
          onClick={onPrevWeek}
          aria-label="Previous week"
          className="inline-flex h-9 w-9 items-center justify-center rounded-full text-[var(--muted)] hover:bg-black/5"
        >
          <ChevronLeft size={20} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={onNextWeek}
          aria-label="Next week"
          className="inline-flex h-9 w-9 items-center justify-center rounded-full text-[var(--muted)] hover:bg-black/5"
        >
          <ChevronRight size={20} aria-hidden="true" />
        </button>
      </div>

      <h1 className="ml-1 font-[family-name:var(--font-display)] text-xl font-normal tracking-tight text-[var(--ink)] sm:ml-2">
        {rangeLabel(weekStart, weekEnd)}
      </h1>

      <div className="ml-auto">
        <span className="inline-flex h-9 items-center rounded-md border border-[var(--line)] px-3 text-sm font-medium text-[var(--ink)]">
          Week
        </span>
      </div>
    </header>
  );
}
