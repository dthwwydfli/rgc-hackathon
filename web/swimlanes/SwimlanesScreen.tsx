import { useCallback, useEffect, useRef, useState } from "react";
import { Menu } from "lucide-react";
import {
  DEFAULT_STORE,
  FALLBACK_MOMENTS,
  FILL_MS,
  STORE_ID,
} from "./constants";
import {
  boardFromFixture,
  buildBoardFromApi,
  emptyLaneDays,
  fetchRecommend,
  fixtureRecommend,
  loadFixtures,
  momentLabel,
  placementsByStrength,
  scopeRecommendToCell,
} from "./load-board";
import { SlotPanel } from "./SlotPanel";
import { SwimlanesBoard } from "./SwimlanesBoard";
import type {
  Board,
  BoardCell,
  BoardFixture,
  RecommendFixture,
  RecommendPayload,
  StoreMeta,
  SwimlaneMoment,
} from "./types";
import { WanderingEyes } from "./WanderingEyes";
import "./swimlanes.css";

interface SwimlanesScreenProps {
  onToggleDrawer: () => void;
}

function cellKey(laneIndex: number, dayIndex: number): string {
  return `${laneIndex}-${dayIndex}`;
}

export function SwimlanesScreen({ onToggleDrawer }: SwimlanesScreenProps) {
  const [moments, setMoments] = useState<SwimlaneMoment[]>(FALLBACK_MOMENTS);
  const [store, setStore] = useState<StoreMeta>(DEFAULT_STORE);
  const [boardFixture, setBoardFixture] = useState<BoardFixture | null>(null);
  const [recommendFixture, setRecommendFixture] =
    useState<RecommendFixture | null>(null);
  const [weekOffset, setWeekOffset] = useState(0);
  const [board, setBoard] = useState<Board | null>(null);
  const [revealed, setRevealed] = useState<Set<string>>(() => new Set());
  const [isRunning, setIsRunning] = useState(false);

  const [panelOpen, setPanelOpen] = useState(false);
  const [panelLoading, setPanelLoading] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [panelPayload, setPanelPayload] = useState<RecommendPayload | null>(
    null,
  );
  const [focusCategory, setFocusCategory] = useState<string | null>(null);

  const fillTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const runGeneration = useRef(0);

  const clearFillTimers = useCallback(() => {
    fillTimers.current.forEach((id) => clearTimeout(id));
    fillTimers.current = [];
  }, []);

  const clearBoardForWeek = useCallback(() => {
    clearFillTimers();
    runGeneration.current += 1;
    setIsRunning(false);
    setBoard(null);
    setRevealed(new Set());
  }, [clearFillTimers]);

  useEffect(() => {
    let cancelled = false;
    loadFixtures()
      .then((bundle) => {
        if (cancelled) {
          return;
        }
        setBoardFixture(bundle.board);
        setRecommendFixture(bundle.recommend);
        setMoments(bundle.moments);
        setStore(bundle.store);
      })
      .catch((error) => {
        console.error("Failed to load swimlanes fixtures", error);
        if (!cancelled) {
          setMoments(FALLBACK_MOMENTS);
          setStore(DEFAULT_STORE);
        }
      });
    return () => {
      cancelled = true;
      clearFillTimers();
    };
  }, [clearFillTimers]);

  const staggerFill = useCallback(
    (nextBoard: Board, generation: number) => {
      setBoard(nextBoard);
      setRevealed(new Set());
      const placements = placementsByStrength(nextBoard);
      if (placements.length === 0) {
        if (runGeneration.current === generation) {
          setIsRunning(false);
        }
        return;
      }
      placements.forEach((placement, index) => {
        const timer = setTimeout(() => {
          if (runGeneration.current !== generation) {
            return;
          }
          setRevealed((prev) => {
            const next = new Set(prev);
            next.add(cellKey(placement.laneIndex, placement.dayIndex));
            return next;
          });
          if (index === placements.length - 1) {
            setIsRunning(false);
          }
        }, 180 + index * FILL_MS);
        fillTimers.current.push(timer);
      });
    },
    [],
  );

  const playSimulation = useCallback(async () => {
    if (isRunning) {
      return;
    }
    clearFillTimers();
    const generation = runGeneration.current + 1;
    runGeneration.current = generation;
    setIsRunning(true);
    setBoard(emptyLaneDays(moments));
    setRevealed(new Set());

    const live = await buildBoardFromApi(weekOffset, moments, store);
    if (runGeneration.current !== generation) {
      return;
    }
    let nextBoard: Board;
    if (live) {
      nextBoard = live.board;
      setStore(live.store);
    } else if (boardFixture) {
      nextBoard = boardFromFixture(boardFixture, moments);
    } else {
      nextBoard = emptyLaneDays(moments);
    }
    staggerFill(nextBoard, generation);
  }, [
    boardFixture,
    clearFillTimers,
    isRunning,
    moments,
    staggerFill,
    store,
    weekOffset,
  ]);

  const resetToThisWeek = useCallback(() => {
    setWeekOffset(0);
    clearBoardForWeek();
  }, [clearBoardForWeek]);

  const shiftWeek = useCallback(
    (delta: number) => {
      setWeekOffset((current) => current + delta);
      clearBoardForWeek();
    },
    [clearBoardForWeek],
  );

  const openCell = useCallback(
    async (laneIndex: number, dayIndex: number, cell: BoardCell) => {
      const moment = moments[laneIndex];
      if (!moment) {
        return;
      }
      const label = momentLabel(moment, dayIndex);
      const focus = cell.categories[0]?.category || null;
      setFocusCategory(focus);
      setPanelOpen(true);
      setPanelLoading(true);
      setPanelError(null);
      setPanelPayload(null);

      const live = await fetchRecommend(
        store.id || STORE_ID,
        dayIndex,
        moment.hour,
      );
      const raw =
        live
        || (recommendFixture
          ? fixtureRecommend(recommendFixture, dayIndex, moment.hour, label)
          : null);

      if (!raw) {
        setPanelLoading(false);
        setPanelError("No data for this slot");
        return;
      }
      if (live?.store) {
        setStore((current) => ({ ...current, ...live.store }));
      }
      setPanelPayload(scopeRecommendToCell(raw, cell));
      setPanelLoading(false);
    },
    [moments, recommendFixture, store.id],
  );

  return (
    <div className="swimlanes">
      <header className="swimlanes-header">
        <div className="swimlanes-brand-cluster">
          <button
            type="button"
            className="swimlanes-menu"
            aria-label="Main menu"
            onClick={onToggleDrawer}
          >
            <Menu size={22} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <div className="swimlanes-brand">Moments</div>
          <div className="swimlanes-week-nav">
            <button
              type="button"
              className="swimlanes-week-arrow"
              aria-label="Previous week"
              onClick={() => shiftWeek(-1)}
            >
              ‹
            </button>
            <button
              type="button"
              className="swimlanes-week-arrow"
              aria-label="Next week"
              onClick={() => shiftWeek(1)}
            >
              ›
            </button>
          </div>
        </div>
        <div className="swimlanes-controls">
          <button
            type="button"
            className="swimlanes-pill"
            onClick={resetToThisWeek}
          >
            Today
          </button>
          <div className="swimlanes-run-slot">
            {isRunning ? (
              <WanderingEyes />
            ) : (
              <button
                type="button"
                className="swimlanes-run"
                aria-label="Run simulation"
                onClick={() => {
                  void playSimulation();
                }}
              >
                <svg viewBox="0 0 12 12" aria-hidden="true">
                  <path d="M2.5 1.2v9.6L11 6z" />
                </svg>
                Run
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="swimlanes-main">
        <SwimlanesBoard
          moments={moments}
          weekOffset={weekOffset}
          board={board}
          revealed={revealed}
          onOpenCell={(lane, day, cell) => {
            void openCell(lane, day, cell);
          }}
        />
      </main>

      <SlotPanel
        open={panelOpen}
        loading={panelLoading}
        error={panelError}
        payload={panelPayload}
        focusCategory={focusCategory}
        onClose={() => setPanelOpen(false)}
      />
    </div>
  );
}
