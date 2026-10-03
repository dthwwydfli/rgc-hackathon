"""Calibration against real sales, and the backtest that says whether any of this works.

Store: The Bread Basket, Edinburgh (till data, 159 days). Last 28 days held out.
Four forecasts of hourly units per category:
  last week          same hour, same weekday, 7 days earlier
  4-week mean        mean of the same hour and weekday over the 4 previous weeks
  US moments x 1     the US persona-moment shape with one fitted number per category (does the US shape transfer?)
  in-context model   TabICL/TabFM regressor reading the store's own history plus the US prior, weather and calendar
Run: python -m backend.calibrate
"""
import json

import numpy as np
import pandas as pd

from . import picks, tabular
from .config import CACHE, moment
from .data import bakery_hourly

HOLDOUT_DAYS, N_CONTEXT = 28, 6000
FEATS = ["hour", "wd", "weekend", "cat_code", "temp", "rain", "prior_us", "lag7", "mean4"]


def us_prior() -> pd.DataFrame:
    """Expected share of to-go purchases by hour, weekend and category from the US pick model."""
    G = picks.load()
    m = G["pick"].merge(G["mix"], on=["hour", "weekend", "persona"])
    m["w"] = m.p * m.share
    pr = m.groupby(["hour", "weekend", "category"], as_index=False).w.sum().merge(G["prop"][["hour", "weekend", "per_adult_day"]], on=["hour", "weekend"])
    pr["prior_us"] = pr.w * pr.per_adult_day
    return pr[["hour", "weekend", "category", "prior_us"]]


def frame() -> pd.DataFrame:
    b = bakery_hourly().merge(us_prior(), on=["hour", "weekend", "category"], how="left").fillna({"prior_us": 0})
    key = ["category", "hour", "date"]
    for k in (7, 14, 21, 28):                    # joined on calendar date, so closed days do not shift the weekday
        lag = b[key + ["units"]].rename(columns={"units": f"lag{k}"})
        lag["date"] = lag.date + pd.Timedelta(days=k)
        b = b.merge(lag, on=key, how="left")
    b["mean4"] = b[["lag7", "lag14", "lag21", "lag28"]].mean(axis=1)
    b["lag7"] = b.lag7.fillna(b.mean4)           # the shop was closed a week earlier: fall back to the 4-week mean
    b["cat_code"] = b.category.astype("category").cat.codes
    b["moment"] = [moment(h, bool(w)) for h, w in zip(b.hour, b.weekend)]
    return b


def backtest() -> dict:
    b = frame()
    days = sorted(b.date.unique())
    full = pd.date_range(days[0], days[-1])
    cut = days[-HOLDOUT_DAYS]
    tr, te = b[(b.date < cut) & b.mean4.notna()].copy(), b[b.date >= cut].copy()
    k = tr.groupby("category").apply(lambda g: g.units.sum() / max(g.prior_us.sum(), 1e-9))
    te["f_last_week"], te["f_mean4"] = te.lag7, te.mean4
    te["f_us"] = te.prior_us * te.category.map(k)
    ctx = tr.sample(min(N_CONTEXT, len(tr)), random_state=0)
    te["f_model"] = np.clip(tabular.regressor().fit(ctx[FEATS], ctx.units).predict(te[FEATS]), 0, None)
    te = te.dropna(subset=["f_last_week", "f_mean4"])

    def score(col, d=te):
        e = (d[col] - d.units).abs()
        return {"mae": round(float(e.mean()), 3), "wape": round(float(e.sum() / d.units.sum()), 3)}
    names = {"f_last_week": "last week", "f_mean4": "4-week mean", "f_us": "US moments x 1 number per category",
             "f_model": f"in-context model ({tabular.BACKEND})"}
    out = {"store": "The Bread Basket, Edinburgh", "train_days": int((pd.Series(days) < cut).sum()), "holdout_days": HOLDOUT_DAYS,
           "missing_days_in_period": int(len(full) - len(days)), "rows_scored": len(te), "categories": sorted(te.category.unique()),
           "units_in_holdout": int(te.units.sum()), "model": tabular.describe(), "context_rows": len(ctx),
           "overall": {names[c]: score(c) for c in names},
           "by_moment": {m: {names[c]: score(c, g)["wape"] for c in names} for m, g in te.groupby("moment")},
           "daily_total_wape": {names[c]: round(float((te.groupby("date")[c].sum() - te.groupby("date").units.sum()).abs().sum() / te.units.sum()), 3) for c in names}}
    (CACHE / "backtest.json").write_text(json.dumps(out, indent=1))
    te[["date", "hour", "moment", "category", "units", "temp", "rain", "f_last_week", "f_mean4", "f_us", "f_model"]].to_parquet(CACHE / "bakery_forecast.parquet")
    return out


def shrunk_ratio(actual: float, predicted: float, prior_weight: float = 20.0) -> float:
    """Calibration scalar pulled toward 1 when there is little evidence."""
    return float(np.clip((actual + prior_weight) / (predicted + prior_weight), 0.25, 4.0))




# ------------------------------------------------------------------ retail backtest (dunnhumby panel, last 8 weeks held out)
def retail_backtest(holdout_weeks: int = 8) -> dict:
    """Units per day, moment and product group across the panel's stores. The held-out weeks include Thanksgiving and
    Christmas, so this also tests whether calendar flags help. Run: python -m backend.calibrate retail"""
    from . import retail
    L = retail.lines()
    L = L[L.hour.isin(retail.HOURS)]
    L = L.assign(moment=[moment(h, bool(w)) for h, w in zip(L.hour, L.weekend)])
    g = L.groupby(["date", "moment", "group"]).size().rename("units")
    idx = pd.MultiIndex.from_product([pd.date_range(L.date.min(), L.date.max()), sorted(L.moment.unique()), retail.GROUPS], names=["date", "moment", "group"])
    b = g.reindex(idx, fill_value=0).reset_index()
    b["dow"] = b.date.dt.weekday
    b = b[~((b.moment == "social evening") & (b.dow < 4)) & ~((b.moment == "weekday evening") & (b.dow >= 4))]      # each evening moment exists on its own days
    b = pd.concat([b.reset_index(drop=True), retail.calendar_flags(b.date.reset_index(drop=True), retail.US_HOLIDAYS_2017)], axis=1)
    key = ["date", "moment", "group"]
    for k in (7, 14, 21, 28):
        lag = b[key + ["units"]].rename(columns={"units": f"lag{k}"})
        lag["date"] = lag.date + pd.Timedelta(days=k)
        b = b.merge(lag, on=key, how="left")
    b["mean4"] = b[["lag7", "lag14", "lag21", "lag28"]].mean(axis=1)
    b["lag7"] = b.lag7.fillna(b.mean4)
    b["m_code"], b["g_code"] = b.moment.astype("category").cat.codes, b.group.astype("category").cat.codes
    cut = b.date.max() - pd.Timedelta(weeks=holdout_weeks)
    tr, te = b[(b.date <= cut) & b.mean4.notna()], b[b.date > cut].dropna(subset=["mean4"]).copy()
    feats_plain, feats_cal = ["dow", "m_code", "g_code", "lag7", "mean4"], ["dow", "m_code", "g_code", "lag7", "mean4", "pre_holiday", "holiday"]
    ctx = tr.sample(min(N_CONTEXT, len(tr)), random_state=0)
    te["f_last_week"], te["f_mean4"] = te.lag7, te.mean4
    te["f_model"] = np.clip(tabular.regressor().fit(ctx[feats_plain], ctx.units).predict(te[feats_plain]), 0, None)
    te["f_model_cal"] = np.clip(tabular.regressor().fit(ctx[feats_cal], ctx.units).predict(te[feats_cal]), 0, None)
    names = {"f_last_week": "last week", "f_mean4": "4-week mean", "f_model": f"in-context model ({tabular.BACKEND})", "f_model_cal": f"in-context model + calendar flags ({tabular.BACKEND})"}
    wape = lambda d, c: round(float((d[c] - d.units).abs().sum() / d.units.sum()), 3)
    hol = te[(te.pre_holiday == 1) | (te.holiday == 1)]
    out = {"data": "dunnhumby The Complete Journey, all panel stores", "train_days": int(tr.date.nunique()), "holdout_days": int(te.date.nunique()),
           "cells_scored": len(te), "units_in_holdout": int(te.units.sum()), "context_rows": len(ctx), "model": tabular.describe(),
           "overall": {names[c]: wape(te, c) for c in names},
           "holiday_and_pre_holiday_days": {"days": int(hol.date.nunique()), **{names[c]: wape(hol, c) for c in names}},
           "by_moment": {m: {names[c]: wape(d, c) for c in names} for m, d in te.groupby("moment")}}
    (CACHE / "retail_backtest.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(retail_backtest() if "retail" in sys.argv else backtest(), indent=1))
