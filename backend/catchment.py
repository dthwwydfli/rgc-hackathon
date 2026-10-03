"""Store catchments by a Huff gravity model: which neighbourhoods a store draws from, and how much.

    P(resident of area i shops at store j) = A_j / d_ij^BETA  over the same for every store within reach
    A_j = floor space of the store's size band

It replaces two shortcuts: a store's shoppers are no longer assumed to come only from the one neighbourhood it stands in,
and its baskets per day are no longer a fixed number per size band but its share of the demand around it.
Residents only: commuters and visitors are still not in it.

Check against real data: the share of each area's demand the model sends to Tesco stores, against Tesco's actual Clubcard
penetration in that area (Tesco Grocery 1.0).  Run: python -m backend.catchment
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import CACHE, DATA

BETA, MAX_KM, MIN_KM = 2.0, 3.0, 0.15            # distance decay; reach (best of 1-3 and 3/5/8 km on the Tesco check); floor on distance
FLOOR = {"convenience": 2000, "small supermarket": 9000, "supermarket": 22000, "superstore": 40000}   # sq ft, mid-point of the Geolytix size band
TRIPS_PER_PERSON_DAY = 0.19                    # grocery trips per resident per day (panel: 1.3 trips a week per household of 2.4, and not all grocers are in the store list)


@lru_cache(maxsize=1)
def model() -> dict:
    from . import stores
    S = stores.table().reset_index(drop=True)
    A = pd.read_csv(DATA / "london" / "msoa_centroids.csv")
    lat0 = np.radians(51.5)
    dx = (S.long_wgs.values[None, :] - A.lon.values[:, None]) * 111.32 * np.cos(lat0)
    dy = (S.lat_wgs.values[None, :] - A.lat.values[:, None]) * 110.57
    d = np.clip(np.sqrt(dx ** 2 + dy ** 2), MIN_KM, None)                 # areas x stores, km
    attract = S.format.map(FLOOR).fillna(2000).values
    U = np.where(d <= MAX_KM, attract[None, :] / d ** BETA, 0.0)
    P = U / U.sum(1, keepdims=True)                                       # each area's trips split across stores
    flow = P * A.population.values[:, None]                               # residents-equivalent
    return {"stores": S, "areas": A, "P": P, "flow": flow}


def build() -> dict:
    M = model()
    S, A, P, flow = M["stores"], M["areas"], M["P"], M["flow"]
    demand = flow.sum(0)
    out = S[["id", "store_name", "retailer", "format"]].copy()
    out["catchment_residents"] = demand.round(0)
    out["baskets_per_day"] = (demand * TRIPS_PER_PERSON_DAY).round(0)
    top = np.argsort(-flow, axis=0)[:8]                                    # the eight areas each store draws most from
    out["catchment"] = [json.dumps({A.area_id[i]: round(float(flow[i, j] / demand[j]), 4) for i in top[:, j] if flow[i, j] > 0}) for j in range(len(S))]
    out["catchment_top8_share"] = [round(float(flow[top[:, j], j].sum() / demand[j]), 3) for j in range(len(S))]
    out["own_area_share"] = [round(float(flow[A.index[A.area_id == m][0], j] / demand[j]), 3) if (A.area_id == m).any() else None for j, m in enumerate(S.msoa)]
    out.to_parquet(CACHE / "catchments.parquet")
    tesco = (S.retailer == "Tesco").values
    pred = P[:, tesco].sum(1)
    r = spearmanr(pred, A.representativeness_norm)[0]
    ev = {"stores": len(S), "areas": len(A), "beta": BETA, "max_km": MAX_KM,
          "check": "share of each area's trips the model sends to Tesco stores vs Tesco's real Clubcard penetration there",
          "spearman_r": round(float(r), 3),
          "baskets_per_day_by_format": out.groupby("format").baskets_per_day.describe()[["25%", "50%", "75%"]].round(0).to_dict("index"),
          "median_share_of_shoppers_from_own_area": float(out.own_area_share.median())}
    (CACHE / "catchment_eval.json").write_text(json.dumps(ev, indent=1))
    return ev


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "catchments.parquet").set_index("id")


def of(store_id: str) -> dict:
    """{area: share of this store's resident shoppers} for its main catchment areas, renormalised to 1."""
    c = json.loads(table().at[str(store_id), "catchment"])
    t = sum(c.values())
    return {k: v / t for k, v in c.items()}


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
