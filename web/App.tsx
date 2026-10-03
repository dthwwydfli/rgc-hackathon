import { useCallback, useEffect, useMemo, useState } from "react";
import { addWeeks, endOfWeek } from "date-fns";
import { loadConfig } from "./data/load-config";
import { loadPredictions } from "./data/load-predictions";
import { loadResults, startResultsRefresh } from "./data/load-results";
import type {
  Moment,
  Persona,
  PredictionsPayload,
  Product,
  ResultsPayload,
} from "./data/types";
import { pickBestSlot } from "./calendar/pick-best-slot";
import { OpportunityPanel } from "./calendar/OpportunityPanel";
import {
  type CalendarEvent,
  groupProductsByMoment,
  WeekCalendar,
  weekStartingMonday,
} from "./calendar/WeekCalendar";
import { PATHS } from "./lib/paths";
import { SideDrawer, type ScreenId } from "./shell/SideDrawer";
import { TopBar } from "./shell/TopBar";
import { SwimlanesScreen } from "./swimlanes/SwimlanesScreen";
import { ValidationScreen } from "./validation/ValidationScreen";
import { WhatIfScreen } from "./whatif/WhatIfScreen";

interface PanelSelection {
  productId: string;
  momentId: string;
  personaId: string;
  focusReturnId: string;
}

export function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [moments, setMoments] = useState<Moment[]>([]);
  const [predictions, setPredictions] = useState<PredictionsPayload | null>(null);
  const [results, setResults] = useState<ResultsPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [weekAnchor, setWeekAnchor] = useState(() => new Date());
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeScreen, setActiveScreen] = useState<ScreenId>("swimlanes");
  const [panelSelection, setPanelSelection] = useState<PanelSelection | null>(null);

  const weekStart = useMemo(() => weekStartingMonday(weekAnchor), [weekAnchor]);
  const weekEnd = useMemo(
    () => endOfWeek(weekStart, { weekStartsOn: 1 }),
    [weekStart],
  );

  const scoringPersonaId = useMemo(() => {
    return personas.find((persona) => !persona.excluded_from_scoring)?.id || null;
  }, [personas]);

  const events = useMemo((): CalendarEvent[] => {
    if (!results || !scoringPersonaId || moments.length === 0) {
      return [];
    }
    const slotted: CalendarEvent[] = [];
    for (const product of products) {
      const slot = pickBestSlot({
        productId: product.id,
        personaId: scoringPersonaId,
        moments,
        results,
      });
      if (!slot) {
        continue;
      }
      const moment = moments.find((item) => item.id === slot.momentId);
      if (!moment) {
        continue;
      }
      slotted.push({ product, slot, moment });
    }
    return slotted;
  }, [products, moments, results, scoringPersonaId]);

  const momentBlocks = useMemo(() => groupProductsByMoment(events), [events]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const [config, predictionsPayload, resultsPayload] = await Promise.all([
          loadConfig(PATHS),
          loadPredictions(PATHS),
          loadResults(PATHS),
        ]);
        if (cancelled) {
          return;
        }
        setProducts(config.products.products);
        setPersonas(config.personas.personas);
        setMoments(config.moments.moments);
        setPredictions(predictionsPayload.predictions);
        setResults(resultsPayload.results);
        setLoadError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : String(error);
        setLoadError(`Failed to load app data: ${message}`);
        console.error("boot failed", { cause: message });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void boot();

    const stopRefresh = startResultsRefresh(PATHS, (payload) => {
      setResults(payload.results);
    });

    return () => {
      cancelled = true;
      stopRefresh();
    };
  }, []);

  const openEvent = useCallback((selection: PanelSelection) => {
    setPanelSelection(selection);
  }, []);

  const closePanel = useCallback(() => {
    setPanelSelection(null);
  }, []);

  const calendarStatus = loading
    ? "Loading calendar…"
    : loadError
      ? loadError
      : null;

  if (activeScreen === "swimlanes") {
    return (
      <div className="flex h-full flex-col bg-white">
        <SideDrawer
          open={drawerOpen}
          activeScreen={activeScreen}
          onClose={() => setDrawerOpen(false)}
          onNavigate={setActiveScreen}
        />
        <SwimlanesScreen
          onToggleDrawer={() => setDrawerOpen((open) => !open)}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <TopBar
        weekStart={weekStart}
        weekEnd={weekEnd}
        onToggleDrawer={() => setDrawerOpen((open) => !open)}
        onToday={() => setWeekAnchor(new Date())}
        onPrevWeek={() => setWeekAnchor((current) => addWeeks(current, -1))}
        onNextWeek={() => setWeekAnchor((current) => addWeeks(current, 1))}
      />

      <SideDrawer
        open={drawerOpen}
        activeScreen={activeScreen}
        onClose={() => setDrawerOpen(false)}
        onNavigate={setActiveScreen}
      />

      <main className="flex min-h-0 flex-1 flex-col">
        {activeScreen === "calendar" ? (
          <WeekCalendar
            weekStart={weekStart}
            momentBlocks={momentBlocks}
            statusMessage={calendarStatus}
            isError={Boolean(loadError)}
            onOpenEvent={openEvent}
          />
        ) : null}

        {activeScreen === "validation" ? (
          <ValidationScreen
            results={results}
            predictions={predictions}
            loadError={loadError}
          />
        ) : null}

        {activeScreen === "whatif" ? (
          <WhatIfScreen
            products={products}
            predictions={predictions}
            selectedProductId={panelSelection?.productId || products[0]?.id || null}
            selectedPersonaId={scoringPersonaId}
            selectedMomentId={panelSelection?.momentId || moments[0]?.id || null}
            loadError={loadError}
          />
        ) : null}
      </main>

      <OpportunityPanel
        open={panelSelection !== null}
        productId={panelSelection?.productId || null}
        momentId={panelSelection?.momentId || null}
        personaId={panelSelection?.personaId || null}
        focusReturnId={panelSelection?.focusReturnId || null}
        products={products}
        moments={moments}
        results={results}
        onClose={closePanel}
      />
    </div>
  );
}
