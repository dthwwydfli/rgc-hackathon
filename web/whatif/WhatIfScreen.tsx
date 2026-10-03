import { useEffect, useMemo, useState } from "react";
import { cellKey, formatPence, shareToPct } from "../data/parse-json";
import type { PredictionsPayload, Product } from "../data/types";
import { simulateWhatIfShares } from "./simulate-whatif";

const ZONES = ["till", "entrance_chiller", "snack_aisle"];

interface WhatIfScreenProps {
  products: Product[];
  predictions: PredictionsPayload | null;
  selectedProductId: string | null;
  selectedPersonaId: string | null;
  selectedMomentId: string | null;
  loadError: string | null;
}

export function WhatIfScreen({
  products,
  predictions,
  selectedProductId,
  selectedPersonaId,
  selectedMomentId,
  loadError,
}: WhatIfScreenProps) {
  const product = useMemo(() => {
    return products.find((item) => item.id === selectedProductId) || products[0] || null;
  }, [products, selectedProductId]);

  const [zone, setZone] = useState("till");
  const [pricePence, setPricePence] = useState("0");
  const [claim, setClaim] = useState("");
  const [ran, setRan] = useState(false);

  useEffect(() => {
    if (!product) {
      return;
    }
    setZone(product.zone);
    setPricePence(String(product.price_pence));
    setClaim(product.fop_claim || "");
    setRan(false);
  }, [product]);

  if (loadError) {
    return <p className="p-6 text-sm text-red-600">{loadError}</p>;
  }
  if (!predictions) {
    return <p className="p-6 text-sm text-[var(--muted)]">Loading what-if…</p>;
  }
  if (!product) {
    return <p className="p-6 text-sm text-red-600">No product selected.</p>;
  }

  const personaId = selectedPersonaId || "gym_regular";
  const momentId = selectedMomentId || "morning_rush";
  const key = cellKey(personaId, momentId);
  const cell = predictions.cells[key];

  if (!cell) {
    return (
      <p className="p-6 text-sm text-red-600">No locked prediction for {key}.</p>
    );
  }

  const parsedPrice = Number.parseInt(pricePence, 10);
  const priceValid = Number.isInteger(parsedPrice) && parsedPrice >= 0;

  const unchanged =
    zone === product.zone
    && priceValid
    && parsedPrice === product.price_pence
    && claim.trim() === (product.fop_claim || "").trim();

  const nextShares =
    !priceValid
      ? null
      : unchanged
        ? { ...cell.predicted_shares }
        : simulateWhatIfShares({
            baseShares: cell.predicted_shares,
            productId: product.id,
            fromZone: product.zone,
            toZone: zone,
            pricePence: parsedPrice,
            basePricePence: product.price_pence,
          });

  const before = shareToPct(cell.predicted_shares[product.id]);
  const after = nextShares ? shareToPct(nextShares[product.id]) : null;

  return (
    <div className="overflow-auto p-6">
      <h2 className="m-0 text-2xl font-normal text-[var(--ink)]">What-if</h2>
      <div className="mt-4 rounded border border-[#6a6ae2] bg-[rgba(106,106,226,0.12)] px-4 py-3 text-[11px] font-semibold uppercase tracking-wide">
        Simulated, not validated
      </div>
      <p className="mt-3 text-sm text-[var(--muted)]">
        {product.name} · {personaId} · {momentId}
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span>
            Zone <span className="text-[var(--muted)]">(negotiate with retailer)</span>
          </span>
          <select
            value={zone}
            onChange={(event) => {
              setZone(event.target.value);
              setRan(false);
            }}
            className="h-10 min-w-44 rounded border border-[var(--line)] px-3"
          >
            {ZONES.map((item) => (
              <option key={item} value={item}>
                {item.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span>
            Price, pence <span className="text-[var(--muted)]">(brand controls)</span>
          </span>
          <input
            type="number"
            min={0}
            step={1}
            value={pricePence}
            onChange={(event) => {
              setPricePence(event.target.value);
              setRan(false);
            }}
            className="h-10 w-36 rounded border border-[var(--line)] px-3"
          />
        </label>

        <label className="flex min-w-56 flex-1 flex-col gap-1 text-sm">
          <span>
            Front-of-pack claim <span className="text-[var(--muted)]">(brand controls)</span>
          </span>
          <input
            type="text"
            value={claim}
            onChange={(event) => {
              setClaim(event.target.value);
              setRan(false);
            }}
            className="h-10 rounded border border-[var(--line)] px-3"
          />
        </label>

        <button
          type="button"
          onClick={() => setRan(true)}
          className="h-10 rounded bg-[var(--action-green)] px-4 text-sm font-medium text-white hover:brightness-95"
        >
          Re-run
        </button>
      </div>

      {!priceValid ? (
        <p className="mt-4 text-sm text-red-600">
          Price must be a non-negative integer (pence).
        </p>
      ) : null}

      {(ran || nextShares) && priceValid && nextShares ? (
        <div className="mt-6 rounded border border-dashed border-[#6a6ae2] p-4">
          <p className="m-0 text-sm">
            {zone.replaceAll("_", " ")}: {before}% to {after}% · price {formatPence(parsedPrice)}
          </p>
          {claim.trim() ? (
            <p className="mt-2 text-sm text-[var(--muted)]">
              Front-of-pack claim (brand controls): {claim.trim()}
            </p>
          ) : null}
          {unchanged ? (
            <p className="mt-2 text-sm text-[var(--muted)]">
              No levers changed — matches locked prediction shares.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
