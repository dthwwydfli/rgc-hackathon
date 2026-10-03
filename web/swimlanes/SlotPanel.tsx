import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowLeftRight,
  Boxes,
  Calendar,
  CalendarCheck,
  CalendarRange,
  CircleAlert,
  CircleCheck,
  CircleX,
  ClipboardList,
  Clock,
  Globe,
  LoaderCircle,
  MapPin,
  Package,
  PackageX,
  ShoppingBag,
  Store,
  Sun,
  TrendingUp,
  User,
  Users,
  X,
} from "lucide-react";
import { SOURCE_CAVEAT_PATTERN } from "./constants";
import { filterCategories } from "./load-board";
import { suggestAction } from "./suggest-action";
import type { RecommendPayload, StockRow, WeekThatDiffers } from "./types";

type TabId = "stock" | "shoppers" | "weeks" | "channels";

interface SlotPanelProps {
  open: boolean;
  loading: boolean;
  error: string | null;
  payload: RecommendPayload | null;
  focusCategory: string | null;
  onClose: () => void;
}

function pct(n: number): string {
  return Math.round(Number(n) * 100) + "%";
}

function pickCaveat(payload: RecommendPayload): string | null {
  const fromList = (payload.caveats || []).find(
    (line) => line && !SOURCE_CAVEAT_PATTERN.test(line),
  );
  if (fromList) {
    return fromList;
  }
  const volume = payload.basis?.volume;
  if (volume && !SOURCE_CAVEAT_PATTERN.test(volume)) {
    return volume;
  }
  return null;
}

function WeekNumber({ n }: { n: number }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <circle
        cx="16"
        cy="16"
        r="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <text
        x="16"
        y="21"
        textAnchor="middle"
        fontSize="12"
        fontWeight="700"
        fontFamily="Helvetica, Arial, sans-serif"
        fill="currentColor"
      >
        {n}
      </text>
    </svg>
  );
}

function Stat({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="swimlanes-stat">
      {icon}
      <div>
        <em>{label}</em>
        <b>{value}</b>
      </div>
    </div>
  );
}

function AccordionLoader() {
  const track = "░".repeat(28);
  return (
    <div className="swimlanes-acc-loader" aria-hidden="true">
      <div className="acc-track">{track}</div>
      <div className="acc-layer" style={{ ["--delay" as string]: "0ms" }}>
        ████
      </div>
      <div className="acc-layer" style={{ ["--delay" as string]: "45ms" }}>
        ▓▓▓▓
      </div>
      <div className="acc-layer" style={{ ["--delay" as string]: "90ms" }}>
        ▒▒▒▒
      </div>
      <div className="acc-layer" style={{ ["--delay" as string]: "135ms" }}>
        ░░░░
      </div>
    </div>
  );
}

function PersonaRow({ name, share, animate }: { name: string; share: number; animate: boolean }) {
  const target = Math.round(share * 100);
  const [display, setDisplay] = useState(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!animate) {
      return;
    }
    let frame = 0;
    const frames = 22;
    let raf = 0;
    const tick = () => {
      frame += 1;
      const t = Math.min(1, frame / frames);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(target * eased));
      if (frame < frames) {
        raf = requestAnimationFrame(tick);
      } else {
        setDisplay(target);
        setReady(true);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [animate, target]);

  return (
    <div className="swimlanes-persona">
      <div className="swimlanes-persona-name">{name}</div>
      <div className="swimlanes-persona-pct">{display}%</div>
      <div className="swimlanes-persona-track">
        {ready ? (
          <div
            className="swimlanes-persona-bar is-ready"
            style={{ ["--w" as string]: `${target}%` }}
          >
            <span />
          </div>
        ) : (
          <AccordionLoader />
        )}
      </div>
    </div>
  );
}

function StockCard({
  row,
  isFocus,
  differ,
}: {
  row: StockRow;
  isFocus: boolean;
  differ: WeekThatDiffers[];
}) {
  const action = suggestAction(row, differ);
  const examples = row.example_products || [];
  const iconSize = 15;

  return (
    <article className={"swimlanes-cat-card" + (isFocus ? " is-focus" : "")}>
      <h3>{row.category}</h3>
      <div className="swimlanes-stats">
        <Stat
          icon={<Package size={iconSize} strokeWidth={2} aria-hidden="true" />}
          label="Units / week"
          value={String(row.units_per_week)}
        />
        <Stat
          icon={<Boxes size={iconSize} strokeWidth={2} aria-hidden="true" />}
          label="Order qty"
          value={row.stock != null ? String(row.stock) : "n/a"}
        />
        <Stat
          icon={<ArrowLeftRight size={iconSize} strokeWidth={2} aria-hidden="true" />}
          label="Forecast range"
          value={row.range ? `${row.range[0]}-${row.range[1]}` : "n/a"}
        />
        <Stat
          icon={<TrendingUp size={iconSize} strokeWidth={2} aria-hidden="true" />}
          label="Vs usual share"
          value={
            row.times_usual_share != null ? `${row.times_usual_share}×` : "n/a"
          }
        />
        <Stat
          icon={<User size={iconSize} strokeWidth={2} aria-hidden="true" />}
          label="Top shopper"
          value={
            (row.bought_most_by || "n/a")
            + (row.that_persona_share != null
              ? ` · ${pct(row.that_persona_share)}`
              : "")
          }
        />
        {row.lowest_week != null ? (
          <Stat
            icon={<Activity size={iconSize} strokeWidth={2} aria-hidden="true" />}
            label="Week span"
            value={`${row.lowest_week}-${row.highest_week}`}
          />
        ) : null}
      </div>
      <div className="swimlanes-action-lines">
        <div className="swimlanes-action-line">
          <ClipboardList size={15} strokeWidth={2} aria-hidden="true" />
          <span>{action.shelf}</span>
        </div>
        <div className="swimlanes-action-line">
          <MapPin size={15} strokeWidth={2} aria-hidden="true" />
          <span>{action.zone}</span>
        </div>
        <div className="swimlanes-action-line">
          <Globe size={15} strokeWidth={2} aria-hidden="true" />
          <span>{action.online}</span>
        </div>
        {action.season ? (
          <div className="swimlanes-action-line">
            <Sun size={15} strokeWidth={2} aria-hidden="true" />
            <span>{action.season}</span>
          </div>
        ) : null}
      </div>
      {examples.length > 0 ? (
        <div className="swimlanes-example">
          <ShoppingBag size={15} strokeWidth={2} aria-hidden="true" />
          <span>
            Example · {examples[0].brand} {examples[0].name}
          </span>
        </div>
      ) : null}
    </article>
  );
}

function PlaceTab({ differ }: { differ: WeekThatDiffers[] }) {
  const hasXmas = differ.some((w) =>
    /christmas|holiday|run-up/i.test(String(w.calendar || "")),
  );
  const seasonLine = hasXmas
    ? "Seasonality: Christmas run-up weeks lift confectionery and gift snacks - lean into that online and in-store."
    : "Seasonality: ordinary weeks stay flat; only bank holidays and pre-holiday days move the forecast.";

  return (
    <>
      <div className="swimlanes-channel-grid">
        <section className="swimlanes-channel-card">
          <h3>
            <Store size={16} strokeWidth={2} aria-hidden="true" />
            In-store
          </h3>
          <ul>
            <li className="do">
              <CircleCheck size={16} strokeWidth={2} aria-hidden="true" />
              <span>Face winners at eye level for this hour</span>
            </li>
            <li className="do">
              <CircleCheck size={16} strokeWidth={2} aria-hidden="true" />
              <span>Keep predicted stock qty on the shelf</span>
            </li>
            <li className="dont">
              <CircleX size={16} strokeWidth={2} aria-hidden="true" />
              <span>Do not bury peak SKUs behind slow movers</span>
            </li>
            <li className="dont">
              <CircleX size={16} strokeWidth={2} aria-hidden="true" />
              <span>Skip deep promotions on weak share slots</span>
            </li>
          </ul>
        </section>
        <section className="swimlanes-channel-card">
          <h3>
            <Globe size={16} strokeWidth={2} aria-hidden="true" />
            Online
          </h3>
          <ul>
            <li className="do">
              <CircleCheck size={16} strokeWidth={2} aria-hidden="true" />
              <span>Feature this slot's top category on homepage / app tile</span>
            </li>
            <li className="do">
              <CircleCheck size={16} strokeWidth={2} aria-hidden="true" />
              <span>
                {hasXmas
                  ? "Push seasonal gift packs and multipacks in run-up weeks"
                  : "Match ad daypart to this moment's clock"}
              </span>
            </li>
            <li className="dont">
              <CircleX size={16} strokeWidth={2} aria-hidden="true" />
              <span>Do not lead with off-moment categories</span>
            </li>
            <li className="dont">
              <CircleX size={16} strokeWidth={2} aria-hidden="true" />
              <span>
                {hasXmas
                  ? "Hold back summer / ice campaigns during Christmas run-up"
                  : "Avoid all-day banners that ignore daypart"}
              </span>
            </li>
          </ul>
        </section>
      </div>
      <div className="swimlanes-season-note">
        <Sun size={16} strokeWidth={2} aria-hidden="true" />
        <span>{seasonLine}</span>
      </div>
    </>
  );
}

export function SlotPanel({
  open,
  loading,
  error,
  payload,
  focusCategory,
  onClose,
}: SlotPanelProps) {
  const [tab, setTab] = useState<TabId>("stock");
  const [peopleAnimated, setPeopleAnimated] = useState(false);

  useEffect(() => {
    if (open) {
      setTab("stock");
      setPeopleAnimated(false);
    }
  }, [open, payload]);

  if (!open) {
    return null;
  }

  if (loading) {
    return (
      <div className="swimlanes-panel">
        <button
          className="swimlanes-backdrop"
          type="button"
          aria-label="Close"
          onClick={onClose}
        />
        <div className="swimlanes-dialog" role="dialog" aria-modal="true">
          <div className="swimlanes-panel-loading">
            <LoaderCircle size={22} strokeWidth={2} aria-hidden="true" />
            <span>Loading</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !payload) {
    return (
      <div className="swimlanes-panel">
        <button
          className="swimlanes-backdrop"
          type="button"
          aria-label="Close"
          onClick={onClose}
        />
        <div className="swimlanes-dialog" role="dialog" aria-modal="true">
          <div className="swimlanes-panel-loading">
            <CircleAlert size={22} strokeWidth={2} aria-hidden="true" />
            <span>{error || "No data for this slot"}</span>
          </div>
        </div>
      </div>
    );
  }

  const store = payload.store;
  const slot = payload.slot || { weekday: "", hour: "", moment: "Moment" };
  const stockFiltered = filterCategories(
    (payload.stock_most || []).map((row) => ({
      ...row,
      units: row.units_per_week,
    })),
  ).map((filtered) => {
    const full = (payload.stock_most || []).find(
      (row) => row.category === filtered.category,
    );
    return full || (filtered as unknown as StockRow);
  });

  let ordered = stockFiltered;
  if (focusCategory) {
    ordered = [
      ...stockFiltered.filter((row) => row.category === focusCategory),
      ...stockFiltered.filter((row) => row.category !== focusCategory),
    ];
  }

  const shoppers = Object.entries(payload.shoppers_in_this_slot || {}).slice(0, 5);
  const differ = payload.weeks_that_differ || [];
  const weeks = payload.weeks || 12;
  const from = payload.from || "";
  const caveat = pickCaveat(payload);
  const storeLabel = [
    store?.store_name || store?.fascia || "Store",
    store?.postcode,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="swimlanes-panel">
      <button
        className="swimlanes-backdrop"
        type="button"
        aria-label="Close"
        onClick={onClose}
      />
      <div className="swimlanes-dialog" role="dialog" aria-modal="true">
        <div className="swimlanes-dialog-body">
          <div className="swimlanes-dialog-head">
            <div className="swimlanes-dialog-head-top">
              <div>
                <h2>{slot.moment || "Moment"}</h2>
              </div>
              <button
                className="swimlanes-close"
                type="button"
                aria-label="Close"
                onClick={onClose}
              >
                <X size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
            <div className="swimlanes-meta-row">
              <div className="swimlanes-meta-chip" title="When">
                <Clock size={15} strokeWidth={2} aria-hidden="true" />
                <span>
                  {slot.weekday} {slot.hour}
                </span>
              </div>
              <div className="swimlanes-meta-chip" title="Store">
                <Store size={15} strokeWidth={2} aria-hidden="true" />
                <span>{storeLabel}</span>
              </div>
              <div className="swimlanes-meta-chip" title="Forecast">
                <CalendarRange size={15} strokeWidth={2} aria-hidden="true" />
                <span>{weeks} weeks</span>
              </div>
            </div>
          </div>

          <div className="swimlanes-tabs" role="tablist">
            {(
              [
                ["stock", "Stock", Package],
                ["shoppers", "People", Users],
                ["weeks", "Weeks", Calendar],
                ["channels", "Place", MapPin],
              ] as const
            ).map(([id, label, Icon]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                onClick={() => {
                  setTab(id);
                  if (id === "shoppers") {
                    setPeopleAnimated(true);
                  }
                }}
              >
                <Icon size={18} strokeWidth={2} aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>

          <div className="swimlanes-tab-panels">
            <div
              className="swimlanes-tab-panel"
              role="tabpanel"
              hidden={tab !== "stock"}
            >
              {ordered.length === 0 ? (
                <div className="swimlanes-empty-tab">
                  <PackageX size={22} strokeWidth={2} aria-hidden="true" />
                  <span>No coffee or snack categories in this slot</span>
                </div>
              ) : (
                ordered.map((row) => (
                  <StockCard
                    key={row.category}
                    row={row}
                    isFocus={row.category === focusCategory}
                    differ={differ}
                  />
                ))
              )}
            </div>

            <div
              className="swimlanes-tab-panel"
              role="tabpanel"
              hidden={tab !== "shoppers"}
            >
              {shoppers.length === 0 ? (
                <div className="swimlanes-empty-tab">
                  <Users size={22} strokeWidth={2} aria-hidden="true" />
                  <span>No shopper mix for this slot</span>
                </div>
              ) : (
                shoppers.map(([name, share]) => (
                  <PersonaRow
                    key={name}
                    name={name}
                    share={Number(share)}
                    animate={peopleAnimated}
                  />
                ))
              )}
            </div>

            <div
              className="swimlanes-tab-panel"
              role="tabpanel"
              hidden={tab !== "weeks"}
            >
              <div className="swimlanes-horizon-banner">
                <CalendarRange size={18} strokeWidth={2} aria-hidden="true" />
                <div>
                  <b>Prediction · {weeks} weeks</b> from {from || "this week"}
                  {payload.basis?.horizon ? (
                    <>
                      <br />
                      {String(payload.basis.horizon).split(":")[0]}
                    </>
                  ) : null}
                </div>
              </div>
              {differ.length === 0 ? (
                <div className="swimlanes-empty-tab">
                  <CalendarCheck size={22} strokeWidth={2} aria-hidden="true" />
                  <span>No calendar outliers in this window</span>
                </div>
              ) : (
                differ.map((week) => (
                  <div className="swimlanes-week-card" key={`${week.week}-${week.date}`}>
                    <div className="swimlanes-week-num">
                      <WeekNumber n={week.week} />
                    </div>
                    <div>
                      <strong>{week.date}</strong>
                      <div className="swimlanes-week-meta">
                        <Calendar size={14} strokeWidth={2} aria-hidden="true" />
                        <span>{week.calendar || "Calendar shift"}</span>
                      </div>
                    </div>
                    {week.vs_typical_week != null ? (
                      <div className="swimlanes-week-mult">
                        {week.vs_typical_week}×
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>

            <div
              className="swimlanes-tab-panel"
              role="tabpanel"
              hidden={tab !== "channels"}
            >
              <PlaceTab differ={differ} />
            </div>
          </div>

          {caveat ? (
            <div className="swimlanes-caveat-bar">
              <CircleAlert size={15} strokeWidth={2} aria-hidden="true" />
              <span>{caveat}</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
