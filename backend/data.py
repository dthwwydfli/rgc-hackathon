"""Loaders. Everything heavy is cached as parquet under data/cache/."""
import json
import re
from datetime import date as Date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import CACHE, DATA, HOURS, PERSONA_FIELDS, TOGO_SOURCES, moment, persona_of

# ---------------------------------------------------------------- food categories (USDA food codes)
def food_category(code: float, desc: str) -> str:
    c, d = str(int(code)), desc.lower()
    has = lambda *w: any(x in d for x in w)
    if c.startswith("94"): return "water"
    if c.startswith("921"): return "coffee"
    if c.startswith("923"): return "tea"
    if c.startswith("924"): return "soft drink"
    if c.startswith("953") or has("energy drink", "sports drink"): return "energy & sports drink"
    if c.startswith(("951", "952")) or has("protein shake", "nutritional drink"): return "protein & nutrition shake"
    if c.startswith(("925", "64")): return "juice & fruit drink"
    if c.startswith("93"): return "alcohol"
    if c.startswith("537") or (c.startswith("53") and has("bar") and has("nutrition", "protein", "granola", "cereal")): return "protein & cereal bar"
    if has("sandwich", "burger", "wrap", "burrito", "taco", "hot dog", "sub,", "quesadilla"): return "sandwich & wrap"
    if has("pizza"): return "pizza"
    if has("soup"): return "soup"
    if c.startswith("114"): return "yogurt"
    if c.startswith("11"): return "milk & dairy drink"
    if c.startswith("13"): return "ice cream & dessert"
    if c.startswith("3"): return "eggs"
    if c.startswith(("42", "43")): return "nuts & seeds"
    if c.startswith(("51", "52")): return "bread & bagel"
    if c.startswith(("53", "55")): return "cake, cookie & pastry"
    if c.startswith("54") or (c.startswith("71") and has("chips")): return "crisps & salty snacks"
    if c.startswith("57"): return "cereal"
    if c.startswith("71"): return "fries & potato"
    if c.startswith(("61", "62", "63")): return "fruit"
    if c.startswith("7"): return "salad & veg"
    if c.startswith(("917", "918")): return "confectionery"
    if c.startswith(("2", "41", "56", "58")): return "hot meal"
    return "other"


@lru_cache(maxsize=1)
def items() -> pd.DataFrame:
    """One row per food item eaten by an adult (both recall days), with persona, moment and category."""
    f = CACHE / "items.parquet"
    if f.exists():
        return pd.read_parquet(f)
    N = DATA / "nhanes"
    demo = pd.read_sas(N / "DEMO_L.xpt").merge(pd.read_sas(N / "WHQ_L.xpt")[["SEQN", "WHQ070"]], how="left")
    demo = demo.merge(pd.read_sas(N / "PAQ_L.xpt"), how="left")
    demo = demo[demo.RIDAGEYR >= 18].copy()
    demo["persona"] = demo.apply(persona_of, axis=1)
    fcd = pd.read_sas(N / "DRXFCD_L.xpt")
    fcd["desc"] = fcd.DRXFCLD.str.decode("latin-1")
    days = []
    for n in (1, 2):
        d = pd.read_sas(N / f"DR{n}IFF_L.xpt")
        d = d.rename(columns=lambda c: c.replace(f"DR{n}", "DR"))
        d["recall_day"] = n
        days.append(d[["SEQN", "recall_day", "DR_020", "DR_030Z", "DRFS", "DR_040Z", "DRDAY", "DRIFDCD",
                       "DRIKCAL", "DRIPROT", "DRISUGR", "DRICAFF", "DRIFIBE", "DRISODI"]])
    t = pd.concat(days).dropna(subset=["DRIKCAL"])
    t = t.merge(fcd[["DRXFDCD", "desc"]], left_on="DRIFDCD", right_on="DRXFDCD").merge(demo[["SEQN", "persona"] + PERSONA_FIELDS], on="SEQN")
    t["hour"] = (t.DR_020 // 3600).astype(int)
    t["dow"] = t.DRDAY.astype(int)                       # 1 = Sunday ... 7 = Saturday
    t["weekend"] = t.dow.isin([1, 6, 7]).astype(int)     # Fri-Sun
    t["moment"] = [moment(h, bool(w)) for h, w in zip(t.hour, t.weekend)]
    t["togo"] = ((t.DR_040Z == 2) | t.DRFS.isin(TOGO_SOURCES)).astype(int)
    t["category"] = [food_category(c, s) for c, s in zip(t.DRIFDCD, t.desc)]
    t["caffeinated"] = (t.DRICAFF >= 30).astype(int)
    t["high_protein"] = (t.DRIPROT >= 10).astype(int)
    t["sugary"] = ((t.DRISUGR * 4 >= 0.4 * t.DRIKCAL) & (t.DRIKCAL >= 20)).astype(int)
    t = t.drop(columns=["DRXFDCD"]).reset_index(drop=True)
    t.to_parquet(f)
    return t


def togo_items() -> pd.DataFrame:
    t = items()
    keep = (t.togo == 1) & (t.category != "other") & t.hour.isin(HOURS)
    keep &= ~((t.category == "salad & veg") & (t.DRIKCAL < 30))   # burger toppings are recorded as separate items
    return t[keep].reset_index(drop=True)


# ---------------------------------------------------------------- calendar
@lru_cache(maxsize=1)
def bank_holidays() -> dict:
    j = json.loads((DATA / "context" / "uk_bank_holidays.json").read_text())
    return {e["date"]: e["title"] for e in j["england-and-wales"]["events"]}


def day_info(d: Date) -> dict:
    hol = bank_holidays().get(d.isoformat())
    wd = d.weekday()                                      # 0 = Monday
    daytype = "SUN" if hol else ["MON", "TWT", "TWT", "TWT", "FRI", "SAT", "SUN"][wd]
    return {"date": d.isoformat(), "weekday": d.strftime("%A"), "daytype": daytype, "holiday": hol,
            "weekend": int(wd >= 4 or bool(hol)),         # Fri-Sun, matching the pick model
            "dow": (wd + 1) % 7 + 1}                      # NHANES coding, 1 = Sunday


@lru_cache(maxsize=1)
def weather() -> pd.DataFrame:
    f = DATA / "context" / "london_weather_forecast.json"
    if not f.exists():
        return pd.DataFrame(columns=["time", "temp", "rain"])
    h = json.loads(f.read_text())["hourly"]
    return pd.DataFrame({"time": pd.to_datetime(h["time"]), "temp": h["temperature_2m"], "rain": h["precipitation"]})


# ---------------------------------------------------------------- location: TfL
@lru_cache(maxsize=1)
def station_profiles() -> pd.DataFrame:
    """Typical exits per station, day type and hour (NUMBAT 2025)."""
    f = CACHE / "station_profiles.parquet"
    if f.exists():
        return pd.read_parquet(f)
    out = []
    for dt in ["MON", "TWT", "FRI", "SAT", "SUN"]:
        p = DATA / "tfl" / f"NBT25{dt}_Outputs.xlsx"
        if not p.exists():
            continue
        try:
            e = pd.read_excel(p, sheet_name="Station_Exits", header=2)
        except Exception:
            continue
        q = [c for c in e.columns if isinstance(c, str) and len(c) == 9 and c[:4].isdigit()]
        m = e.melt(id_vars=["Station"], value_vars=q, var_name="slot", value_name="exits")
        m["hour"] = m.slot.str[:2].astype(int)
        g = m.groupby(["Station", "hour"], as_index=False).exits.sum()
        g["daytype"] = dt
        out.append(g)
    r = pd.concat(out).rename(columns={"Station": "station"})
    r.to_parquet(f)
    return r


def _norm(name: str) -> str:
    """The two TfL files spell stations differently ("London Bridge LU" vs "London Bridge")."""
    name = re.sub(r"\b(lu|nr|dlr|el|lo)\b", "", name.lower().replace("&", "and"))
    return re.sub(r"[^a-z]", "", name)


@lru_cache(maxsize=1)
def daily_taps() -> pd.DataFrame:
    t = pd.read_csv(DATA / "tfl" / "StationFootfall_2025_2026.csv")
    t["date"] = pd.to_datetime(t.TravelDate.astype(str))
    t = t.rename(columns={"Station": "station", "ExitTapCount": "exits", "EntryTapCount": "entries"})
    t["key"] = t.station.map(_norm).replace({"bank": "bankandmonument", "monument": "bankandmonument"})   # one complex in NUMBAT
    return t.groupby(["key", "date"], as_index=False)[["exits", "entries"]].sum()


def footfall(station: str, d: Date) -> pd.DataFrame:
    """People leaving the station per hour on a date: typical shape x that day's (or recent) volume."""
    info = day_info(d)
    prof = station_profiles()
    types = set(prof.daytype)
    dt = info["daytype"] if info["daytype"] in types else ("SAT" if info["daytype"] == "SUN" else "TWT")
    p = prof[(prof.station == station) & (prof.daytype == dt)].set_index("hour").exits.reindex(HOURS).fillna(0)
    taps = daily_taps()
    s = taps[taps.key == _norm(station)]
    scale, basis = 1.0, "typical 2025 day (no tap data for this station name)"
    if len(s) and p.sum() > 0:
        day = s[s.date == pd.Timestamp(d)]
        if len(day):
            scale, basis = float(day.exits.iloc[0]) / p.sum(), "actual taps that day"
        else:
            recent = s[(s.date.dt.weekday == d.weekday()) & (s.date < pd.Timestamp(d))].tail(6)
            if len(recent):
                scale, basis = float(recent.exits.mean()) / p.sum(), f"mean of last {len(recent)} {info['weekday']}s"
        scale = float(np.clip(scale, 0.2, 3.0))
    return pd.DataFrame({"hour": HOURS, "people": (p.values * scale).round(0), "basis": basis, "profile": dt})


def stations() -> list:
    return sorted(station_profiles().station.unique())


# ---------------------------------------------------------------- real sales: Edinburgh bakery
BAKERY_MAP = {"Coffee": "coffee", "Tea": "tea", "Hot chocolate": "milk & dairy drink", "Juice": "juice & fruit drink",
              "Coke": "soft drink", "Mineral water": "water", "Smoothies": "juice & fruit drink",
              "Bread": "bread & bagel", "Toast": "bread & bagel", "Farm House": "bread & bagel", "Baguette": "bread & bagel",
              "Pastry": "cake, cookie & pastry", "Medialuna": "cake, cookie & pastry", "Cake": "cake, cookie & pastry",
              "Cookies": "cake, cookie & pastry", "Muffin": "cake, cookie & pastry", "Scone": "cake, cookie & pastry",
              "Brownie": "cake, cookie & pastry", "Alfajores": "cake, cookie & pastry", "Scandinavian": "cake, cookie & pastry",
              "Sandwich": "sandwich & wrap", "Chicken Stew": "hot meal", "Soup": "soup", "Spanish Brunch": "hot meal",
              "Frittata": "eggs", "Truffles": "confectionery", "Fudge": "confectionery"}


@lru_cache(maxsize=1)
def bakery_hourly() -> pd.DataFrame:
    """Units sold per date, hour and category, zero-filled over opening hours."""
    b = pd.read_csv(DATA / "bakery" / "BreadBasket_DMS.csv")
    b = b[b.Item != "NONE"]
    b["category"] = b.Item.map(BAKERY_MAP)
    b = b.dropna(subset=["category"])
    b["hour"] = pd.to_datetime(b.Time, format="%H:%M:%S").dt.hour
    b = b[b.hour.between(8, 17)]
    g = b.groupby(["Date", "hour", "category"]).size().rename("units")
    idx = pd.MultiIndex.from_product([sorted(b.Date.unique()), range(8, 18), sorted(b.category.unique())], names=["Date", "hour", "category"])
    g = g.reindex(idx, fill_value=0).reset_index()
    g["date"] = pd.to_datetime(g.Date)
    w = json.loads((DATA / "context" / "edinburgh_weather_2016_2017.json").read_text())["hourly"]
    wx = pd.DataFrame({"t": pd.to_datetime(w["time"]), "temp": w["temperature_2m"], "rain": w["precipitation"]})
    wx["date"], wx["hour"] = wx.t.dt.normalize(), wx.t.dt.hour
    g = g.merge(wx[["date", "hour", "temp", "rain"]], on=["date", "hour"], how="left")
    g["wd"] = g.date.dt.weekday
    g["weekend"] = (g.wd >= 4).astype(int)
    return g


@lru_cache(maxsize=1)
def bakery_baskets() -> pd.DataFrame:
    """Items per till transaction with its hour and day type: the stand-in for time in store."""
    b = pd.read_csv(DATA / "bakery" / "BreadBasket_DMS.csv")
    b = b[b.Item != "NONE"]
    b["hour"] = pd.to_datetime(b.Time, format="%H:%M:%S").dt.hour
    b["weekend"] = (pd.to_datetime(b.Date).dt.weekday >= 4).astype(int)
    return b.groupby(["Transaction", "hour", "weekend"]).size().rename("n").reset_index()
