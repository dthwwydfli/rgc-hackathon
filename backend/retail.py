"""Retail engine: who buys what, when, in a supermarket.

Source: dunnhumby "The Complete Journey" (via the completejourney R package): every line item bought by 2,469
households at 457 stores of one US grocer during 2017, with a timestamp; 801 households carry demographics.
From it we learn three things, all per persona:
    trips     shopping trips per household per day, by day of week, hour and store size
    baskets   items per trip
    picks     P(category | persona, hour, day type, pre-holiday, store size)   <- in-context tabular model

Build: python -m backend.retail        (writes data/cache/retail_*.parquet and retail_eval.json)
"""
import json
import sys
import time
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from . import shopper_personas, tabular
from .config import CACHE, DATA

HOURS = list(range(6, 23))            # store trading hours modelled (local time)
N_CONTEXT = 6000

# ------------------------------------------------------------------ 28 personas, built from behaviour
# Demographic personas were tested first and predict nothing on unseen households (mean AUC 0.52); personas built from
# what a household bought in the first half of the year predict the second half (0.65). See exploration/t1_behaviour_personas.py.
N_PERSONAS, MIN_TRIPS = 28, 20
AGE_ORD = {"19-24": 0, "25-34": 1, "35-44": 2, "45-54": 3, "55-64": 4, "65+": 5}
INC_TIER = {"Under 15K": 0, "15-24K": 0, "25-34K": 0, "35-49K": 1, "50-74K": 1, "75-99K": 2, "100-124K": 2,
            "125-149K": 3, "150-174K": 3, "175-199K": 3, "200-249K": 3, "250K+": 3}
DEMO_FIELDS = ["age_ord", "income_tier", "adults", "kids", "hh_size"]
TIME_FIELDS = ["hour", "weekend", "pre_holiday"]
TRAITS = {"h_trips": ("frequent", "occasional"), "h_lines": ("big baskets", "small baskets"), "h_small": ("top-up trips", "stock-up trips"),
          "h_evening": ("evening", "daytime"), "h_weekend": ("weekend", "weekday"), "h_big": ("big stores", "local stores"),
          "h_own": ("own label", "branded"), "h_promo": ("deal seeking", "full price")}


# ------------------------------------------------------------------ categories: 10 groups, 30 categories
RULES = [  # (group, category, keywords matched against "DEPARTMENT|PRODUCT_CATEGORY")
    ("alcohol", "beer & cider", ["BEERS/ALES", "BEER"]), ("alcohol", "wine", ["WINE"]), ("alcohol", "spirits", ["SPIRITS|", "LIQUOR"]),
    ("drinks", "water", ["WATER"]), ("drinks", "sports & energy drinks", ["ISOTONIC", "ENERGY"]),
    ("drinks", "juice", ["JUICE", "DRNK MX"]), ("drinks", "soft drinks", ["SOFT DRINKS"]),
    ("breakfast & hot drinks", "coffee", ["COFFEE"]), ("breakfast & hot drinks", "tea", ["TEAS", "TEA "]),
    ("breakfast & hot drinks", "cereal", ["CEREAL"]), ("breakfast & hot drinks", "breakfast foods", ["BRKFST", "BREAKFAST", "SYRUPS", "PNT BTR"]),
    ("snacks & confectionery", "confectionery", ["CANDY", "GUM"]), ("snacks & confectionery", "crisps & savoury snacks", ["BAG SNACKS", "SNACK", "POPCORN", "NUTS"]),
    ("snacks & confectionery", "biscuits & crackers", ["COOKIES", "CRACKERS"]), ("snacks & confectionery", "ice cream", ["ICE CREAM", "NOVELTIES"]),
    ("bakery", "sweet bakery", ["SWEET GOODS", "PASTRY|", "CAKE", "PIE/DESSERT", "DONUT"]), ("bakery", "bread", ["BREAD", "ROLLS", "BAGEL", "DOUGH"]),
    ("ready meals & deli", "pizza", ["PIZZA"]), ("ready meals & deli", "soup", ["SOUP"]),
    ("ready meals & deli", "food to go & deli", ["DELI|", "SALAD BAR", "RESTAURANT", "CHEF SHOPPE", "SANDWICH", "HEAT/SERVE"]),
    ("ready meals & deli", "ready meals", ["DINNERS", "DINNER MXS", "FRZN MEAT", "ENTREE", "FROZEN GROCERY", "HISPANIC", "FRZN POTATOES", "FRZN VEG"]),
    ("dairy & eggs", "yogurt", ["YOGURT"]), ("dairy & eggs", "cheese", ["CHEESE"]), ("dairy & eggs", "eggs", ["EGGS"]),
    ("dairy & eggs", "milk", ["MILK", "DAIRY"]), ("dairy & eggs", "butter & spreads", ["MARGARINE", "BUTTER"]),
    ("meat & fish", "fish", ["SEAFOOD"]), ("meat & fish", "poultry", ["CHICKEN", "TURKEY", "POULTRY"]),
    ("meat & fish", "bacon, sausage & cooked meats", ["LUNCHMEAT", "BACON", "SAUSAGE", "HOT DOG", "MEAT-PCKGD|"]),
    ("meat & fish", "fresh meat", ["MEAT|", "BEEF", "PORK", "LAMB"]),
    ("fresh produce", "salad", ["SALAD"]), ("fresh produce", "fruit", ["FRUIT", "APPLES", "CITRUS", "BERRIES", "GRAPES", "MELON", "BANANA", "PEARS", "STONE"]),
    ("fresh produce", "vegetables", ["PRODUCE|", "VEGETABLES - ALL", "ONIONS", "POTATOES", "TOMATOES", "PEPPERS", "CARROTS", "CORN", "MUSHROOM", "BROCCOLI", "ORGANICS"]),
    ("store cupboard", "store cupboard", ["GROCERY|"]),
]
NON_FOOD = ("DRUG GM|", "COSMETICS|", "FLORAL|", "FUEL|", "MISCELLANEOUS|", "GARDEN", "COUPON|", "TRAVEL", "PHOTO", "CNTRL", "TOYS|", "NUTRITION|")
NON_FOOD_CAT = ("PET", "CAT FOOD", "DOG FOOD", "TISSUE", "TOWEL", "DETERGENT", "CLEAN", "BAG", "HOUSEWARES", "CIGAR", "BABY", "LAUNDRY", "CHARCOAL", "CANDLE")


def categorise(dept: str, cat: str) -> tuple:
    key = f"{dept}|{cat}".upper()
    if "CANDY" not in key and (key.startswith(NON_FOOD) or any(w in key for w in NON_FOOD_CAT)):
        return ("non-food", "non-food")
    for group, category, words in RULES:
        if any(w in key for w in words):
            return (group, category)
    return ("non-food", "non-food")


GROUPS = list(dict.fromkeys(g for g, _, _ in RULES))
CATEGORIES = list(dict.fromkeys(c for _, c, _ in RULES))
GROUP_OF = {c: g for g, c, _ in RULES}

US_HOLIDAYS_2017 = ["2017-01-01", "2017-02-05", "2017-04-16", "2017-05-29", "2017-07-04", "2017-09-04", "2017-11-23", "2017-12-25", "2018-01-01"]


def calendar_flags(dates: pd.Series, holidays: list) -> pd.DataFrame:
    """pre_holiday = the three days before a major holiday; holiday = the day itself."""
    d = pd.to_datetime(dates).dt.normalize()
    hol = pd.to_datetime(pd.Series(holidays))
    gap = pd.concat([(h - d).dt.days.rename(i) for i, h in enumerate(hol)], axis=1)
    return pd.DataFrame({"holiday": (gap == 0).any(axis=1).astype(int), "pre_holiday": ((gap >= 1) & (gap <= 3)).any(axis=1).astype(int)}, index=dates.index)


@lru_cache(maxsize=1)
def lines() -> pd.DataFrame:
    """Food and drink line items with local time, calendar flags, category, store size and (where known) persona."""
    f = CACHE / "retail_lines.parquet"
    if f.exists():
        return pd.read_parquet(f)
    D = DATA / "dunnhumby"
    t, p, d = (pd.read_parquet(D / f"{n}.parquet") for n in ("transactions", "products", "demographics"))
    p[["group", "category"]] = [categorise(str(a), str(b)) for a, b in zip(p.department, p.product_category)]
    t = t.merge(p[["product_id", "group", "category", "brand"]], on="product_id")
    t = t[(t.group != "non-food") & (t.quantity > 0)]
    # timestamps in the package are UTC (trough at 08-09h); the grocer trades in US Eastern time
    ts = t.transaction_timestamp.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    t["date"], t["hour"], t["dow"] = ts.dt.normalize(), ts.dt.hour, ts.dt.weekday          # 0 = Monday
    t["weekend"] = (t.dow >= 4).astype(int)                                                 # Fri-Sun
    t = pd.concat([t, calendar_flags(t.date, US_HOLIDAYS_2017)], axis=1)
    t["own_label"] = (t.brand == "Private").astype(int)
    t["on_promo"] = (t.retail_disc > 0).astype(int)
    size = t.groupby("store_id").basket_id.nunique()
    t["big_store"] = t.store_id.map((size >= size.quantile(0.75)).astype(int))             # top quarter of stores by trips
    d = d.dropna(subset=["age", "income", "household_comp"]).astype(str)
    d["income_tier"] = d.income.map(INC_TIER).astype(int)
    d["age_ord"] = d.age.map(AGE_ORD).astype(int)
    d["adults"] = d.household_comp.str[0].astype(int)
    d["kids"] = d.kids_count.astype(str).str[0].astype(int)
    d["hh_size"] = d.household_size.astype(str).str[0].astype(int)
    t = t.merge(d[["household_id"] + DEMO_FIELDS], on="household_id", how="left")
    t = t[["household_id", "store_id", "basket_id", "date", "hour", "dow", "weekend", "holiday", "pre_holiday", "week", "group", "category",
           "quantity", "sales_value", "own_label", "on_promo", "big_store"] + DEMO_FIELDS].reset_index(drop=True)
    t.to_parquet(f)
    return t


@lru_cache(maxsize=1)
def all_baskets() -> pd.DataFrame:
    """One row per shopping trip, every household: when, where, how big, and which groups it contained."""
    f = CACHE / "retail_baskets_all.parquet"
    if f.exists():
        return pd.read_parquet(f)
    t = lines()
    t = t[t.hour.isin(HOURS)]
    key = ["basket_id", "household_id", "store_id", "date", "week", "hour", "dow", "weekend", "holiday", "pre_holiday", "big_store"]
    b = t.groupby(key, observed=True).agg(lines=("quantity", "size"), spend=("sales_value", "sum"), own_label=("own_label", "mean"), promo=("on_promo", "mean")).reset_index()
    has = (pd.crosstab(t.basket_id, t.group) > 0).astype(int).reindex(columns=GROUPS, fill_value=0)
    b = b.merge(has, left_on="basket_id", right_index=True)
    b["small_basket"] = (b.lines <= 5).astype(int)
    # Format is modelled through mission. 99% of this panel's trips are to the grocer's larger stores, so store size cannot
    # stand in for a UK convenience store; a top-up trip (five lines or fewer) can. From here on big_store = 1 means a
    # stock-up trip and 0 a top-up trip; the store's real size is kept as store_big.
    b["store_big"] = b.big_store
    b["big_store"] = 1 - b.small_basket
    b.to_parquet(f)
    return b


def profile(b: pd.DataFrame, weeks: float) -> pd.DataFrame:
    """A household's shopping habits over a period: how often, how big, when, where, and what its trips contain."""
    p = b.groupby("household_id").agg(h_trips=("basket_id", "size"), h_lines=("lines", "mean"), h_small=("small_basket", "mean"),
                                      h_evening=("hour", lambda h: (h >= 17).mean()), h_weekend=("weekend", "mean"), h_big=("store_big", "mean"),
                                      h_own=("own_label", "mean"), h_promo=("promo", "mean"), **{f"h_has_{g}": (g, "mean") for g in GROUPS})
    p["n_trips"] = p.h_trips
    p["h_trips"] = p.h_trips / weeks
    return p


PERSONA_FIELDS = [f"p_{k}" for k in shopper_personas.TRAITS]     # a persona is described to the model by its average habits
FEATS = PERSONA_FIELDS + TIME_FIELDS + ["big_store"]


def persona_fit() -> tuple:
    """(household -> persona, persona table). The personas are the team's 28 shopper types; see shopper_personas.py."""
    return shopper_personas.fit()


def personas() -> dict:
    """persona -> one-line description, all 28."""
    P = persona_fit()[1]
    return dict(zip(P.persona, P.rule))


def measured() -> list:
    P = persona_fit()[1]
    return P[P.measured].persona.tolist()


TARGETS = GROUPS


@lru_cache(maxsize=1)
def baskets() -> pd.DataFrame:
    """Trips by households that have a persona, with the persona's habit profile attached."""
    H, P = persona_fit()
    b = all_baskets().merge(H, on="household_id").merge(P[["persona"] + PERSONA_FIELDS], on="persona")
    b["life"] = b.persona                      # tables are keyed by persona
    return b


# ------------------------------------------------------------------ build
def build():
    t0 = time.time()
    L = lines()
    B = baskets()
    H, P = persona_fit()
    t = L[L.hour.isin(HOURS)].drop(columns=["big_store"]).merge(B[["basket_id", "persona", "big_store"]], on="basket_id")
    t["life"] = t.persona
    print("lines", len(L), "with persona", len(t), "trips", len(B), "households", len(H), "stores", L.store_id.nunique(), flush=True)

    # picks: P(trip contains group | persona, hour, day type, pre-holiday, store size), one in-context model per group
    P = P[P.measured]
    q = P[["persona"] + PERSONA_FIELDS].merge(pd.DataFrame({"hour": HOURS}), how="cross").merge(pd.DataFrame({"weekend": [0, 1]}), how="cross") \
        .merge(pd.DataFrame({"pre_holiday": [0, 1]}), how="cross").merge(pd.DataFrame({"big_store": [0, 1]}), how="cross")
    ctx = B.sample(N_CONTEXT, random_state=1)
    G = q[["persona", "hour", "weekend", "pre_holiday", "big_store"]].copy()
    for y in TARGETS:
        m = tabular.classifier().fit(ctx[FEATS], ctx[y])
        G[y] = m.predict_proba(q[FEATS])[:, list(m.classes_).index(1)]
    G.melt(id_vars=["persona", "hour", "weekend", "pre_holiday", "big_store"], var_name="group", value_name="p").to_parquet(CACHE / "retail_pick.parquet")
    print("pick grid", len(q), "query rows x", len(TARGETS), "models", f"[{time.time()-t0:.0f}s]", flush=True)
    # lines bought in a group when the trip includes it, by life stage and store size
    lg = t.groupby(["basket_id", "life", "big_store", "group"], observed=True).size().rename("n").reset_index()
    lg.groupby(["life", "big_store", "group"]).n.mean().rename("lines").reset_index().to_parquet(CACHE / "retail_depth.parquet")

    # category within group, by life stage and day part (counts, smoothed toward the group's overall split)
    t["daypart"] = pd.cut(t.hour, [0, 11, 14, 17, 24], right=False, labels=["morning", "lunch", "afternoon", "evening"]).astype(str)
    allc = t.groupby(["group", "category"]).size().rename("n_all").reset_index()
    allc["share_all"] = allc.n_all / allc.groupby("group").n_all.transform("sum")
    w = t.groupby(["life", "daypart", "group", "category"]).size().rename("n").reset_index()
    full = pd.MultiIndex.from_product([sorted(H.persona.unique()), ["morning", "lunch", "afternoon", "evening"]], names=["life", "daypart"]).to_frame(index=False).merge(allc, how="cross")
    w = full.merge(w, how="left").fillna({"n": 0})
    w["share"] = (w.n + 30 * w.share_all) / (w.groupby(["life", "daypart", "group"]).n.transform("sum") + 30)
    w[["life", "daypart", "group", "category", "share"]].to_parquet(CACHE / "retail_within.parquet")

    # trips: per household per day, by persona and day of week; hour shape by life stage, day type and store size
    hh = H.persona.value_counts()
    ndays = L.drop_duplicates("date").assign(dow=lambda x: x.date.dt.weekday).groupby("dow").size()
    grid = pd.MultiIndex.from_product([sorted(hh.index), range(7)], names=["persona", "dow"]).to_frame(index=False).merge(B.groupby(["persona", "dow"]).size().rename("n").reset_index(), how="left")
    grid["trips_per_day"] = grid.n.fillna(0) / (grid.persona.map(hh) * grid.dow.map(ndays))
    grid[["persona", "dow", "trips_per_day"]].to_parquet(CACHE / "retail_trips.parquet")
    hs = pd.crosstab([B.life, B.weekend, B.big_store], B.hour).reindex(columns=HOURS, fill_value=0) + 2
    hs.div(hs.sum(1), axis=0).stack().rename("share").reset_index().to_parquet(CACHE / "retail_hours.parquet")
    B.groupby("persona").big_store.mean().rename("p_big").reset_index().to_parquet(CACHE / "retail_bigshare.parquet")
    cal = B.groupby(["date", "pre_holiday", "holiday", "dow"]).size().rename("trips").reset_index()
    cal["index"] = cal.trips / cal.dow.map(cal[(cal.pre_holiday == 0) & (cal.holiday == 0)].groupby("dow").trips.mean())
    uplift = {"pre_holiday": round(float(cal[cal.pre_holiday == 1]["index"].mean()), 3), "holiday": round(float(cal[cal.holiday == 1]["index"].mean()), 3)}
    B.groupby(["persona", "weekend"]).size().rename("trips").reset_index().to_parquet(CACHE / "retail_support.parquet")
    meta = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": tabular.describe(), "context_rows": N_CONTEXT, "lines": len(t), "trips": len(B),
            "households": len(H), "personas": "15 of the team's 28 shopper personas are measurable from till data", "stores": int(L.store_id.nunique()), "calendar_uplift": uplift,
            "source": "dunnhumby The Complete Journey, 2017, via the completejourney R package"}
    (CACHE / "retail_meta.json").write_text(json.dumps(meta, indent=1))
    print("done", meta["calendar_uplift"], f"[{time.time()-t0:.0f}s]", flush=True)


@lru_cache(maxsize=1)
def load() -> dict:
    r = lambda n: pd.read_parquet(CACHE / f"retail_{n}.parquet")
    ev = CACHE / "persona28_eval.json"         # written by python -m backend.shopper_personas
    return {"pick": r("pick"), "within": r("within"), "trips": r("trips"), "hours": r("hours"), "bigshare": r("bigshare"), "depth": r("depth"),
            "support": r("support"), "personas": r("personas"), "meta": json.loads((CACHE / "retail_meta.json").read_text()),
            "eval": json.loads(ev.read_text()) if ev.exists() else None}


if __name__ == "__main__":
    build()
