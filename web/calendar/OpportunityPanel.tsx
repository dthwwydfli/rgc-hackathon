import { useEffect, useId, useRef } from "react";
import {
  Ban,
  CircleDollarSign,
  ClipboardList,
  Layers,
  MapPin,
  Store,
  X,
} from "lucide-react";
import type {
  ActionOwner,
  Effort,
  Moment,
  Product,
  ResultsPayload,
} from "../data/types";
import { cellKey, formatCostPence } from "../data/parse-json";
import { pickBestSlot } from "./pick-best-slot";

const EFFORT_LABEL: Record<Effort, string> = {
  S: "Low lift",
  M: "Medium lift",
  L: "High lift",
};

const OWNER_LABEL: Record<ActionOwner, string> = {
  brand: "Brand",
  retailer: "Retailer",
};

function formatFixtureZone(zone: string): string {
  return zone
    .split("_")
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

interface OpportunityPanelProps {
  open: boolean;
  productId: string | null;
  momentId: string | null;
  personaId: string | null;
  focusReturnId: string | null;
  products: Product[];
  moments: Moment[];
  results: ResultsPayload | null;
  onClose: () => void;
}

export function OpportunityPanel({
  open,
  productId,
  momentId,
  personaId,
  focusReturnId,
  products,
  moments,
  results,
  onClose,
}: OpportunityPanelProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    previouslyFocused.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) {
        return;
      }
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      return;
    }
    if (previouslyFocused.current) {
      previouslyFocused.current.focus();
      previouslyFocused.current = null;
      return;
    }
    if (focusReturnId) {
      document.getElementById(focusReturnId)?.focus();
    }
  }, [open, focusReturnId]);

  if (!open) {
    return null;
  }

  const product = products.find((item) => item.id === productId);
  const moment = moments.find((item) => item.id === momentId);
  const key = personaId && momentId ? cellKey(personaId, momentId) : null;
  const cell = key && results ? results.cells[key] : undefined;
  const action = productId ? cell?.actions_by_product?.[productId] : undefined;

  const slot =
    productId && personaId && results
      ? pickBestSlot({
          productId,
          personaId,
          moments,
          results,
        })
      : null;

  const productName = product?.name || productId || "Product";
  const momentName = moment?.name || momentId || "Moment";
  const fixtureZone = product?.zone
    ? formatFixtureZone(product.zone)
    : "—";
  const ownerLabel = action?.owner ? OWNER_LABEL[action.owner] : "—";
  const effortLabel = action?.effort
    ? EFFORT_LABEL[action.effort] || action.effort
    : "—";

  return (
    <div className="fixed inset-0 z-[60]">
      <button
        type="button"
        className="absolute inset-0 bg-black/30"
        aria-label="Close panel"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-white shadow-2xl"
      >
        <div className="flex items-center justify-end border-b border-[var(--line)] p-2">
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full hover:bg-black/5"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <div className="overflow-auto p-5">
          <h2 id={titleId} className="m-0 text-xl font-medium text-[var(--ink)]">
            {productName}
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Shopping occasion · {momentName}
          </p>
          <p className="mt-2 text-xs uppercase tracking-wide text-[var(--muted)]">
            {slot?.rankLabel || "No ranked slot"}
          </p>

          <div className="mt-6">
            <h3 className="m-0 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              <ClipboardList size={14} aria-hidden="true" />
              Recommended trial
            </h3>
            <p className="mt-2 text-base text-[var(--ink)]">
              {action?.next_step || "No next step listed for this cell."}
            </p>
          </div>

          <div className="mt-6 grid grid-cols-3 gap-3">
            <div>
              <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                <CircleDollarSign size={14} aria-hidden="true" />
                Trial investment
              </span>
              <p className="mt-1 text-sm">
                {action ? formatCostPence(action.cost_pence) : "Cost unknown"}
              </p>
            </div>
            <div>
              <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                <Store size={14} aria-hidden="true" />
                Execution owner
              </span>
              <p className="mt-1 text-sm">{ownerLabel}</p>
            </div>
            <div>
              <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                <Layers size={14} aria-hidden="true" />
                Operational lift
              </span>
              <p className="mt-1 text-sm">{effortLabel}</p>
            </div>
          </div>

          <div className="mt-6">
            <h3 className="m-0 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              <Ban size={14} aria-hidden="true" />
              Media deferred
            </h3>
            <p className="mt-2 text-sm text-[var(--ink)]">
              {action?.expensive_action_avoided || "—"}
            </p>
          </div>

          <p className="mt-8 flex items-center gap-2 text-xs uppercase tracking-wide text-[var(--muted)]">
            <MapPin size={14} aria-hidden="true" className="shrink-0" />
            Fixture · {fixtureZone} · Assumed dwell · {moment?.dwell_label || "—"}
          </p>
        </div>
      </div>
    </div>
  );
}
