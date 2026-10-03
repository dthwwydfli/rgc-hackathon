import { formatPct } from "../data/parse-json";
import type { PredictionsPayload, ResultsPayload } from "../data/types";

interface ValidationScreenProps {
  results: ResultsPayload | null;
  predictions: PredictionsPayload | null;
  loadError: string | null;
}

export function ValidationScreen({ results, predictions, loadError }: ValidationScreenProps) {
  if (loadError) {
    return <p className="p-6 text-sm text-red-600">{loadError}</p>;
  }
  if (!results) {
    return <p className="p-6 text-sm text-[var(--muted)]">Loading validation…</p>;
  }

  const gapsRoot = results.gaps as {
    say_vs_do?: Array<{ summary: string; count: number; response_ids?: string[] }>;
    familiarity_pick_share?: { pct: number; n: number };
  } | undefined;
  const sayVsDo = gapsRoot?.say_vs_do || [];
  const familiarity = gapsRoot?.familiarity_pick_share;
  const calibration = results.calibration;

  return (
    <div className="overflow-auto p-6">
      <h2 className="m-0 text-2xl font-normal text-[var(--ink)]">Validation</h2>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Metric
          label="Our accuracy"
          value={formatPct(results.accuracy.overall.pct, results.accuracy.overall.n)}
        />
        <Metric
          label="Cheapest wins"
          value={formatPct(results.baselines.cheapest_wins.pct, results.baselines.cheapest_wins.n)}
        />
        <Metric
          label="Random"
          value={formatPct(results.baselines.random.pct, results.baselines.random.n)}
        />
        <Metric label="Choices scored" value={String(results.n_scored)} />
        <Metric label="Other (excluded)" value={String(results.n_other)} />
      </div>

      <section className="mt-8 rounded border border-[var(--line)] p-4">
        <h3 className="m-0 text-sm font-medium text-[var(--ink)]">Locked predictions</h3>
        <p className="mt-2 text-xs uppercase tracking-wide text-[var(--muted)]">
          {predictions
            ? `Locked at ${predictions.locked_at} · commit ${predictions.git_commit}`
            : "Lock metadata unavailable."}
        </p>
      </section>

      <h3 className="mt-8 text-base font-medium">By moment</h3>
      <ul className="m-0 list-none p-0">
        {Object.entries(results.accuracy.by_moment || {}).map(([momentId, stat]) => (
          <li key={momentId} className="border-b border-[var(--line)] py-3 text-sm">
            {momentId}: {formatPct(stat.pct, stat.n)}
          </li>
        ))}
      </ul>

      <h3 className="mt-8 text-base font-medium">By persona</h3>
      <ul className="m-0 list-none p-0">
        {Object.entries(results.accuracy.by_persona || {}).map(([personaId, stat]) => (
          <li key={personaId} className="border-b border-[var(--line)] py-3 text-sm">
            {personaId}: {formatPct(stat.pct, stat.n)}
          </li>
        ))}
      </ul>

      <h3 className="mt-8 text-base font-medium">Calibration</h3>
      <p className="text-sm text-[var(--ink)]">
        {calibration.status === "insufficient"
          ? calibration.message || "Not enough data to calibrate yet"
          : `Locked held-out ${calibration.locked_heldout_pct}% · calibrated held-out ${calibration.calibrated_heldout_pct}% (n=${calibration.n})`}
      </p>

      <h3 className="mt-8 text-base font-medium">Say vs do</h3>
      <ul className="m-0 list-none p-0">
        {sayVsDo.length === 0 ? (
          <li className="py-3 text-sm italic text-[var(--muted)]">No say-vs-do gaps yet.</li>
        ) : (
          sayVsDo.map((gap) => (
            <li key={gap.summary} className="border-b border-[var(--line)] py-3 text-sm">
              {gap.summary} (n={gap.count}; {(gap.response_ids || []).join(", ")})
            </li>
          ))
        )}
      </ul>
      <p className="mt-4 text-sm text-[var(--muted)]">
        Familiarity picks:{" "}
        <span className="uppercase tracking-wide">
          {familiarity ? formatPct(familiarity.pct, familiarity.n) : "—"}
        </span>
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--line)] p-4">
      <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
        {label}
      </span>
      <span className="mt-1 block text-2xl font-normal text-[var(--ink)]">{value}</span>
    </div>
  );
}
