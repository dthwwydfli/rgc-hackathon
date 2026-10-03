"""Shelf plan: the hourly forecast turned into a layout that is set once and a short list of refill visits.

Refilling at every moment costs more labour than it earns. This layer keeps the forecast and changes the action:
  layout   which item sits in which zone for the whole period, so each zone holds what sells when shoppers reach it
  visits   the fewest refills per day, and their hours, before the shelf empties
  money    margin kept minus labour, against refilling at every moment and at every hour

    seen(zone, hour)   door  = 1                          every shopper passes it
                       aisle = P(basket >= 2 | hour)      shoppers with time for a second item
                       back  = P(basket >= 3 | hour)      shoppers who browse
Basket size is real till data (Edinburgh bakery) and stands in for time in store until a retailer supplies
door-counter or Wi-Fi dwell.  Run: python -m backend.shelf
"""
import json
from datetime import date as Date, timedelta
from functools import lru_cache
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.stats import poisson

from . import simulate
from .config import EVIDENCE, HOURS, moment
from .data import bakery_baskets

ZONES = {"door": 4, "aisle": 5, "back": 4}   # item positions per zone; the back takes any overflow
FACINGS, PER_FACING = 40, 8                  # fixture size: facings, units per facing
WAGE, FILL_MIN, MARGIN = 12.71, 15, 1.00     # GBP per hour, minutes per refill visit, GBP margin per unit
PRIOR_TX, THIN_TX, MAX_FILLS = 50, 100, 8
DAYTYPE = {0: "Mon-Thu", 1: "Fri-Sun"}


@lru_cache(maxsize=1)
def seen() -> pd.DataFrame:
    """Share of shoppers who reach each zone, per hour and day type. Hours with few transactions are pulled toward the all-day share."""
    t = bakery_baskets()
    idx = pd.MultiIndex.from_product([HOURS, [0, 1]], names=["hour", "weekend"])
    out = pd.DataFrame({"tx": t.groupby(["hour", "weekend"]).size().reindex(idx, fill_value=0)})
    for z, k in zip(ZONES, (1, 2, 3)):
        hit = t[t.n >= k].groupby(["hour", "weekend"]).size().reindex(idx, fill_value=0)
        out[z] = (hit + PRIOR_TX * (t.n >= k).mean()) / (out.tx + PRIOR_TX)
    return out.reset_index()


def demand(station: str, start: Date, days: int = 7) -> pd.DataFrame:
    """Forecast units per day, item and hour."""
    rows = []
    for k in range(days):
        sim = simulate.simulate(station, start + timedelta(days=k))
        rows += [{"date": sim["day"]["date"], "weekend": sim["day"]["weekend"], "item_id": c["item_id"], "item": c["item"], "hour": h, "units": u}
                 for c in sim["cells"] for h, u in c["by_hour"].items()]
    return pd.DataFrame(rows)


def lost_table(M: np.ndarray, cap: np.ndarray) -> np.ndarray:
    """L[s, e]: expected units lost if every item is filled to `cap` at hour index s and not again before e. Demand is Poisson."""
    n = M.shape[1]
    cum = np.concatenate([np.zeros((len(M), 1)), M.cumsum(1)], axis=1)
    L = np.zeros((n + 1, n + 1))
    for s in range(n):
        for e in range(s + 1, n + 1):
            mu = cum[:, e] - cum[:, s]
            L[s, e] = np.nan_to_num(mu * poisson.sf(cap - 1, mu) - cap * poisson.sf(cap, mu)).sum()
    return L


def lost(L: np.ndarray, fills: tuple) -> float:
    return float(sum(L[a, b] for a, b in zip(fills, fills[1:] + (len(L) - 1,))))


def best_fills(L: np.ndarray, k: int) -> tuple:
    """The k fill hours (the first at opening) that lose the fewest units."""
    return min(((0,) + c for c in combinations(range(1, len(L) - 1), k - 1)), key=lambda f: lost(L, f))


def plan(station: str, start: Date, days: int = 7) -> dict:
    D = demand(station, start, days)
    names = D.drop_duplicates("item_id").set_index("item_id").item
    S = seen().set_index(["weekend", "hour"])[list(ZONES)]
    W = D.pivot_table(index="item_id", columns=["weekend", "hour"], values="units", aggfunc="sum").fillna(0)
    V = pd.DataFrame(W.values @ S.reindex(W.columns).values, index=W.index, columns=list(ZONES))   # units seen over the period, per item and zone

    # layout: one position per item, chosen to maximise units seen
    slots = [z for z, n in ZONES.items() for _ in range(n)] + ["back"] * max(len(W) - sum(ZONES.values()), 0)
    r, c = linear_sum_assignment(-V[slots].values)
    zone = pd.Series([slots[j] for j in c], index=V.index[r])
    rank = pd.Series(slots[:len(W)], index=W.sum(axis=1).sort_values(ascending=False).index)      # usual rule: best sellers nearest the door
    total = float(W.values.sum())
    seen_units = lambda z: float(sum(V.loc[i, z[i]] for i in z.index))
    peak = D.assign(moment=[moment(h, bool(w)) for h, w in zip(D.hour, D.weekend)]).groupby(["item_id", "moment"]).units.sum()
    lay = [{"zone": zone[i], "item_id": i, "item": names[i], "units": round(float(W.loc[i].sum()), 1), "units_seen": round(float(V.loc[i, zone[i]]), 1),
            "peak_moment": peak[i].idxmax(), "zone_by_volume_rank": rank[i]} for i in sorted(zone.index, key=lambda i: (slots.index(zone[i]), -W.loc[i].sum()))]

    # visits: per day type, on the average day's seen demand
    fill_cost, moments = WAGE * FILL_MIN / 60, tuple(i for i, h in enumerate(HOURS) if i == 0 or moment(h, False) != moment(HOURS[i - 1], False))
    mean_daily = sum(V.loc[i, zone[i]] for i in zone.index) / days
    cap = pd.Series({i: max(1, round(FACINGS * V.loc[i, zone[i]] / days / mean_daily)) * PER_FACING for i in zone.index})
    visits, week = {}, {"labour_saved": 0.0, "margin_change": 0.0}
    for we, n_days in D.drop_duplicates("date").weekend.value_counts().sort_index().items():
        M = np.array([[W.loc[i].get((we, h), 0.0) / n_days * S.loc[(we, h), zone[i]] for h in HOURS] for i in zone.index])
        L, tot = lost_table(M, cap.values), float(M.sum())
        row = lambda f: {"fills": len(f), "hours": [HOURS[i] for i in f], "units_sold": round(tot - lost(L, f), 1), "units_lost": round(lost(L, f), 1),
                         "labour": round(len(f) * fill_cost, 2), "net": round(MARGIN * (tot - lost(L, f)) - len(f) * fill_cost, 2)}
        options = [row(best_fills(L, k)) for k in range(1, MAX_FILLS + 1)]
        pick, every_moment = max(options, key=lambda o: o["net"]), row(moments)
        visits[DAYTYPE[we]] = {"days": int(n_days), "demand_seen": round(tot, 1), "plan": pick, "every_moment": every_moment,
                               "every_hour": row(tuple(range(len(HOURS)))), "options": options}
        week["labour_saved"] += n_days * (every_moment["labour"] - pick["labour"])
        week["margin_change"] += n_days * MARGIN * (pick["units_sold"] - every_moment["units_sold"])
    S0 = seen()
    return {"station": station, "start": start.isoformat(), "days": days, "layout": lay,
            "layout_gain": {"forecast_units": round(total, 1), "seen_by_volume_rank": round(seen_units(rank), 1), "seen_by_moment": round(seen_units(zone), 1),
                            "uplift_pct": round(100 * (seen_units(zone) / seen_units(rank) - 1), 2), "items_moved": int((zone != rank.reindex(zone.index)).sum())},
            "capacity": {names[i]: int(cap[i]) for i in zone.index}, "visits": visits,
            "period": {k: round(v, 2) for k, v in week.items()} | {"net_gain": round(week["labour_saved"] + week["margin_change"], 2)},
            "seen": S0.round(3).to_dict("records"), "thin_hours": sorted(S0[S0.tx < THIN_TX].hour.unique().tolist()),
            "assumptions": {"wage_gbp_per_hour": WAGE, "minutes_per_fill": FILL_MIN, "margin_gbp_per_unit": MARGIN, "facings": FACINGS,
                            "units_per_facing": PER_FACING, "zone_positions": ZONES},
            "evidence": [EVIDENCE["bakery"], EVIDENCE["nhanes"], EVIDENCE["tfl"]],
            "caveats": ["Sold and lost units are computed on the forecast, not measured. No store has run this plan.",
                        "Reach per zone is basket size at one Edinburgh bakery, 2016-17, used as a stand-in for time in store.",
                        f"Hours with under {THIN_TX} bakery transactions use mostly the all-day share.",
                        "Every item is treated as visibility-driven. Items people come in for are found wherever they sit; pin those by hand.",
                        "Wage, minutes per fill, margin and fixture size are assumptions; a retailer supplies its own."]}


if __name__ == "__main__":
    p = plan("London Bridge LU", Date(2026, 10, 5))
    print(json.dumps({k: p[k] for k in ("layout", "layout_gain", "capacity", "visits", "period", "thin_hours")}, indent=1))
