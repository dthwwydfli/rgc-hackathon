"""Which persona goes to which store format, and when.

Source: dunnhumby "Let's Get Sort-of-Real" (50,000-customer sample). SYNTHETIC: dunnhumby built it to replicate the
patterns in real till data. It is the only source here that links a customer to a store format, a region and an hour,
so it is used for that link only, and everything from it is labelled synthetic. Products are anonymous codes.

Ten of the team's personas can be measured in it (no promotion, brand or product names, so five till personas cannot).
Fast by design: 10 weeks sampled across the first year to profile customers, 6 weeks sampled later to test.
Run: python -m backend.sortofreal
"""
import json
import zipfile
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import CACHE, DATA

ZIP = DATA / "sortofreal" / "sample_50k.zip"
PROFILE_WEEKS = ["200610", "200616", "200622", "200628", "200634", "200640", "200646", "200652", "200706", "200712"]
TEST_WEEKS = ["200724", "200732", "200740", "200748", "200804", "200812"]
FORMATS = {"SS": "convenience", "MS": "small supermarket", "LS": "supermarket", "XLS": "superstore"}
COLS = ["SHOP_WEEK", "SHOP_DATE", "SHOP_WEEKDAY", "SHOP_HOUR", "QUANTITY", "SPEND", "PROD_CODE", "CUST_CODE", "BASKET_ID", "BASKET_SIZE",
        "BASKET_PRICE_SENSITIVITY", "BASKET_TYPE", "BASKET_DOMINANT_MISSION", "STORE_CODE", "STORE_FORMAT", "STORE_REGION"]
TRAITS = ["frequency", "lines", "small", "stores", "store_loyalty", "repeat", "schedule", "peak_quick", "less_affluent", "up_market", "mid_market"]
PERSONAS = {"The Bargain Hunter": {"less_affluent": 2}, "The Luxury Loyalist": {"up_market": 2}, "The Value Optimizer": {"mid_market": 2},
            "The Comparison Expert": {"stores": 1, "store_loyalty": -1}, "The Mission Shopper": {"small": 1, "repeat": 0.5, "frequency": 0.5},
            "The Habitual Creature": {"repeat": 1, "store_loyalty": 1}, "The Bulk Buyer": {"lines": 1, "frequency": -1},
            "The Spontaneous Adventurer": {"repeat": -2}, "The Methodical Perfectionist": {"schedule": 2}, "The Decisive Alpha": {"peak_quick": 2}}


def read(weeks: tuple) -> pd.DataFrame:
    f = CACHE / f"sor_{weeks[0]}_{weeks[-1]}_{len(weeks)}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    z = zipfile.ZipFile(ZIP)
    names = {n.split("_")[-1][:6]: n for n in z.namelist() if "transactions_" in n}
    d = pd.concat([pd.read_csv(z.open(names[w]), usecols=COLS, dtype={"BASKET_ID": str}) for w in weeks])
    d = d.dropna(subset=["CUST_CODE"])
    d.to_parquet(f)
    return d


def trips(d: pd.DataFrame) -> pd.DataFrame:
    b = d.groupby("BASKET_ID").agg(cust=("CUST_CODE", "first"), week=("SHOP_WEEK", "first"), date=("SHOP_DATE", "first"), weekday=("SHOP_WEEKDAY", "first"),
                                   hour=("SHOP_HOUR", "first"), lines=("PROD_CODE", "size"), spend=("SPEND", "sum"), price=("BASKET_PRICE_SENSITIVITY", "first"),
                                   type=("BASKET_TYPE", "first"), mission=("BASKET_DOMINANT_MISSION", "first"), store=("STORE_CODE", "first"),
                                   format=("STORE_FORMAT", "first"), region=("STORE_REGION", "first")).reset_index()
    b["weekend"] = b.weekday.isin([1, 6, 7]).astype(int)            # 1 = Sunday in this file; Fri-Sun to match the rest of the system
    b["small"] = (b.lines <= 5).astype(int)
    return b


def traits(d: pd.DataFrame, min_trips: int = 5) -> pd.DataFrame:
    b = trips(d)
    b["peak_quick"] = (b.small.eq(1) & b.weekday.between(2, 6) & b.hour.isin([12, 13, 17, 18])).astype(int)
    d = d.sort_values(["CUST_CODE", "SHOP_DATE"])
    first = d.groupby(["CUST_CODE", "PROD_CODE"]).SHOP_DATE.transform("min")
    rep = (d.SHOP_DATE > first).groupby(d.CUST_CODE).mean()
    g = b.groupby("cust")
    h = pd.DataFrame({"n_trips": g.size(), "frequency": g.size() / max(b.week.nunique(), 1), "lines": g.lines.mean(), "small": g.small.mean(),
                      "stores": g.store.nunique(), "store_loyalty": g.store.agg(lambda s: s.value_counts(normalize=True).iloc[0]),
                      "schedule": g.weekday.agg(lambda s: s.value_counts(normalize=True).iloc[0]) + g.hour.agg(lambda s: (s // 3).value_counts(normalize=True).iloc[0]),
                      "peak_quick": g.peak_quick.mean(), "less_affluent": g.price.agg(lambda s: (s == "LA").mean()), "up_market": g.price.agg(lambda s: (s == "UM").mean()),
                      "mid_market": g.price.agg(lambda s: (s == "MM").mean())})
    h["repeat"] = rep.reindex(h.index)
    return h[h.n_trips >= min_trips]


def scores(h: pd.DataFrame) -> pd.DataFrame:
    z = ((h[TRAITS] - h[TRAITS].mean()) / h[TRAITS].std()).clip(-3, 3)
    s = pd.DataFrame({p: sum(w * z[k] for k, w in f.items()) for p, f in PERSONAS.items()})
    return (s - s.mean()) / s.std()


def build(seed: int = 0, n_context: int = 3000, n_test: int = 2000) -> dict:
    from sklearn.metrics import roc_auc_score
    from . import tabular
    P, T = read(tuple(PROFILE_WEEKS)), read(tuple(TEST_WEEKS))
    h = traits(P)
    S = scores(h)
    h["persona"] = S.idxmax(axis=1)
    bp = trips(P).merge(h[["persona"]], left_on="cust", right_index=True)
    # ---- who goes where: share of each persona's trips by store format, against all customers
    fmt = pd.crosstab(bp.persona, bp.format, normalize="index").reindex(columns=list(FORMATS))
    lift = (fmt / bp.format.value_counts(normalize=True).reindex(list(FORMATS))).round(3)
    lift.rename(columns=FORMATS).reset_index().to_parquet(CACHE / "sor_format_lift.parquet")
    # ---- when: hour profile by format and day type
    hours = pd.crosstab([bp.format, bp.weekend], bp.hour, normalize="index")
    hours.stack().rename("share").reset_index().to_parquet(CACHE / "sor_hours.parquet")
    peak = bp.groupby(["persona", "format"]).hour.agg(lambda s: int(s.mode().iloc[0])).unstack().reindex(columns=list(FORMATS)).rename(columns=FORMATS)
    # ---- fast test: customers the model never saw, in later weeks
    rng = np.random.default_rng(seed)
    custs = h.index.to_numpy()
    rng.shuffle(custs)
    test_c = set(custs[: int(0.3 * len(custs))])
    cent = h.groupby("persona")[TRAITS].mean().add_prefix("c_")
    bt = trips(T).merge(h[["persona"]], left_on="cust", right_index=True).merge(cent, left_on="persona", right_index=True).merge(S.add_prefix("s_"), left_on="cust", right_index=True)
    bt["small_format"] = bt.format.isin(["SS", "MS"]).astype(int)
    bt["full_shop"] = (bt.type == "Full Shop").astype(int)
    bt["evening"] = (bt.hour >= 17).astype(int)
    a, t = bt[~bt.cust.isin(test_c)], bt[bt.cust.isin(test_c)]
    ctx, t = a.sample(min(n_context, len(a)), random_state=0), t.sample(min(n_test, len(t)), random_state=0)
    WHEN = ["hour", "weekday", "weekend"]
    tests = {"trip is at a convenience or small store": ("small_format", WHEN), "trip is a full shop": ("full_shop", WHEN), "trip is in the evening": ("evening", ["weekday", "weekend"])}
    auc = {}
    for label, (y, when) in tests.items():
        row = {"base_rate": round(float(a[y].mean()), 3)}
        for name, cols in (("when only", when), ("named persona + when", list(cent.columns) + when), ("scores on all 10 personas + when", [f"s_{p}" for p in PERSONAS] + when)):
            m = tabular.classifier().fit(ctx[cols], ctx[y])
            row[name] = round(float(roc_auc_score(t[y], m.predict_proba(t[cols])[:, list(m.classes_).index(1)])), 3)
        auc[label] = row
    out = {"source": "dunnhumby Let's Get Sort-of-Real, 50,000-customer sample (synthetic)", "profile_weeks": PROFILE_WEEKS, "test_weeks": TEST_WEEKS,
           "customers_profiled": len(h), "trips_profile_weeks": len(bp), "trips_test_weeks": len(bt), "test_customers": len(test_c),
           "persona_sizes": h.persona.value_counts().to_dict(), "format_share_of_trips": bp.format.value_counts(normalize=True).rename(FORMATS).round(3).to_dict(),
           "format_lift_by_persona": lift.rename(columns=FORMATS).to_dict("index"), "peak_hour_by_persona_and_format": peak.to_dict("index"),
           "basket_type_by_format": pd.crosstab(bp.format, bp.type, normalize="index").rename(index=FORMATS).round(3).to_dict("index"),
           "auc_unseen_customers_later_weeks": auc, "model": tabular.describe()}
    (CACHE / "sor_eval.json").write_text(json.dumps(out, indent=1))
    return out


@lru_cache(maxsize=1)
def format_lift() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "sor_format_lift.parquet").set_index("persona")


@lru_cache(maxsize=1)
def hours() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "sor_hours.parquet")


if __name__ == "__main__":
    r = build()
    print(json.dumps({k: v for k, v in r.items() if k not in ("profile_weeks", "test_weeks")}, indent=1))
