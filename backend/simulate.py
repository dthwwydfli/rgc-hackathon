"""The simulation: what will be bought, by which persona, at which hour, at a location.

    units(item, hour, persona) = people(station, hour)            TfL
                               x capture x propensity(hour)        share who buy food to go in that hour
                               x mix(persona | hour)               who those buyers are
                               x P(category | persona, moment)     in-context tabular model
                               x share(item | category, persona)   attribute fit (caffeine, protein, sugar)
                               x calibration(category, moment)     learned from scored decisions
"""
import json
from datetime import date as Date

import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import catalogue, picks
from .config import DATA, EVIDENCE, HOURS, PERSONAS, moment
from .data import day_info, footfall, weather

CALIBRATION = DATA / "calibration.json"
DEFAULT_CAPTURE = 0.02   # share of people leaving the station who buy from this shelf in an average hour; an assumption until sales exist


def calibration(location: str) -> dict:
    c = json.loads(CALIBRATION.read_text()) if CALIBRATION.exists() else {}
    return {"capture": DEFAULT_CAPTURE, "category": {}, "moment": {}, **c.get(location, {})}


def save_calibration(location: str, cal: dict):
    c = json.loads(CALIBRATION.read_text()) if CALIBRATION.exists() else {}
    c[location] = cal
    CALIBRATION.write_text(json.dumps(c, indent=1))


def pick_table(weekend: int) -> pd.DataFrame:
    """persona x hour x category probabilities for one day type."""
    g = picks.load()["pick"]
    return g[g.weekend == weekend]


def simulate_station(station: str, d: Date, items: list | None = None, service_level: float = 0.85) -> dict:
    G = picks.load()
    items = items or catalogue.load()
    info, cal = day_info(d), calibration(station)
    we = info["weekend"]
    ff = footfall(station, d).set_index("hour")
    prop = G["prop"][G["prop"].weekend == we].set_index("hour").per_adult_day.reindex(HOURS).fillna(0)
    prop = prop / prop.mean()
    mix = G["mix"][G["mix"].weekend == we].pivot(index="hour", columns="persona", values="share").reindex(HOURS).fillna(1 / len(PERSONAS))
    pick = G["pick"][G["pick"].weekend == we].pivot_table(index=["hour", "persona"], columns="category", values="p").fillna(0)
    attr = G["attr"][G["attr"].weekend == we].set_index(["hour", "persona"])
    sup = G["support"][G["support"].weekend == we].groupby("hour").n_items.sum()
    wx = weather()
    by_cat = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)

    rows, hours = [], []
    for h in HOURS:
        people = float(ff.people.get(h, 0))
        buyers = people * cal["capture"] * prop[h]
        mom = moment(h, bool(we))
        k_m = cal["moment"].get(mom, 1.0)
        served = 0.0
        for p in PERSONAS:
            b = buyers * mix.loc[h, p]
            for cat, its in by_cat.items():
                pc = float(pick.loc[(h, p)].get(cat, 0)) if (h, p) in pick.index else 0.0
                a = attr.loc[(h, p)] if (h, p) in attr.index else None
                w = np.array([np.prod([(a[k] if it[k] else 1 - a[k]) for k in picks.ATTRS]) if a is not None else 1.0 for it in its])
                w = w / w.sum() if w.sum() > 0 else np.ones(len(its)) / len(its)
                for it, share in zip(its, w):
                    base = b * pc * share                                   # before anything learned from this location's sales
                    u = base * cal["category"].get(cat, 1.0) * k_m
                    served += u
                    rows.append({"hour": h, "moment": mom, "persona": p, "item_id": it["id"], "item": it["name"], "category": cat, "units": u, "base": base})
        w_now = wx[(wx.time.dt.date == d) & (wx.time.dt.hour == h)]
        hours.append({"hour": h, "moment": mom, "people": round(people), "buyers": round(buyers, 1), "units_served": round(served, 1),
                      "unserved_buyers": round(max(buyers * k_m - served, 0), 1),   # wanted a category the shelf does not stock
                      "persona_mix": {p: round(float(mix.loc[h, p]), 3) for p in PERSONAS},
                      "evidence_items": int(sup.get(h, 0)),
                      "weather": {"temp_c": float(w_now.temp.iloc[0]), "rain_mm": float(w_now.rain.iloc[0])} if len(w_now) else None})
    R = pd.DataFrame(rows)
    cells = []
    for (mom, iid), g in R.groupby(["moment", "item_id"], sort=False):
        mu = float(g.units.sum())
        cells.append({"moment": mom, "hours": sorted(g.hour.unique().tolist()), "item_id": iid, "item": g.item.iloc[0], "category": g.category.iloc[0],
                      "units": round(mu, 1), "base_units": round(float(g.base.sum()), 2), "low": int(poisson.ppf(0.1, mu)) if mu > 0 else 0, "high": int(poisson.ppf(0.9, mu)) if mu > 0 else 0,
                      "order_qty": int(poisson.ppf(service_level, mu)) if mu > 0 else 0,
                      "by_persona": {p: round(float(u), 1) for p, u in g.groupby("persona").units.sum().items()},
                      "by_hour": {int(h): round(float(u), 1) for h, u in g.groupby("hour").units.sum().items()}})
    return {"station": station, "day": info, "footfall_basis": ff.basis.iloc[0], "profile": ff.profile.iloc[0],
            "calibration": cal, "service_level": service_level, "hours": hours, "cells": cells,
            "model": G["meta"], "pick_eval": G["eval"],
            "evidence": [EVIDENCE[k] for k in ("nhanes", "tfl", "off", "holidays")],
            "caveats": ["Pick probabilities come from US adults (NHANES); UK transfer is checked only on bakery sales shape.",
                        f"Capture rate {cal['capture']:.3f} is an assumption until this location has scored sales.",
                        "Ranges are Poisson 10-90% around the expected units; model uncertainty is not included."]}


def simulate(location: str, d: Date, items: list | None = None, service_level: float = 0.85) -> dict:
    """A location is a store id from the store table (the default) or, for a kiosk at a station, a TfL station name."""
    from . import store_sim, stores
    if str(location) in set(stores.table().id):
        return store_sim.simulate(str(location), d, service_level=service_level)
    return simulate_station(location, d, items, service_level)
