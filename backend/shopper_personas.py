"""The team's 28 shopper personas, as categories of individuals, measured from what each household actually did at the till.

Location is a separate input. A persona is a kind of person; the same persona behaves the same way in Camden or Barking,
and the store's neighbourhood and format are applied on top.

Fifteen of the 28 can be measured from supermarket transactions. Thirteen cannot (they are about online channels,
apparel returns, social influence or not buying at all) and need a survey; they are listed with no weight until one is linked.

Run: python -m backend.shopper_personas        fast test on sampled weeks (about 2 minutes), writes data/cache/persona28_eval.json
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import CACHE, DATA

# persona -> (group, what it means in a supermarket, score as weights on standardised traits)
MEASURED = {
    "The Bargain Hunter":           ("Financial", "highest share of items on promotion and of trips using a coupon", {"promo": 1, "coupon": 1}),
    "The Luxury Loyalist":          ("Financial", "pays above the category's typical price, branded, rarely on promotion", {"price_index": 1, "own_label": -1, "promo": -0.5}),
    "The Value Optimizer":          ("Financial", "own label and below-typical prices without relying on promotions", {"own_label": 1, "price_index": -0.5}),
    "The Comparison Expert":        ("Financial", "splits trips across many stores", {"stores": 1, "store_loyalty": -1}),
    "The Ethical Consumer":         ("Financial", "highest share of organic and natural products", {"organic": 2}),
    "The Impulse Buyer":            ("Behavioural", "checkout-lane confectionery and magazines in the basket", {"checklane": 2}),
    "The Mission Shopper":          ("Behavioural", "small baskets of things bought before; in and out", {"small": 1, "repeat": 0.5, "frequency": 0.5}),
    "The Habitual Creature":        ("Behavioural", "same products, same store, time after time", {"repeat": 1, "store_loyalty": 1}),
    "The Seasonal Splurger":        ("Behavioural", "spend concentrated in the days before holidays", {"holiday": 2}),
    "The Bulk Buyer":               ("Behavioural", "few, very large trips", {"lines": 1, "frequency": -1}),
    "The Spontaneous Adventurer":   ("Psychological", "highest share of products never bought before", {"repeat": -2}),
    "The Methodical Perfectionist": ("Psychological", "shops on a fixed day and hour", {"schedule": 2}),
    "The Humanistic Connector":     ("Psychological", "spends most at staffed counters: deli, fish, flowers, hot food", {"service": 2}),
    "The Decisive Alpha":           ("Psychological", "quick small trips at lunch and straight after work", {"peak_quick": 2}),
    "The Gift-Giver Archetype":     ("Social", "cards, wrap, party supplies and flowers", {"gift": 2}),
}
NOT_MEASURABLE = {
    "The Window Shopper": ("Financial", "buys nothing, so leaves no transaction"),
    "The Multi-Size Guard": ("Behavioural", "apparel returns; not a grocery behaviour"),
    "The Digital-First Shopper": ("Technology", "online channel is not in till data"),
    "The Brick-and-Mortar Traditionalist": ("Technology", "everyone in till data shops in store; needs their online behaviour to tell apart"),
    "The Webroomer": ("Technology", "online research is not in till data"),
    "The Showroomer": ("Technology", "purchase happens elsewhere"),
    "The Click-and-Collect Devotee": ("Technology", "collection orders are not flagged in this panel"),
    "The Tech Innovator": ("Technology", "self-scan and app use are not recorded"),
    "The Skeptical Critic": ("Psychological", "attitude to risk and guarantees; needs a survey"),
    "The Social Groupie": ("Social", "who they shop with is not recorded"),
    "The Trend Follower": ("Social", "social-media influence is not recorded"),
    "The Status Seeker": ("Social", "motive, not behaviour; needs a survey"),
    "The Community Advocate": ("Social", "avoids chains, so is absent from a chain's data"),
}
TRAITS = ["promo", "coupon", "price_index", "own_label", "stores", "store_loyalty", "organic", "checklane", "small", "repeat",
          "frequency", "holiday", "lines", "schedule", "service", "peak_quick", "gift"]
SERVICE = ("DELI", "SEAFOOD", "FLORAL", "RESTAURANT", "SALAD BAR", "CHEF SHOPPE")


@lru_cache(maxsize=1)
def raw() -> pd.DataFrame:
    """Every line item (food and non-food) with the flags the traits need."""
    f = CACHE / "persona_raw.parquet"
    if f.exists():
        return pd.read_parquet(f)
    from . import retail
    D = DATA / "dunnhumby"
    t, p = pd.read_parquet(D / "transactions.parquet"), pd.read_parquet(D / "products.parquet")
    p["key"] = (p.department.astype(str) + "|" + p.product_category.astype(str) + "|" + p.product_type.astype(str)).str.upper()
    p["organic"] = p.key.str.contains("ORGANIC|NUTRITION\\|", regex=True).astype(int)
    p["checklane"] = p.key.str.contains("CHECKLANE|MAGAZINE|GUM").astype(int)
    p["service"] = p.department.astype(str).str.upper().isin(SERVICE).astype(int)
    p["gift"] = p.key.str.contains("GREETING|WRAP|PARTY|FLORAL|GIFT").astype(int)
    p["own_label"] = (p.brand.astype(str) == "Private").astype(int)
    t = t[(t.quantity > 0) & (t.sales_value > 0)].merge(p[["product_id", "product_category", "organic", "checklane", "service", "gift", "own_label"]], on="product_id")
    ts = t.transaction_timestamp.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    t["date"], t["hour"], t["dow"] = ts.dt.normalize(), ts.dt.hour, ts.dt.weekday
    t = pd.concat([t, retail.calendar_flags(t.date, retail.US_HOLIDAYS_2017)], axis=1)
    unit = t.sales_value / t.quantity
    t["price_index"] = (unit / unit.groupby(t.product_category.astype(str)).transform("median")).clip(0.2, 5)
    t["promo"] = (t.retail_disc != 0).astype(int)
    t["coupon"] = ((t.coupon_disc != 0) | (t.coupon_match_disc != 0)).astype(int)
    t = t[["household_id", "store_id", "basket_id", "product_id", "week", "date", "hour", "dow", "holiday", "pre_holiday", "sales_value",
           "price_index", "promo", "coupon", "organic", "checklane", "service", "gift", "own_label"]]
    t.to_parquet(f)
    return t


def traits(t: pd.DataFrame, min_trips: int = 8) -> pd.DataFrame:
    """One row per household: 17 habits measured over the weeks in `t`."""
    t = t.sort_values(["household_id", "date"])
    first = t.groupby(["household_id", "product_id"]).date.transform("min")
    t = t.assign(seen_before=(t.date > first).astype(int), spend_hol=t.sales_value * ((t.holiday + t.pre_holiday) > 0))
    b = t.groupby(["household_id", "basket_id"]).agg(store=("store_id", "first"), dow=("dow", "first"), hour=("hour", "first"), lines=("product_id", "size"),
                                                    coupon=("coupon", "max"), checklane=("checklane", "max")).reset_index()
    b["small"] = (b.lines <= 5).astype(int)
    b["peak_quick"] = (b.small.eq(1) & (b.dow < 5) & b.hour.isin([12, 13, 17, 18])).astype(int)
    weeks = max(t.week.nunique(), 1)
    g = b.groupby("household_id")
    h = pd.DataFrame({"n_trips": g.size(), "frequency": g.size() / weeks, "lines": g.lines.mean(), "small": g.small.mean(), "coupon": g.coupon.mean(),
                      "checklane": g.checklane.mean(), "peak_quick": g.peak_quick.mean(), "stores": g.store.nunique(),
                      "store_loyalty": g.store.agg(lambda s: s.value_counts(normalize=True).iloc[0]),
                      "schedule": g.dow.agg(lambda s: s.value_counts(normalize=True).iloc[0]) + g.hour.agg(lambda s: (s // 3).value_counts(normalize=True).iloc[0])})
    lg = t.groupby("household_id")
    exp_hol = t.drop_duplicates("date").pipe(lambda d: ((d.holiday + d.pre_holiday) > 0).mean())
    h = h.join(pd.DataFrame({"promo": lg.promo.mean(), "price_index": lg.price_index.mean(), "own_label": lg.own_label.mean(), "organic": lg.organic.mean(),
                             "service": lg.service.mean(), "gift": lg.gift.mean(), "repeat": lg.seen_before.mean(),
                             "holiday": (lg.spend_hol.sum() / lg.sales_value.sum()) / max(exp_hol, 1e-9)}))
    return h[h.n_trips >= min_trips]


def scores(h: pd.DataFrame, ref: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each household's score on each measurable persona. Traits and scores are standardised against `ref` (default: itself)."""
    ref = h if ref is None else ref
    z = ((h[TRAITS] - ref[TRAITS].mean()) / ref[TRAITS].std()).clip(-3, 3)
    zr = ((ref[TRAITS] - ref[TRAITS].mean()) / ref[TRAITS].std()).clip(-3, 3)
    raw_s = pd.DataFrame({p: sum(w * z[k] for k, w in f.items()) for p, (_, _, f) in MEASURED.items()})
    ref_s = pd.DataFrame({p: sum(w * zr[k] for k, w in f.items()) for p, (_, _, f) in MEASURED.items()})
    return (raw_s - ref_s.mean()) / ref_s.std()


def assign(h: pd.DataFrame, ref: pd.DataFrame | None = None) -> pd.Series:
    """Primary persona: the one on which the household is most unusual."""
    return scores(h, ref).idxmax(axis=1)


def fit() -> tuple:
    """Production assignment over the full year. Returns (household -> persona, persona table) in the shape retail.py expects."""
    fh, fp = CACHE / "retail_household_persona.parquet", CACHE / "retail_personas.parquet"
    if fh.exists() and fp.exists():
        return pd.read_parquet(fh), pd.read_parquet(fp)
    from . import retail
    h = traits(raw(), min_trips=20)
    h["persona"] = assign(h)
    S = scores(h)
    demo = retail.lines().drop_duplicates("household_id").set_index("household_id")[retail.DEMO_FIELDS].reindex(h.index)
    rows = []
    for name, (grp, meaning, _) in MEASURED.items():
        m = h[h.persona == name]
        d = demo.loc[m.index].dropna()
        rows.append({"persona": name, "group": grp, "meaning": meaning, "measured": True, "households": len(m), "share": round(len(m) / len(h), 4),
                     "households_with_demographics": len(d), "older_share": round(float((d.age_ord >= 4).mean()), 3) if len(d) else None,
                     "family_share": round(float((d.kids > 0).mean()), 3) if len(d) else None,
                     "trips_per_week": round(float(m.frequency.mean()), 2), "lines_per_trip": round(float(m.lines.mean()), 1),
                     **{f"p_{k}": float(m[k].mean()) for k in TRAITS}})
    for name, (grp, why) in NOT_MEASURABLE.items():
        rows.append({"persona": name, "group": grp, "meaning": why, "measured": False, "households": 0, "share": 0.0})
    P = pd.DataFrame(rows)
    P["name"], P["rule"] = P.persona, P.persona + ": " + P.meaning
    H = h[["persona"]].reset_index()
    H.to_parquet(fh); P.to_parquet(fp)
    return H, P


# ------------------------------------------------------------------ fast test on sampled weeks
def evaluate(seed: int = 0, n_context: int = 3000, n_test: int = 1500) -> dict:
    """Profile households on 10 weeks sampled from the first half of the year, predict their trips in 8 weeks sampled from the
    second half, score only on households the model never saw. AUC, 0.5 is chance."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupShuffleSplit
    from . import retail, tabular
    rng = np.random.default_rng(seed)
    wp, wt = sorted(rng.choice(range(1, 27), 10, replace=False).tolist()), sorted(rng.choice(range(27, 54), 8, replace=False).tolist())
    R = raw()
    h = traits(R[R.week.isin(wp)], min_trips=5)
    S = scores(h)
    h["persona"] = S.idxmax(axis=1)
    cent = h.groupby("persona")[TRAITS].mean().add_prefix("c_")
    hz = (h[TRAITS] - h[TRAITS].mean()) / h[TRAITS].std()
    h["k28"] = KMeans(28, n_init=5, random_state=0).fit_predict(hz.fillna(0))
    k28c = h.groupby("k28")[TRAITS].mean().add_prefix("k_")
    B = retail.all_baskets()
    own = h[TRAITS].add_prefix("t_").join(h[["persona", "k28"]]).reset_index()
    T = B[B.week.isin(wt)].merge(own, on="household_id") \
        .merge(cent, left_on="persona", right_index=True).merge(k28c, left_on="k28", right_index=True)
    T = T.merge(S.add_prefix("s_"), left_on="household_id", right_index=True)
    D = retail.lines().drop_duplicates("household_id")[["household_id"] + retail.DEMO_FIELDS].dropna()
    WHEN, MISSION = ["hour", "weekend", "pre_holiday"], ["big_store"]          # mission: top-up or stock-up trip, set by store format
    sets = {"demographics": retail.DEMO_FIELDS, "when only": WHEN,
            "named persona (1 of 15) + when": list(cent.columns) + WHEN, "data-driven clusters (1 of 28) + when": list(k28c.columns) + WHEN,
            "scores on all 15 personas + when": [f"s_{p}" for p in MEASURED] + WHEN,
            "when + mission": WHEN + MISSION, "named persona + when + mission": list(cent.columns) + WHEN + MISSION,
            "scores on all 15 personas + when + mission": [f"s_{p}" for p in MEASURED] + WHEN + MISSION}
    tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=seed).split(T, groups=T.household_id))
    targets = ["alcohol", "fresh produce", "snacks & confectionery", "ready meals & deli", "meat & fish", "drinks"]
    out = {}
    for y in targets:
        row = {}
        for name, cols in sets.items():
            a, t = T.iloc[tr], T.iloc[te]
            if name == "demographics":
                a, t = a.merge(D, on="household_id"), t.merge(D, on="household_id")
            ctx, t = a.sample(min(n_context, len(a)), random_state=0), t.sample(min(n_test, len(t)), random_state=0)
            m = tabular.classifier().fit(ctx[cols], ctx[y])
            row[name] = round(float(roc_auc_score(t[y], m.predict_proba(t[cols])[:, list(m.classes_).index(1)])), 3)
        out[y] = row
        print(y, row, flush=True)
    df = pd.DataFrame(out).T
    res = {"profile_weeks": wp, "test_weeks": wt, "households": len(h), "test_households": int(T.iloc[te].household_id.nunique()), "trips_in_test_weeks": len(T),
           "context_rows": n_context, "persona_sizes_in_profile_weeks": h.persona.value_counts().to_dict(), "auc": out, "mean_auc": df.mean().round(3).to_dict(),
           "model": tabular.describe()}
    (CACHE / "persona28_eval.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    r = evaluate()
    print(json.dumps({k: r[k] for k in ("profile_weeks", "test_weeks", "households", "test_households", "mean_auc", "persona_sizes_in_profile_weeks")}, indent=1))
