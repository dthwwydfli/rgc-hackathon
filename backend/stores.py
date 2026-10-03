"""Locations are stores. Any UK supermarket or convenience store from Geolytix Retail Points (open data, June 2026),
joined to the Tesco Grocery 1.0 purchase profile of the neighbourhood it stands in (London MSOAs, Clubcard data, CC BY 4.0).

A store brings three things to the simulation:
    format      size band -> small or big store behaviour, and an assumed number of baskets a day
    taste       how the area's Tesco purchases differ from the London average, per category
    people      the area's age structure, which shifts the persona mix
Build: python -m backend.stores      (postcode -> MSOA through postcodes.io, about 20 requests)
"""
import json
import time
import urllib.request
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import CACHE, DATA

SIZE = {"< 3,013 ft2 (280m2)": ("convenience", 0, 1200), "3,013 < 15,069 ft2 (280 < 1,400 m2)": ("small supermarket", 0, 3000),
        "15,069 < 30,138 ft2 (1,400 < 2,800 m2)": ("supermarket", 1, 6000), "30,138 ft2 > (2,800 m2)": ("superstore", 1, 10000)}
#        size band -> (format, behaves like a big store, ASSUMED baskets per day until the store has scored sales)

TESCO_OF = {"beer & cider": "beer", "wine": "wine", "spirits": "spirits", "water": "water", "soft drinks": "soft_drinks",
            "sports & energy drinks": "soft_drinks", "juice": "soft_drinks", "coffee": "tea_coffee", "tea": "tea_coffee",
            "cereal": "grains", "bread": "grains", "breakfast foods": "grains", "confectionery": "sweets", "biscuits & crackers": "sweets",
            "ice cream": "sweets", "sweet bakery": "sweets", "pizza": "readymade", "soup": "readymade", "ready meals": "readymade",
            "food to go & deli": "readymade", "yogurt": "dairy", "cheese": "dairy", "milk": "dairy", "eggs": "eggs",
            "butter & spreads": "fats_oils", "fish": "fish", "poultry": "poultry", "fresh meat": "meat_red",
            "bacon, sausage & cooked meats": "meat_red", "salad": "fruit_veg", "fruit": "fruit_veg", "vegetables": "fruit_veg",
            "store cupboard": "sauces"}


def _lookup(postcodes: list) -> dict:
    out = {}
    for i in range(0, len(postcodes), 100):
        req = urllib.request.Request("https://api.postcodes.io/postcodes", data=json.dumps({"postcodes": postcodes[i:i + 100]}).encode(),
                                     headers={"Content-Type": "application/json"})
        for r in json.load(urllib.request.urlopen(req, timeout=40))["result"]:
            x = r["result"] or {}
            out[r["query"]] = (x.get("codes", {}).get("msoa"), x.get("admin_district"))
        time.sleep(0.3)
    return out


def build():
    g = pd.read_csv(DATA / "stores" / "geolytix" / "geolytix_retailpoints_v46_202606.csv", low_memory=False)
    g = g[g.county == "Greater London"].copy()
    look = _lookup(sorted(g.postcode.dropna().unique()))
    g["msoa"] = g.postcode.map(lambda p: look.get(p, (None, None))[0])
    g["borough"] = g.postcode.map(lambda p: look.get(p, (None, None))[1])
    t = pd.read_csv(DATA / "tesco" / "year_msoa_grocery.csv")
    g["msoa_source"] = np.where(g.msoa.isin(t.area_id), "postcode", "nearest matched store")
    ok = g[g.msoa.isin(t.area_id)]
    for i in g.index[~g.msoa.isin(t.area_id)]:          # new or retired postcodes: take the neighbourhood of the closest matched store
        j = ((ok.lat_wgs - g.at[i, "lat_wgs"]) ** 2 + ((ok.long_wgs - g.at[i, "long_wgs"]) * 0.62) ** 2).idxmin()
        g.at[i, "msoa"], g.at[i, "borough"] = ok.at[j, "msoa"], ok.at[j, "borough"]
    cats = sorted(set(TESCO_OF.values()))
    idx = t[["area_id"]].copy()
    for c in cats:
        idx[f"taste_{c}"] = (t[f"f_{c}"] / t[f"f_{c}"].mean()).round(3)
    idx["share_65"] = t["age_65+"] / t.population
    idx["share_kids"] = t["age_0_17"] / t.population
    idx["older_index"] = (idx.share_65 / idx.share_65.mean()).round(3)
    idx["family_index"] = (idx.share_kids / idx.share_kids.mean()).round(3)
    idx["tesco_transactions"], idx["population"] = t.num_transactions, t.population
    idx["sugar_energy_share"], idx["energy_density"] = t.f_energy_sugar.round(4), t.energy_density.round(4)
    s = g.merge(idx, left_on="msoa", right_on="area_id", how="left").drop(columns=["area_id"])
    s[["format", "big_store", "assumed_baskets"]] = [SIZE.get(b, ("convenience", 0, 1200)) for b in s.size_band]
    s["id"] = s["id"].astype(str)
    s.to_parquet(CACHE / "stores.parquet")
    print(len(s), "London stores;", int(s.taste_dairy.notna().sum()), "matched to a Tesco MSOA profile")


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "stores.parquet")


@lru_cache(maxsize=1)
def uk_level() -> dict:
    """How much more or less of each category a London Tesco basket holds than the US panel's basket (Tesco share / panel share).
    The panel supplies timing, personas and calendar; this moves its category levels to UK ones. Clipped to 0.3-3.5.
    Store cupboard and crisps have no clean Tesco counterpart and stay at 1."""
    from . import retail
    L = retail.lines()
    L = L[L.category.isin(TESCO_OF) & (L.category != "store cupboard")]
    us = L.category.map(TESCO_OF).value_counts(normalize=True)
    t = pd.read_csv(DATA / "tesco" / "year_msoa_grocery.csv")
    uk = t[[f"f_{c}" for c in us.index]].mean()
    uk.index = us.index
    ratio = ((uk / uk.sum()) / us).clip(0.3, 3.5)
    f = CACHE / "uk_level_calibration.json"      # written by uk_backtest: brings the engine's own average basket onto the real one
    cal = json.loads(f.read_text()) if f.exists() else {}
    return {c: round(float(ratio[k] * cal.get(k, 1.0)), 3) for c, k in TESCO_OF.items() if c != "store cupboard"}


def get(store_id: str) -> dict:
    t = table()
    r = t[t.id == str(store_id)]
    if r.empty:
        raise KeyError(store_id)
    r = r.iloc[0].replace({np.nan: None}).to_dict()
    lvl = uk_level()
    r["uk_level"] = lvl
    from . import catchment
    try:                                         # the store draws from several neighbourhoods (gravity model), not only the one it stands in
        r["catchment"] = catchment.of(r["id"])
        C = catchment.table().loc[r["id"]]
        r["assumed_baskets"], r["baskets_basis"] = int(max(C.baskets_per_day, 1)), "gravity model: this store's share of resident demand within 3 km"
        area = t.drop_duplicates("msoa").set_index("msoa")
        w = pd.Series(r["catchment"])
        w = w[w.index.isin(area.index)]
        mix = lambda col: float((area.loc[w.index, col].fillna(1.0) * w).sum() / w.sum()) if len(w) else 1.0
        r["taste"] = {c: mix(f"taste_{k}") * lvl.get(c, 1.0) for c, k in TESCO_OF.items()}          # catchment against London x London against the US panel
    except (KeyError, FileNotFoundError):
        r["catchment"], r["baskets_basis"] = ({r["msoa"]: 1.0} if r.get("msoa") else {}), "assumed for the size band"
        r["taste"] = {c: (r.get(f"taste_{k}") or 1.0) * lvl.get(c, 1.0) for c, k in TESCO_OF.items()}
    return r


def search(q: str = "", retailer: str = "", borough: str = "", limit: int = 50) -> list:
    t = table()
    m = t.store_name.str.contains(q, case=False, na=False) if q else pd.Series(True, index=t.index)
    if retailer:
        m &= t.retailer.str.contains(retailer, case=False, na=False)
    if borough:
        m &= t.borough.fillna("").str.contains(borough, case=False)
    cols = ["id", "retailer", "fascia", "store_name", "postcode", "borough", "format", "lat_wgs", "long_wgs", "msoa"]
    return t[m][cols].head(limit).replace({np.nan: None}).to_dict("records")


if __name__ == "__main__":
    build()
