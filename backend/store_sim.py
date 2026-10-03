"""Store simulation: at which hour, at this store, which persona buys what.

    units(category, hour, persona) = baskets a day at this store            assumed by size band until sales arrive
                                   x share of trips by this persona         how common the persona is x its trips per day (day of week)
                                   x share of that persona's trips in hour  by persona, day type, store size
                                   x calendar uplift                        the three days before a bank holiday
                                   x P(trip contains group | persona, hour, day type, pre-holiday, store size)   in-context tabular model
                                   x lines per trip in that group x category split within the group
                                   x UK level x neighbourhood taste         Tesco Grocery 1.0: London against the US panel, and this store's MSOA against London
                                   x calibration                            learned from scored decisions at this store
"""
from datetime import date as Date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import retail, sortofreal, stores, survey_personas, uk_personas
from .config import moment
from .data import bank_holidays, day_info, weather

EVIDENCE = [
    {"name": "dunnhumby The Complete Journey (2017): 2,469 households, 457 stores, every line item with a timestamp", "licence": "dunnhumby source files, free for research; not redistributed here", "role": "when people shop, trip size, calendar effects"},
    {"name": "Geolytix Retail Points v46 (June 2026)", "licence": "Geolytix open data licence", "role": "store, retailer, format, location"},
    {"name": "Tesco Grocery 1.0 (2015 Clubcard purchases by London MSOA)", "licence": "CC BY 4.0", "role": "UK category levels and each neighbourhood's taste"},
    {"name": "London MSOA Atlas (2011 Census and related)", "licence": "OGL v3", "role": "who lives around each store; neighbourhood types"},
    {"name": "FSA Food and You 2, Wave 11 (5,898 UK adults, 2025)", "licence": "OGL v3", "role": "how common each persona is in this kind of neighbourhood; UK measures for five personas till data cannot see"},
    {"name": "dunnhumby Let's Get Sort-of-Real, 50,000-customer sample (SYNTHETIC)", "licence": "dunnhumby source files; terms not read", "role": "which personas favour which store format"},
    {"name": "ONS MSOA population-weighted centroids", "licence": "OGL v3", "role": "distances for the store catchment model"},
    {"name": "gov.uk bank holidays", "licence": "OGL v3", "role": "calendar"},
]


def _daypart(h: int) -> str:
    return "morning" if h < 11 else "lunch" if h < 14 else "afternoon" if h < 17 else "evening"


def uk_calendar(d: Date) -> dict:
    info = day_info(d)
    ahead = [bank_holidays().get((d + timedelta(days=k)).isoformat()) for k in (1, 2, 3)]
    info["pre_holiday"] = int(any(ahead))
    info["upcoming_holiday"] = next((a for a in ahead if a), None)
    info["py_dow"] = d.weekday()
    return info


@lru_cache(maxsize=4)
def _tables(big: int) -> dict:
    """Everything that does not depend on the date or the place, for one trip mission."""
    R = retail.load()
    P = R["personas"]
    P = P[P.measured].set_index("persona")
    life = pd.Series(P.index, index=P.index)                              # behaviour tables are keyed by persona
    trips = R["trips"].pivot(index="persona", columns="dow", values="trips_per_day").reindex(P.index)
    pbig = R["bigshare"].set_index("persona").p_big.reindex(P.index)
    size_share = pbig if big else 1 - pbig                               # share of the persona's trips that are stock-up (big) or top-up
    hrs = R["hours"][R["hours"].big_store == big]
    hour_share = {(l, w): g.set_index("hour").share.reindex(retail.HOURS).fillna(0).values for (l, w), g in hrs.groupby(["life", "weekend"])}
    pick = R["pick"][R["pick"].big_store == big]
    pick = {(w, ph): g.pivot_table(index=["persona", "hour"], columns="group", values="p") for (w, ph), g in pick.groupby(["weekend", "pre_holiday"])}
    depth = R["depth"][R["depth"].big_store == big].pivot(index="life", columns="group", values="lines")
    within = {(l, dp): g.set_index("category").share for (l, dp), g in R["within"].groupby(["life", "daypart"])}
    return {"P": P, "life": life, "trips": trips, "size_share": size_share, "hour_share": hour_share, "pick": pick, "depth": depth, "within": within, "meta": R["meta"], "eval": R["eval"]}


def _weights(S: dict, T: dict) -> pd.Series:
    """How common each persona is among shoppers at this store: the panel's overall mix, tilted by how much more or less
    common the persona is among adults in this kind of neighbourhood (Food and You 2). Personas the survey does not
    measure keep their overall share."""
    w = T["P"].households.astype(float)
    tilt = survey_personas.tilt(S.get("catchment") or S.get("msoa"))
    w = w * pd.Series({p: tilt.get(p, 1.0) for p in w.index})
    # which personas favour this store format (synthetic Sort-of-Real data; ten personas measurable there)
    F = sortofreal.format_lift()
    if S.get("format") in F.columns:
        w = w * pd.Series({p: float(F.at[p, S["format"]]) if p in F.index else 1.0 for p in w.index})
    return w


def neighbourhood(S: dict, top: int = 3) -> list:
    """The store's location described on its own terms: the neighbourhood types around it (see uk_personas.py)."""
    W = uk_personas.area_weights()
    c = pd.Series(S.get("catchment") or {S.get("msoa"): 1.0}, dtype=float)
    c = c[c.index.isin(W.index)]
    if c.empty:
        return []
    N, mix = uk_personas.names(), W.loc[c.index].mul(c, axis=0).sum() / c.sum()
    return [{"type": k, "share": round(float(v), 3), "description": N[k]} for k, v in mix.sort_values(ascending=False).head(top).items()]


def visits(S: dict, T: dict, cal: dict, calendar: dict) -> pd.DataFrame:
    """Expected trips by persona (rows) and hour (columns) on this date."""
    w = _weights(S, T) * T["size_share"]
    day_rate = T["trips"].mul(w, axis=0)                                   # persona x dow
    k = S["assumed_baskets"] / day_rate.sum().mean()                       # so an average day has the assumed baskets
    we = calendar["weekend"]
    shape = np.vstack([T["hour_share"][(l, we)] for l in T["life"]])
    up = T["meta"]["calendar_uplift"]
    factor = (up["pre_holiday"] if calendar["pre_holiday"] else 1.0) * (up["holiday"] if calendar["holiday"] else 1.0) * cal.get("volume", 1.0)
    v = shape * (day_rate[calendar["py_dow"]].values * k * factor)[:, None]
    return pd.DataFrame(v, index=T["P"].index, columns=retail.HOURS)


def simulate(store_id: str, d: Date, service_level: float = 0.85, taste: dict | None = None) -> dict:
    """`taste` replaces the store's neighbourhood taste; the UK backtest uses it to hide held-out areas' real purchases."""
    from .simulate import calibration
    S = stores.get(store_id)
    if taste is not None:
        S["taste"] = taste
    T, cal, calendar = _tables(int(S["big_store"])), calibration(str(store_id)), uk_calendar(d)
    V = visits(S, T, cal, calendar)
    pick = T["pick"][(calendar["weekend"], calendar["pre_holiday"])]
    wx = weather()
    rows, hours = [], []
    for h in retail.HOURS:
        mom, dp = moment(h, bool(calendar["weekend"])), _daypart(h)
        km = cal["moment"].get(mom, 1.0)
        for p in V.index:
            v, l = V.loc[p, h], T["life"][p]
            if v <= 0:
                continue
            att, dep, win = pick.loc[(p, h)], T["depth"].loc[l], T["within"][(l, dp)]
            for c, share in win.items():
                g = retail.GROUP_OF[c]
                base = v * att[g] * dep[g] * share * S["taste"].get(c, 1.0)
                rows.append((h, mom, p, c, base, base * cal["category"].get(c, 1.0) * km))
        w_now = wx[(wx.time.dt.date == d) & (wx.time.dt.hour == h)]
        col = V[h]
        hours.append({"hour": h, "moment": mom, "people": round(float(col.sum())), "buyers": round(float(col.sum()), 1),
                      "persona_mix": {p: round(float(x), 4) for p, x in (col / max(col.sum(), 1e-9)).items()},
                      "weather": {"temp_c": float(w_now.temp.iloc[0]), "rain_mm": float(w_now.rain.iloc[0])} if len(w_now) else None})
    R = pd.DataFrame(rows, columns=["hour", "moment", "persona", "category", "base", "units"])
    for hrow in hours:
        hrow["units_served"] = round(float(R[R.hour == hrow["hour"]].units.sum()), 1)
        hrow["unserved_buyers"], hrow["evidence_items"] = 0.0, T["meta"]["trips"] // len(retail.HOURS)
    cells = []
    for (mom, c), g in R.groupby(["moment", "category"], sort=False):
        mu = float(g.units.sum())
        top = g.groupby("persona").units.sum().sort_values(ascending=False)
        cells.append({"moment": mom, "hours": sorted(g.hour.unique().tolist()), "item_id": c, "item": c, "category": c, "group": retail.GROUP_OF[c],
                      "units": round(mu, 1), "base_units": round(float(g.base.sum()), 2), "low": int(poisson.ppf(0.1, mu)), "high": int(poisson.ppf(0.9, mu)),
                      "order_qty": int(poisson.ppf(service_level, mu)), "top_persona": top.index[0], "top_persona_share": round(float(top.iloc[0] / max(mu, 1e-9)), 3),
                      "by_persona": {p: round(float(u), 2) for p, u in top.items()},
                      "by_hour": {int(h): round(float(u), 1) for h, u in g.groupby("hour").units.sum().items()}})
    return {"station": S["store_name"], "location": {k: S[k] for k in ("id", "retailer", "fascia", "store_name", "postcode", "borough", "format", "msoa", "assumed_baskets", "older_index", "family_index")},
            "day": calendar, "footfall_basis": f"{S['assumed_baskets']} baskets a day for this {S['format']}, {S.get('baskets_basis', 'assumed')} (no sales loaded for this store)", "profile": S["format"], "mission": "stock-up trips (more than five lines)" if S["big_store"] else "top-up trips (five lines or fewer)",
            "calibration": cal, "service_level": service_level, "hours": hours, "cells": cells, "trips_by_persona_hour": {p: {int(h): round(float(x), 2) for h, x in V.loc[p].items()} for p in V.index},
            "neighbourhood": neighbourhood(S), "local_personas": survey_personas.local(S.get("catchment") or S.get("msoa")), "catchment": S.get("catchment"), "model": T["meta"], "pick_eval": T["eval"], "evidence": EVIDENCE,
            "caveats": ["Timing, personas and calendar effects are learned from US households in 2017. Category levels are moved to London Tesco levels (2015), and the neighbourhood taste and age structure are UK data.",
                        f"Baskets per day ({S['assumed_baskets']}) comes from a gravity model of resident demand; commuters and visitors are not in it, and the level rests on an assumed 0.19 trips per resident per day.",
                        "Convenience and small formats are modelled with top-up trips (five lines or fewer), larger formats with stock-up trips; the panel has too few small-store trips to model format directly.",
                        "Personas are kinds of shopper measured from till behaviour in the US panel (15 of the team's 28 can be measured). Location is applied separately: store format sets the trip mission, and the neighbourhood's real Tesco purchases set the local taste.",
                        "Ranges are Poisson 10-90% around the expected units."]}


def persona_view(persona: str, store_id: str, d: Date) -> dict:
    """One persona at one store on one date: when they come and what they buy."""
    sim = simulate(store_id, d)
    trips = sim["trips_by_persona_hour"][persona]
    total = sum(trips.values())
    what = sorted(((c["category"], c["moment"], c["by_persona"].get(persona, 0.0)) for c in sim["cells"]), key=lambda x: -x[2])
    by_cat = pd.DataFrame(what, columns=["category", "moment", "units"])
    return {"persona": persona, "rule": retail.personas()[persona], "store": sim["location"], "day": sim["day"], "trips": round(total, 1),
            "share_of_store_trips": round(total / max(sum(h["buyers"] for h in sim["hours"]), 1e-9), 4),
            "peak_hour": max(trips, key=trips.get), "trips_by_hour": trips,
            "top_categories": by_cat.groupby("category").units.sum().sort_values(ascending=False).head(10).round(1).to_dict(),
            "by_moment": {m: g.sort_values("units", ascending=False).head(3)[["category", "units"]].round(1).to_dict("records") for m, g in by_cat.groupby("moment", sort=False)}}


def where(persona: str, d: Date, borough: str = "", limit: int = 15) -> list:
    """Which stores this persona shops at on this date, ranked by expected trips, with the hour they are most likely there."""
    from .simulate import calibration
    t, calendar, out = stores.table(), uk_calendar(d), []
    if borough:
        t = t[t.borough.fillna("").str.contains(borough, case=False)]
    for sid in t.id:
        S = stores.get(sid)
        V = visits(S, _tables(int(S["big_store"])), calibration(str(sid)), calendar).loc[persona]
        out.append({"id": sid, "store_name": S["store_name"], "fascia": S["fascia"], "format": S["format"], "borough": S["borough"],
                    "trips": round(float(V.sum()), 1), "peak_hour": int(V.idxmax())})
    return sorted(out, key=lambda x: -x["trips"])[:limit]


# ------------------------------------------------------------------ the product's main question
CATALOGUE_TO_CATEGORY = {"protein & cereal bar": "breakfast foods", "protein & nutrition shake": "milk", "coffee": "coffee", "crisps & salty snacks": "crisps & savoury snacks",
                         "yogurt": "yogurt", "tea": "tea", "cake, cookie & pastry": "sweet bakery", "soft drink": "soft drinks", "energy & sports drink": "sports & energy drinks",
                         "juice & fruit drink": "juice", "salad & veg": "salad", "water": "water", "sandwich & wrap": "food to go & deli", "confectionery": "confectionery"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def recommend(store_id: str, weekday: int, hour: int, weeks: int = 12, start: Date | None = None, top: int = 8, service_level: float = 0.85) -> dict:
    """The user picks a day of the week and an hour; this says what kind of product to stock at this store in that slot
    for each of the next `weeks` weeks, how much, for which shoppers, and which weeks differ because of the calendar."""
    from . import catalogue
    start = start or Date.today()
    first = start + timedelta(days=(weekday - start.weekday()) % 7)
    products = {}
    for it in catalogue.load():
        products.setdefault(CATALOGUE_TO_CATEGORY.get(it["category"]), []).append({"name": it["name"], "brand": it["brand"]})
    rows, weeks_out, loc = [], [], None
    for k in range(weeks):
        d = first + timedelta(days=7 * k)
        sim = simulate(store_id, d, service_level)
        loc = sim
        hr = next(h for h in sim["hours"] if h["hour"] == hour)
        day_total = sum(c["units"] for c in sim["cells"])
        slot_total = sum(c["by_hour"].get(hour, 0.0) for c in sim["cells"])
        closed = d.month == 12 and d.day == 25                                   # UK supermarkets do not open on Christmas Day
        if closed:
            weeks_out.append({"week": k + 1, "date": d.isoformat(), "trips": 0, "units": 0.0, "calendar": "closed: Christmas Day", "weather": None})
            continue
        for c in sim["cells"]:
            if hour not in c["hours"]:
                continue
            u = c["by_hour"].get(hour, 0.0)
            day_cat = sum(x["units"] for x in sim["cells"] if x["category"] == c["category"])
            rows.append({"week": k + 1, "date": d.isoformat(), "category": c["category"], "group": c["group"], "units": u,
                         "index": (u / max(slot_total, 1e-9)) / max(day_cat / max(day_total, 1e-9), 1e-9), "top_persona": c["top_persona"],
                         "persona_share": c["top_persona_share"]})
        weeks_out.append({"week": k + 1, "date": d.isoformat(), "trips": hr["people"], "units": round(slot_total, 1),
                          "calendar": "bank holiday" if sim["day"]["holiday"] else f"run-up to {sim['day']['upcoming_holiday']}" if sim["day"]["pre_holiday"] else None,
                          "weather": hr["weather"]})
    R = pd.DataFrame(rows)
    g = R.groupby("category").agg(group=("group", "first"), mean_units=("units", "mean"), low_week=("units", "min"), high_week=("units", "max"),
                                  index=("index", "mean"), top_persona=("top_persona", lambda s: s.mode().iloc[0]), persona_share=("persona_share", "mean")).reset_index()
    g["stock_per_week"] = [int(poisson.ppf(service_level, m)) if m > 0 else 0 for m in g.mean_units]
    g["range"] = [[int(poisson.ppf(0.1, m)), int(poisson.ppf(0.9, m))] if m > 0 else [0, 0] for m in g.mean_units]
    g["products"] = g.category.map(lambda c: products.get(c, []))
    fmt = lambda t: [{"category": r.category, "group": r.group, "units_per_week": round(r.mean_units, 1), "range": r.range, "stock": r.stock_per_week,
                      "times_usual_share": round(r["index"], 2), "bought_most_by": r.top_persona, "that_persona_share": round(r.persona_share, 2),
                      "lowest_week": round(r.low_week, 1), "highest_week": round(r.high_week, 1), "example_products": r.products} for _, r in t.iterrows()]
    named = g[g.category != "store cupboard"]
    base = float(np.median([w["units"] for w in weeks_out if w["units"] > 0]))
    for w in weeks_out:
        w["vs_typical_week"] = round(w["units"] / max(base, 1e-9), 2)
    mom = moment(hour, weekday >= 4)
    return {"store": loc["location"], "slot": {"weekday": WEEKDAYS[weekday], "hour": f"{hour:02d}:00-{hour + 1:02d}:00", "moment": mom}, "weeks": weeks, "from": first.isoformat(),
            "stock_most": fmt(named.sort_values("mean_units", ascending=False).head(top)),
            "sells_unusually_well_in_this_slot": fmt(named[named.mean_units >= 1].sort_values("index", ascending=False).head(top)),
            "shoppers_in_this_slot": dict(sorted(next(h for h in loc["hours"] if h["hour"] == hour)["persona_mix"].items(), key=lambda x: -x[1])[:5]),
            "week_by_week": weeks_out, "weeks_that_differ": [w for w in weeks_out if w["calendar"]],
            "note_on_weeks": "The model has no seasonal trend: an ordinary week gets the same forecast, and only bank holidays, the three days before them and Christmas Day closure change it.",
            "neighbourhood": loc["neighbourhood"], "local_personas": loc["local_personas"],
            "basis": {"horizon": "tested twelve weeks ahead without updates on the household panel: daily error 26% of units, matching a 4-week mean refreshed weekly",
                      "what": "UK basket validated against Tesco purchases in held-out neighbourhoods (0.97)", "when_and_who": "validated on US households only (0.99 by hour, 0.94 by persona, time and category)",
                      "volume": loc["footfall_basis"]},
            "caveats": loc["caveats"], "evidence": loc["evidence"]}
