"""Test of the product's own prediction engine on UK data, in one pass.

The engine (store_sim.simulate) is run for every Tesco store in London, with its real inputs: UK store locations and
formats, gravity-model catchments, the 28 personas with their UK survey tilt and format preferences, hours, calendar,
UK category levels. Its output is then traced back through the catchments to the neighbourhoods the shoppers live in
and compared with what residents of those neighbourhoods really bought at Tesco (Tesco Grocery 1.0, Clubcard data).

Kept honest by holding data back: 30% of neighbourhoods have their Tesco purchases hidden from the engine. For those the
engine gets a taste predicted from who lives there (TabICL, fitted on the other 70% using January, April and July),
and it is scored on their real purchases in October and December.
Tesco data has no time of day and no personas, so this tests location and what is bought. Hours and personas are
tested on the household panel (backtest.py).      Run: python -m backend.uk_backtest      (about 4 minutes)
"""
import json
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from . import catchment, retail, store_sim, stores, uk_personas
from .config import CACHE, DATA

WEEKDAY, WEEKEND = date(2026, 10, 6), date(2026, 10, 10)        # a Tuesday and a Saturday; a week = 4 of the first + 3 of the second
SKIP = {"store cupboard"}                                       # no clean Tesco counterpart
CATS = uk_personas.CATS


def run(seed: int = 0) -> dict:
    M = catchment.model()
    S, A, P, flow = M["stores"], M["areas"], M["P"], M["flow"]
    ids = pd.Index(A.area_id)
    rng = np.random.default_rng(seed)
    test = pd.Index(rng.choice(ids, int(0.3 * len(ids)), replace=False))
    train = ids.difference(test)
    tr_m, te_m = uk_personas.TRAIN_MONTHS, uk_personas.TEST_MONTHS

    # ---- location input, with the held-out neighbourhoods' purchases hidden
    nb = uk_personas.Personas(train, tr_m, sensitive=False)
    Ytr = uk_personas._mean_periods(tr_m).loc[train]
    idx = pd.concat([Ytr, uk_personas.tab_predict(nb.weights(train), Ytr, nb.weights(test)).clip(0.2, 5)])       # area x 17 categories, index against London
    # UK category levels from the training neighbourhoods and months only
    L = retail.lines()
    L = L[L.category.isin(stores.TESCO_OF) & ~L.category.isin(SKIP)]
    us = L.category.map(stores.TESCO_OF).value_counts(normalize=True)
    raw = lambda per, who: sum(pd.read_csv(DATA / "tesco" / f"{m}_msoa_grocery.csv").set_index("area_id").reindex(who)[[f"f_{c}" for c in CATS]].set_axis(CATS, axis=1) for m in per) / len(per)
    uk_tr = raw(tr_m, train).mean()
    level = ((uk_tr[us.index] / uk_tr[us.index].sum()) / us).clip(0.3, 3.5)
    lvl = {c: float(level[k]) for c, k in stores.TESCO_OF.items() if c not in SKIP}

    # ---- run the product engine for every Tesco store
    tesco = S.index[S.retailer == "Tesco"]
    mix, cache = {}, CACHE / f"uk_backtest_mixes_{seed}.parquet"
    if cache.exists():
        mix = pd.read_parquet(cache).T.to_dict("series")
    for j in ([] if mix else tesco):
        sid = S.at[j, "id"]
        c = pd.Series(catchment.of(sid))
        c = c[c.index.isin(idx.index)]
        taste = {cat: float((idx.loc[c.index, k] * c).sum() / c.sum()) * lvl.get(cat, 1.0) for cat, k in stores.TESCO_OF.items()}
        u = pd.Series(0.0, index=CATS)
        for d, w in ((WEEKDAY, 4), (WEEKEND, 3)):
            cells = pd.DataFrame(store_sim.simulate(sid, d, taste=taste)["cells"])
            cells = cells[~cells.category.isin(SKIP) & cells.category.isin(stores.TESCO_OF)]
            u = u.add(cells.groupby(cells.category.map(stores.TESCO_OF)).units.sum() * w, fill_value=0)
        mix[j] = u
    mixes = pd.DataFrame(mix).T.reindex(columns=CATS).fillna(0)                 # store x category, units in a week
    mixes.to_parquet(cache)
    store_week = mixes.sum(1)
    shares = mixes.div(store_week, axis=0)

    # ---- trace back to where the shoppers live
    F = pd.DataFrame(flow[:, tesco], index=ids, columns=tesco)                 # residents of area i using Tesco store j
    no_tesco = int((F.loc[test].sum(1) == 0).sum())
    test = test[(F.loc[test].sum(1) > 0).values]                                # a neighbourhood with no Tesco within reach has nothing to compare
    pred = (F.values @ shares.values) / np.maximum(F.values.sum(1, keepdims=True), 1e-9)
    pred = pd.DataFrame(pred, index=ids, columns=CATS)
    cols = [c for c in CATS if c != "sauces"]                                   # "sauces" is where store cupboard would map
    pred = pred[cols].div(pred[cols].sum(1), axis=0)
    act = raw(te_m, ids)[cols]
    act = act.div(act.sum(1), axis=0)
    uncal = pred.loc[test]
    # level calibration: scale each category so the engine's average basket over the TRAINING neighbourhoods and months
    # equals their real average basket. One number per category; the held-out neighbourhoods play no part in it.
    act_tr = raw(tr_m, train)[cols]
    act_tr = act_tr.div(act_tr.sum(1), axis=0).mean()
    factor = act_tr / pred.loc[train].mean()
    pred = (pred * factor).div((pred * factor).sum(1), axis=0)
    (CACHE / "uk_level_calibration.json").write_text(json.dumps({k: round(float(v), 4) for k, v in factor.items()}, indent=1))
    p, a = pred.loc[test], act.loc[test].fillna(act.mean())

    out = {"tesco_stores_simulated": len(tesco), "simulations": len(tesco) * 2, "neighbourhoods": len(ids), "held_out_neighbourhoods": len(test), "held_out_with_no_tesco_within_3km": no_tesco,
           "fitted_on_months": tr_m, "scored_on_months": te_m, "categories_compared": len(cols)}
    # 1. what a neighbourhood buys: the basket
    within = [float(np.corrcoef(p.loc[i], a.loc[i])[0, 1]) for i in test]
    london = act.loc[train].mean()
    us_mix = (us.reindex(cols) / us.reindex(cols).sum())
    out["basket mix per held-out neighbourhood (16 category shares)"] = {
        "engine": {"mean_correlation": round(float(np.mean(within)), 3), "mean_gap_share_points": round(float((p - a).abs().mean().mean() * 100), 2)},
        "engine before level calibration": {"mean_correlation": round(float(np.mean([np.corrcoef(uncal.loc[i], a.loc[i])[0, 1] for i in test])), 3),
                                            "mean_gap_share_points": round(float((uncal - a).abs().mean().mean() * 100), 2)},
        "baseline: every neighbourhood gets the London average": {"mean_correlation": round(float(np.mean([np.corrcoef(london, a.loc[i])[0, 1] for i in test])), 3),
                                                                  "mean_gap_share_points": round(float((a - london).abs().mean().mean() * 100), 2)},
        "baseline: the US panel's basket, no UK data": {"mean_correlation": round(float(np.mean([np.corrcoef(us_mix, a.loc[i])[0, 1] for i in test])), 3),
                                                       "mean_gap_share_points": round(float((a - us_mix).abs().mean().mean() * 100), 2)}}
    # 2. how neighbourhoods differ from each other
    pi, ai = p / pred.loc[train].mean(), a / act.loc[train].mean()
    per = {c: round(float(spearmanr(pi[c], ai[c])[0]), 3) for c in cols}
    direct = idx.loc[test, cols]
    out["differences between held-out neighbourhoods (rank correlation per category)"] = {
        "engine": {"mean": round(float(np.mean(list(per.values()))), 3), "positive_categories": sum(v > 0 for v in per.values()), "per_category": per},
        "neighbourhood model alone, before stores and catchments": round(float(np.mean([spearmanr(direct[c], ai[c])[0] for c in cols])), 3),
        "baseline: London average": 0.0}
    # 3. how much: Tesco trips by residents of each neighbourhood
    T = pd.read_csv(DATA / "tesco" / "year_msoa_grocery.csv").set_index("area_id").reindex(ids)
    pred_trips = F.sum(1) * catchment.TRIPS_PER_PERSON_DAY * 365
    out["volume: Tesco trips a year by residents of each neighbourhood"] = {
        "rank_correlation_all": round(float(spearmanr(pred_trips, T.num_transactions)[0]), 3),
        "rank_correlation_held_out": round(float(spearmanr(pred_trips.loc[test], T.num_transactions.loc[test])[0]), 3),
        "note": "rank only: the Tesco file counts item-level Clubcard records, not baskets, so totals are not comparable; catchment settings were chosen on Tesco penetration in all areas"}
    out["store volumes simulated (units a week, Tesco stores)"] = {"median_units": round(float(store_week.median())), "by_format": S.loc[tesco].assign(u=store_week).groupby("format").u.median().round(0).to_dict()}
    (CACHE / "uk_backtest.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
