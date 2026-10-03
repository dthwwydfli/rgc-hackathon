import { useEffect, useRef } from "react";
import { DAYS, TONES, UNITS_FLOOR } from "./constants";
import { cellFillPercent, maxUnits } from "./load-board";
import type { Board, BoardCell, SwimlaneMoment } from "./types";
import { dateForWeekday, todayWeekdayIndex } from "./week-dates";

interface SwimlanesBoardProps {
  moments: SwimlaneMoment[];
  weekOffset: number;
  board: Board | null;
  revealed: Set<string>;
  onOpenCell: (laneIndex: number, dayIndex: number, cell: BoardCell) => void;
}

function cellKey(laneIndex: number, dayIndex: number): string {
  return `${laneIndex}-${dayIndex}`;
}

function CellButton({
  cell,
  tone,
  peak,
  isRevealed,
  onOpen,
}: {
  cell: BoardCell | null;
  tone: string;
  peak: number;
  isRevealed: boolean;
  onOpen: () => void;
}) {
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isRevealed || !cell || !cell.categories.length) {
      return;
    }
    const button = buttonRef.current;
    if (!button) {
      return;
    }
    let frameOuter = 0;
    let frameInner = 0;
    frameOuter = requestAnimationFrame(() => {
      frameInner = requestAnimationFrame(() => {
        button.classList.add("is-visible");
      });
    });
    return () => {
      cancelAnimationFrame(frameOuter);
      cancelAnimationFrame(frameInner);
    };
  }, [isRevealed, cell]);

  if (!isRevealed || !cell || !cell.categories.length || cell.s < UNITS_FLOOR) {
    return (
      <button type="button" className="is-empty" disabled>
        ·
      </button>
    );
  }

  const fill = cellFillPercent(cell.s, peak);
  const top = cell.categories[0].category;

  return (
    <button
      ref={buttonRef}
      type="button"
      title={top}
      style={{ ["--fill" as string]: `${fill}%`, ["--tone" as string]: tone }}
      onClick={onOpen}
    >
      <span className="swimlanes-sku">{top}</span>
    </button>
  );
}

export function SwimlanesBoard({
  moments,
  weekOffset,
  board,
  revealed,
  onOpenCell,
}: SwimlanesBoardProps) {
  const weekStart = dateForWeekday(weekOffset, 0);
  const todayIdx = todayWeekdayIndex();
  const peak = board ? maxUnits(board) : 1;
  const rowCount = Math.max(moments.length, 1);

  return (
    <div className="swimlanes-board">
      <div
        className="swimlanes-grid"
        style={{
          gridTemplateRows: `3rem repeat(${rowCount}, minmax(0, 1fr))`,
        }}
      >
        <div className="swimlanes-corner">Moment \ Day</div>
        {DAYS.map((name, dayIndex) => {
          const date = new Date(weekStart);
          date.setDate(date.getDate() + dayIndex);
          const isToday = weekOffset === 0 && dayIndex === todayIdx;
          return (
            <div
              key={name}
              className={"swimlanes-day-head" + (isToday ? " is-today" : "")}
            >
              <span>{name}</span>
              <strong>{date.getDate()}</strong>
            </div>
          );
        })}

        {moments.map((moment, laneIndex) => {
          const tone = TONES[laneIndex % TONES.length];
          return (
            <div key={moment.id} style={{ display: "contents" }}>
              <div
                className="swimlanes-lane-label"
                style={{ ["--tone" as string]: tone }}
              >
                <strong>{moment.name}</strong>
                <em>{moment.time}</em>
              </div>
              {DAYS.map((_, dayIndex) => {
                const cell = board?.[laneIndex]?.[dayIndex] ?? null;
                const key = cellKey(laneIndex, dayIndex);
                return (
                  <div
                    key={key}
                    className="swimlanes-cell"
                    style={{ ["--tone" as string]: tone }}
                  >
                    <CellButton
                      cell={cell}
                      tone={tone}
                      peak={peak}
                      isRevealed={revealed.has(key)}
                      onOpen={() => {
                        if (cell) {
                          onOpenCell(laneIndex, dayIndex, cell);
                        }
                      }}
                    />
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
