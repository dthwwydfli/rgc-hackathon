"""End-to-end backtest of the persona model on real till data.

Everything the model uses (persona assignment, trip rates, hour shapes, the TabICL pick grid, basket depth, category
split, calendar uplift) is rebuilt from weeks 1-40 of the dunnhumby panel only. It then predicts six later weeks
sampled from 42-52, including Thanksgiving and Christmas weeks, and is scored against what the same households bought.

The panel is treated as one store, so this tests who, when and what. It does not test location.
Run: python -m backend.backtest        (about 3 minutes)
"""
import json

import numpy as np
import pandas as pd

from . import retail, shopper_personas as sp, tabular
from .config import CACHE, moment

TRAIN_END, TEST_WEEKS = 40, [42, 44, 46, 47, 50, 52]
N_CONTEXT = 6000
DAYPART = lambda h: "morning" if h < 11 else "lunch" if h < 14 else "afternoon" if h < 17 else "evening"


def run() -> dict:
    H = retail.HOURS
    R = sp.raw()
    h = sp.traits(R[R.week <= TRAIN_END], min_trips=15)
    h["persona"] = sp.assign(h)
    cent = h.groupby("persona")[sp.TRAITS].mean().add_prefix("p_")
    B = retail.all_baskets().merge(h[["persona"]], left_on="household_id", right_index=True)
    L = retail.lines()
    L = L[L.hour.isin(H)].drop(columns=["big_store"]).merge(B[["basket_id", "persona", "big_store"]], on="basket_id")
    L["daypart"] = L.hour.map(DAYPART)
    Btr, Bte, Ltr, Lte = B[B.week <= TRAIN_END], B[B.week.isin(TEST_WEEKS)], L[L.week <= TRAIN_END], L[L.week.isin(TEST_WEEKS)]
    hh = h.persona.value_counts()
    P = sorted(hh.index)

    # ---- everything below is learned from the training weeks only
    ndays = Btr.drop_duplicates("date").groupby("dow").size()
    rate = Btr.groupby(["persona", "dow"]).size().rename("n").reset_index()
    rate["rate"] = rate.n / (rate.persona.map(hh) * rate.dow.map(ndays))            # trips per household per day
    rate = rate[["persona", "dow", "rate"]]
    pbig = Btr.groupby("persona").big_store.mean().rename("p_big").reset_index()
    hs = pd.crosstab([Btr.persona, Btr.weekend, Btr.big_store], Btr.hour).reindex(columns=H, fill_value=0) + 2
    hs = hs.div(hs.sum(1), axis=0).stack().rename("hshare").reset_index()
    cal = Btr.groupby(["date", "pre_holiday", "holiday", "dow"]).size().rename("trips").reset_index()
    cal["idx"] = cal.trips / cal.dow.map(cal[(cal.pre_holiday == 0) & (cal.holiday == 0)].groupby("dow").trips.mean())
    up_pre, up_hol = float(cal[cal.pre_holiday == 1].idx.mean()), float(cal[cal.holiday == 1].idx.mean())
    feats = list(cent.columns) + ["hour", "weekend", "pre_holiday", "big_store"]
    ctx = Btr.merge(cent, left_on="persona", right_index=True).sample(N_CONTEXT, random_state=0)
    q = cent.reset_index().merge(pd.DataFrame({"hour": H}), how="cross").merge(pd.DataFrame({"weekend": [0, 1]}), how="cross") \
        .merge(pd.DataFrame({"pre_holiday": [0, 1]}), how="cross").merge(pd.DataFrame({"big_store": [0, 1]}), how="cross")
    G = q[["persona", "hour", "weekend", "pre_holiday", "big_store"]].copy()
    for g in retail.GROUPS:
        m = tabular.classifier().fit(ctx[feats], ctx[g])
        G[g] = m.predict_proba(q[feats])[:, list(m.classes_).index(1)]
    attach = G.melt(id_vars=["persona", "hour", "weekend", "pre_holiday", "big_store"], var_name="group", value_name="attach")
    lg = Ltr.groupby(["basket_id", "persona", "big_store", "group"], observed=True).size().rename("n").reset_index()
    depth = lg.groupby(["persona", "big_store", "group"]).n.mean().rename("depth").reset_index()
    allc = Ltr.groupby(["group", "category"]).size().rename("n_all").reset_index()
    allc["share_all"] = allc.n_all / allc.groupby("group").n_all.transform("sum")
    w = pd.MultiIndex.from_product([P, ["morning", "lunch", "afternoon", "evening"]], names=["persona", "daypart"]).to_frame(index=False).merge(allc, how="cross") \
        .merge(Ltr.groupby(["persona", "daypart", "group", "category"]).size().rename("n").reset_index(), how="left").fillna({"n": 0})
    w["within"] = (w.n + 30 * w.share_all) / (w.groupby(["persona", "daypart", "group"]).n.transform("sum") + 30)

    # ---- predict every test day
    days = Bte.drop_duplicates("date")[["date", "dow", "weekend", "pre_holiday", "holiday"]]
    days["uplift"] = np.where(days.pre_holiday == 1, up_pre, 1.0) * np.where(days.holiday == 1, up_hol, 1.0)
    T = days.merge(rate, on="dow").merge(pbig, on="persona").merge(pd.DataFrame({"big_store": [0, 1]}), how="cross")
    T["day_trips"] = T.persona.map(hh) * T.rate * np.where(T.big_store == 1, T.p_big, 1 - T.p_big) * T.uplift
    T = T.merge(hs, on=["persona", "weekend", "big_store"])
    T["trips"] = T.day_trips * T.hshare
    U = T.merge(attach, on=["persona", "hour", "weekend", "pre_holiday", "big_store"]).merge(depth, on=["persona", "big_store", "group"], how="left").fillna({"depth": 1.0})
    U["daypart"] = U.hour.map(DAYPART)
    U = U.merge(w[["persona", "daypart", "group", "category", "within"]], on=["persona", "daypart", "group"])
    U["pred"] = U.trips * U.attach * U.depth * U.within
    U["moment"] = [moment(a, bool(b)) for a, b in zip(U.hour, U.weekend)]
    Lte = Lte.assign(moment=[moment(a, bool(b)) for a, b in zip(Lte.hour, Lte.weekend)])
    Ltr = Ltr.assign(moment=[moment(a, bool(b)) for a, b in zip(Ltr.hour, Ltr.weekend)])
    wape = lambda a, p: round(float((a - p).abs().sum() / a.sum()), 3)
    corr = lambda a, p: round(float(np.corrcoef(a, p)[0, 1]), 3)
    out = {"train_weeks": f"1-{TRAIN_END}", "test_weeks": TEST_WEEKS, "test_days": int(days.date.nunique()), "holiday_or_pre_holiday_days": int(((days.pre_holiday + days.holiday) > 0).sum()),
           "households": len(h), "persona_sizes": hh.to_dict(), "lines_in_test_weeks": len(Lte), "model": tabular.describe(), "calendar_uplift_learned": {"pre_holiday": round(up_pre, 3), "holiday": round(up_hol, 3)}}

    # 1. totals
    out["total_units"] = {"predicted": round(float(U.pred.sum())), "actual": len(Lte), "ratio": round(float(U.pred.sum() / len(Lte)), 3)}
    out["total_trips"] = {"predicted": round(float(T.trips.sum())), "actual": len(Bte), "ratio": round(float(T.trips.sum() / len(Bte)), 3)}
    # 2. when: trips by persona and hour, summed over the test days
    a = Bte.groupby(["persona", "hour"]).size().rename("a")
    p = T.groupby(["persona", "hour"]).trips.sum().rename("p")
    j = pd.concat([a, p], axis=1).fillna(0)
    out["when: trips by persona and hour"] = {"cells": len(j), "error_share": wape(j.a, j.p), "correlation": corr(j.a, j.p)}
    j2 = j.groupby("hour").sum()
    out["when: trips by hour, all personas"] = {"error_share": wape(j2.a, j2.p), "correlation": corr(j2.a, j2.p)}
    # 3. what: units by persona, moment and category, summed over the test days
    a = Lte.groupby(["persona", "moment", "category"]).size().rename("a")
    p = U.groupby(["persona", "moment", "category"]).pred.sum().rename("p")
    j = pd.concat([a, p], axis=1).fillna(0)
    # baselines for the same cells
    dtypes = days.groupby("weekend").size()
    hist = (Ltr.groupby(["persona", "weekend", "moment", "category"]).size() / Ltr.drop_duplicates("date").groupby("weekend").size()).rename("per_day").reset_index()
    hist["h"] = hist.per_day * hist.weekend.map(dtypes)
    j["history"] = hist.groupby(["persona", "moment", "category"]).h.sum().reindex(j.index).fillna(0)
    tot = U.groupby(["moment", "category"]).pred.sum()
    share = (T.groupby("persona").trips.sum() / T.trips.sum())
    j["no_persona"] = [tot.get((m, c), 0.0) * share[pp] for pp, m, c in j.index]
    out["what: units by persona, moment and category"] = {"cells": len(j), "model": {"error_share": wape(j.a, j.p), "correlation": corr(j.a, j.p)},
        "baseline: each persona buys the average mix": {"error_share": wape(j.a, j.no_persona), "correlation": corr(j.a, j.no_persona)},
        "baseline: the persona's own average from weeks 1-40": {"error_share": wape(j.a, j.history), "correlation": corr(j.a, j.history)}}
    # per persona: how well is its mix across categories predicted (share of its units)
    per = {}
    for pp, g in j.groupby(level="persona"):
        c = g.groupby(level="category").sum()
        per[pp] = {"units": int(c.a.sum()), "predicted": int(c.p.sum()), "category_mix_correlation": corr(c.a / c.a.sum(), c.p / c.p.sum()),
                   "lift_correlation": corr(c.a / c.a.sum() - j.groupby(level="category").a.sum() / j.a.sum(), c.p / c.p.sum() - j.groupby(level="category").p.sum() / j.p.sum())}
    out["by persona"] = per
    # 4. day by day: units by date, moment and group, against time-series baselines
    Lall = L.assign(moment=[moment(a, bool(b)) for a, b in zip(L.hour, L.weekend)])
    act = Lall.groupby(["date", "moment", "group"]).size().rename("units")
    idx = pd.MultiIndex.from_product([pd.date_range(L.date.min(), L.date.max()), sorted(Lall.moment.unique()), retail.GROUPS], names=["date", "moment", "group"])
    act = act.reindex(idx, fill_value=0).reset_index()
    for k in (7, 14, 21, 28):
        lag = act[["date", "moment", "group", "units"]].rename(columns={"units": f"lag{k}"})
        lag["date"] = lag.date + pd.Timedelta(days=k)
        act = act.merge(lag, on=["date", "moment", "group"], how="left")
    act["mean4"] = act[["lag7", "lag14", "lag21", "lag28"]].mean(axis=1)
    pred = U.groupby(["date", "moment", "group"]).pred.sum().rename("pred").reset_index()
    d = pred.merge(act, on=["date", "moment", "group"], how="left").merge(days[["date", "pre_holiday", "holiday"]], on="date")
    hol = d[(d.pre_holiday + d.holiday) > 0]
    out["day by day: units by date, moment and product group"] = {"cells": len(d),
        "persona model (knows nothing after week 40)": wape(d.units, d.pred), "same weekday last week": wape(d.units, d.lag7.fillna(d.mean4)), "mean of last 4 weeks": wape(d.units, d.mean4),
        "holiday days": {"days": int(hol.date.nunique()), "persona model": wape(hol.units, hol.pred), "same weekday last week": wape(hol.units, hol.lag7.fillna(hol.mean4)), "mean of last 4 weeks": wape(hol.units, hol.mean4)}}
    dd = d.groupby("date")[["units", "pred", "mean4"]].sum()
    out["day by day: total units per day"] = {"persona model": wape(dd.units, dd.pred), "mean of last 4 weeks": wape(dd.units, dd.mean4)}
    (CACHE / "backtest_chain.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "by persona"}, indent=1))
    print(pd.DataFrame(r["by persona"]).T.to_string())
