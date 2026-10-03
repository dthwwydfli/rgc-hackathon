import { useEffect, useMemo, useState } from "react";
import { addWeeks, endOfWeek, startOfWeek } from "date-fns";
import { loadConfig } from "./data/load-config";
import { loadPredictions } from "./data/load-predictions";
import type {
  Moment,
  Persona,
  PredictionsPayload,
  Product,
} from "./data/types";
import { PATHS } from "./lib/paths";
import { SideDrawer, type ScreenId } from "./shell/SideDrawer";
import { TopBar } from "./shell/TopBar";
import { SwimlanesScreen } from "./swimlanes/SwimlanesScreen";
import { WhatIfScreen } from "./whatif/WhatIfScreen";

export function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [moments, setMoments] = useState<Moment[]>([]);
  const [predictions, setPredictions] = useState<PredictionsPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [weekAnchor, setWeekAnchor] = useState(() => new Date());
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeScreen, setActiveScreen] = useState<ScreenId>("swimlanes");

  const weekStart = useMemo(
    () => startOfWeek(weekAnchor, { weekStartsOn: 1 }),
    [weekAnchor],
  );
  const weekEnd = useMemo(
    () => endOfWeek(weekStart, { weekStartsOn: 1 }),
    [weekStart],
  );

  const scoringPersonaId = useMemo(() => {
    return personas.find((persona) => !persona.excluded_from_scoring)?.id || null;
  }, [personas]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const [config, predictionsPayload] = await Promise.all([
          loadConfig(PATHS),
          loadPredictions(PATHS),
        ]);
        if (cancelled) {
          return;
        }
        setProducts(config.products.products);
        setPersonas(config.personas.personas);
        setMoments(config.moments.moments);
        setPredictions(predictionsPayload.predictions);
        setLoadError(null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : String(error);
        setLoadError(`Failed to load app data: ${message}`);
        console.error("boot failed", { cause: message });
      }
    }

    void boot();

    return () => {
      cancelled = true;
    };
  }, []);

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
        {activeScreen === "whatif" ? (
          <WhatIfScreen
            products={products}
            predictions={predictions}
            selectedProductId={products[0]?.id || null}
            selectedPersonaId={scoringPersonaId}
            selectedMomentId={moments[0]?.id || null}
            loadError={loadError}
          />
        ) : null}
      </main>
    </div>
  );
}
