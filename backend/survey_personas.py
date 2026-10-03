"""UK persona prevalence by kind of place, from the FSA's Food and You 2 survey (Wave 11, 5,898 adults, OGL v3).

Two jobs:
  1. Five of the team's personas that till data cannot see become measurable in the UK (online, app, trust, local).
  2. For seven personas that both sources measure, how much more or less common each is in a neighbourhood like this one.
     That tilts the persona mix at each store, so location changes who is in the shop.

A respondent is "in" a persona when they give the stated answer; the in-context tabular model then predicts that answer
from age band, deprivation quintile, urban/rural and region.  Run: python -m backend.survey_personas   (build + held-out check)
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import CACHE, DATA

FEATS = ["ageband_dv_w7", "imd", "urban", "Region_dv"]
#            persona                        measured in till data too?   how the survey sees it
MEASURES = {
    "The Bargain Hunter":           (True,  "price or value for money is most important when choosing food", lambda d: d.defra1_1_w9 == 1, lambda d: d.defra1_1_w9 >= 0),
    "The Value Optimizer":          (True,  "quality is most important", lambda d: d.defra1_2_w9 == 1, lambda d: d.defra1_2_w9 >= 0),
    "The Ethical Consumer":         (True,  "ethics, eco-friendliness or farming methods are most important", lambda d: (d.defra1_26_w9 == 1) | (d.defra1_27_w9 == 1) | (d.defra1_11_w9 == 1), lambda d: d.defra1_26_w9 >= 0),
    "The Impulse Buyer":            (True,  "bought on impulse because of a promotion in the last two weeks", lambda d: d.promowhy2 == 1, lambda d: d.promowhy2 >= 0),
    "The Methodical Perfectionist": (True,  "checks ingredients and nutrition information always or most of the time", lambda d: d.foodchk1_c.between(1, 2) & d.foodchk2_a.between(1, 2), lambda d: d.foodchk1_c.between(1, 5)),
    "The Humanistic Connector":     (True,  "trust in the supplier is most important", lambda d: d.defra1_15_w9 == 1, lambda d: d.defra1_15_w9 >= 0),
    "The Decisive Alpha":           (True,  "convenience is most important", lambda d: d.defra1_17_w9 == 1, lambda d: d.defra1_17_w9 >= 0),
    "The Digital-First Shopper":    (False, "has ordered food through a delivery app", lambda d: d.shophave_b == 1, lambda d: d.shophave_b >= 0),
    "The Tech Innovator":           (False, "has used a food-sharing app such as Too Good To Go", lambda d: d.shophave_e == 1, lambda d: d.shophave_e >= 0),
    "The Trend Follower":           (False, "has ordered food through social media", lambda d: d.shophave_d == 1, lambda d: d.shophave_d >= 0),
    "The Skeptical Critic":         (False, "not confident in the food supply chain", lambda d: d.foodsupply.isin([3, 4]), lambda d: d.foodsupply.between(1, 4)),
    "The Community Advocate":       (False, "started buying locally produced food in the last year", lambda d: d.dietenvi6 == 1, lambda d: d.dietenvi6 >= 0),
}
AGE_OF = {"age 16-29": [1, 2], "age 30-44": [2, 3], "age 45-64": [4, 5], "age 65+": [6, 7]}     # Atlas band -> survey bands (25-34 split across two)
MIN_AUC = 0.55                                                                                # below this, place and age do not predict the persona


@lru_cache(maxsize=1)
def survey() -> pd.DataFrame:
    d = pd.read_csv(DATA / "fy2" / "fy2_w11_abridged.csv", low_memory=False, encoding="utf-8-sig")
    return d[(d.ageband_dv_w7 >= 1) & (d.imd >= 1) & (d.urban >= 1)].reset_index(drop=True)


def _xy(name: str) -> tuple:
    d = survey()
    _, _, hit, asked = MEASURES[name]
    m = asked(d)
    return d.loc[m, FEATS].astype(float), hit(d)[m].astype(int)


def evaluate(seed: int = 0) -> dict:
    """Does the kind of place and age predict the persona? Held-out respondents; AUC, 0.5 is chance."""
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split
    from . import tabular
    out = {}
    for name in MEASURES:
        X, y = _xy(name)
        Xa, Xb, ya, yb = train_test_split(X, y, test_size=0.3, random_state=seed, stratify=y)
        Xa, ya = Xa.iloc[:3000], ya.iloc[:3000]
        m = tabular.classifier().fit(Xa, ya)
        out[name] = {"asked": len(y), "uk_share": round(float(y.mean()), 3), "auc": round(float(roc_auc_score(yb, m.predict_proba(Xb)[:, list(m.classes_).index(1)])), 3)}
    return out


def build():
    """Predicted share for every age band x deprivation quintile, urban, London; then per London neighbourhood."""
    from . import tabular, uk_personas
    d = survey()
    london = int(d.groupby("Region_dv").urban.apply(lambda s: (s == 1).mean()).idxmax())          # the all-urban region is London
    grid = pd.MultiIndex.from_product([range(1, 8), range(1, 6)], names=["ageband_dv_w7", "imd"]).to_frame(index=False)
    grid["urban"], grid["Region_dv"] = 1, london
    for name in MEASURES:
        X, y = _xy(name)
        ctx = X.sample(min(4000, len(X)), random_state=0)
        m = tabular.classifier().fit(ctx, y.loc[ctx.index])
        grid[name] = m.predict_proba(grid[FEATS].astype(float))[:, list(m.classes_).index(1)]
    A = uk_personas.areas()
    dep = pd.qcut(A["income deprived"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)   # 1 = most deprived, within London
    ages = A[list(AGE_OF)].div(A[list(AGE_OF)].sum(1), axis=0)
    rows = []
    for area in A.index:
        g = grid[grid.imd == dep[area]].set_index("ageband_dv_w7")
        w = pd.Series(0.0, index=g.index)
        for band, codes in AGE_OF.items():
            for c in codes:
                w[c] += ages.at[area, band] / len(codes)
        rows.append({"area_id": area, "deprivation_quintile": int(dep[area]), **{n: float((g[n] * w).sum() / w.sum()) for n in MEASURES}})
    P = pd.DataFrame(rows)
    P.to_parquet(CACHE / "survey_area_prevalence.parquet")
    ev = evaluate()
    uk = {n: ev[n]["uk_share"] for n in MEASURES}
    meta = {"uk_share": uk, "london_region_code": london, "eval": ev, "meaning": {n: MEASURES[n][1] for n in MEASURES},
            "in_till_data": {n: MEASURES[n][0] for n in MEASURES}, "model": tabular.describe(),
            "note": "deprivation quintile is the neighbourhood's rank within London on income deprivation, used against the survey's national quintile"}
    (CACHE / "survey_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(ev, indent=1))
    print(P.drop(columns=["area_id"]).describe().loc[["min", "mean", "max"]].round(3).T.to_string())


@lru_cache(maxsize=1)
def area_prevalence() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "survey_area_prevalence.parquet").set_index("area_id")


@lru_cache(maxsize=1)
def meta() -> dict:
    return json.loads((CACHE / "survey_meta.json").read_text())


def _blend(where) -> pd.Series | None:
    """Prevalence over one neighbourhood (a code) or a catchment ({code: weight})."""
    A = area_prevalence()
    w = pd.Series(where if isinstance(where, dict) else {where: 1.0}, dtype=float)
    w = w[w.index.isin(A.index)]
    return None if w.empty else A.loc[w.index, list(MEASURES)].mul(w, axis=0).sum() / w.sum()


def local(where) -> list:
    """Every survey-measured persona among the residents this store draws from: share of adults, and how that compares with the UK."""
    M, a = meta(), _blend(where)
    if a is None:
        return []
    return [{"persona": n, "share_of_adults": round(float(a[n]), 3), "uk_share": M["uk_share"][n],
             "index_vs_uk": round(float(a[n] / max(M["uk_share"][n], 1e-9)), 2), "in_till_data": M["in_till_data"][n], "survey_answer": M["meaning"][n]}
            for n in MEASURES]


def tilt(where) -> dict:
    """Multiplier on the till-measured personas' weights at a store (share in its catchment over the London-wide share)."""
    A, M, a = area_prevalence(), meta(), _blend(where)
    if a is None:
        return {}
    base = A[list(MEASURES)].mean()
    # only where the survey shows place and age actually predict the persona; the rest are spread evenly and stay at 1
    return {n: float(np.clip(a[n] / base[n], 0.5, 2.0)) for n in MEASURES if M["in_till_data"][n] and M["eval"][n]["auc"] >= MIN_AUC}


if __name__ == "__main__":
    build()
