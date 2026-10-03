"""UK shopper personas, built so that they explain real UK purchases.

Unit of evidence: 983 London neighbourhoods (MSOAs). For each we know who lives there (London MSOA Atlas, 2011 Census
and related, OGL) and what they bought at Tesco (Tesco Grocery 1.0, Clubcard, CC BY 4.0).

    1. learn demographics -> purchase profile on some areas and some months            (ridge regression)
    2. cluster areas by the purchase profile their demographics predict -> 28 personas  (k-means)
    3. a persona = who they are (mean demographics) + what they buy (mean real purchases of its areas)
    4. any area, seen or not, is a mixture of personas; its predicted purchases are the mixture of persona profiles

Test (fast: 983 rows): fit on 70% of areas using January, April and July; score on the other 30% using October and December.
Run: python -m backend.uk_personas        (fit, test, write data/cache/uk_*.parquet and uk_eval.json)
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .config import CACHE, DATA
from .stores import TESCO_OF

K = 28
CATS = sorted(set(TESCO_OF.values()))
TRAIN_MONTHS, TEST_MONTHS = ["Jan", "Apr", "Jul"], ["Oct", "Dec"]
SENSITIVE = ("ethnic", "religion", "born")          # census facts about protected characteristics; tested with and without


@lru_cache(maxsize=1)
def areas() -> pd.DataFrame:
    """One row per London MSOA: shares and rates only, so area size does not drive anything."""
    d = pd.read_excel(DATA / "london" / "msoa-data.xls", sheet_name="iadatasheet1", header=None)
    v = d.iloc[3:].reset_index(drop=True)
    v = v[v[0].astype(str).str.startswith("E02")]
    n = lambda i: pd.to_numeric(v[i], errors="coerce")
    pop, quals = n(2), sum(n(i) for i in range(131, 138))
    X = pd.DataFrame({"area_id": v[0].values, "name": v[1].values})
    f = {"age 0-15": n(3) / pop, "age 16-29": n(4) / pop, "age 30-44": n(5) / pop, "age 45-64": n(6) / pop, "age 65+": n(7) / pop,
         "couples with children": n(48), "couples without children": n(49), "lone parents": n(50), "living alone": n(51),
         "own outright": n(95), "own with mortgage": n(96), "social renters": n(97), "private renters": n(98),
         "flats": n(110), "detached houses": n(107), "semi-detached": n(108), "terraced": n(109), "density": n(112),
         "house price": np.log(n(113)), "household income": np.log(n(148)), "income deprived": n(149), "pension credit": n(150),
         "no qualifications": n(131) / quals, "degree educated": n(136) / quals, "students": n(138) / pop,
         "economically active": n(142), "unemployment": n(143), "very good health": n(166), "bad health": n(169),
         "adult obesity": n(175), "no car": n(189), "cars per household": n(194),
         "ethnic: white": n(59), "ethnic: asian": n(61), "ethnic: black": n(62), "born outside UK": n(68),
         "religion: christian": n(82), "religion: hindu": n(84), "religion: jewish": n(85), "religion: muslim": n(86), "religion: none": n(89)}
    for k, s in f.items():
        X[k] = s.values
    X = X.set_index("area_id")
    X.iloc[:, 1:] = X.iloc[:, 1:].fillna(X.iloc[:, 1:].median())
    return X


def features(sensitive: bool) -> list:
    return [c for c in areas().columns if c != "name" and (sensitive or not c.lower().startswith(SENSITIVE))]


@lru_cache(maxsize=16)
def purchases(period: str = "year") -> pd.DataFrame:
    """Category index per area for a period: the area's share of each of 17 categories over the London mean share."""
    t = pd.read_csv(DATA / "tesco" / f"{period}_msoa_grocery.csv").set_index("area_id")
    y = t[[f"f_{c}" for c in CATS]].copy()
    y.columns = CATS
    y = y.div(y.sum(1), axis=0)
    return (y / y.mean()).reindex(pd.read_csv(DATA / "tesco" / "year_msoa_grocery.csv").area_id).fillna(1.0)   # an area with no data in a month sits at the average


def _mean_periods(periods: list) -> pd.DataFrame:
    return sum(purchases(p) for p in periods) / len(periods)


class Personas:
    """Fitted on a set of areas and periods; can place any area."""

    def __init__(self, ids, periods, sensitive=False, k=K, alpha=10.0, cluster_on="predicted"):
        self.cols = features(sensitive)
        X, Y = areas().loc[ids, self.cols], _mean_periods(periods).loc[ids]
        self.sx = StandardScaler().fit(X)
        self.reg = Ridge(alpha=alpha).fit(self.sx.transform(X), Y)
        self.cluster_on = cluster_on
        Z = self._space(X)
        self.sz = StandardScaler().fit(Z)
        self.km = KMeans(k, n_init=10, random_state=0).fit(self.sz.transform(Z))
        lab = pd.Series(self.km.labels_, index=ids)
        self.profile = Y.groupby(lab).mean()                       # what each persona buys: real purchases of its areas
        self.demo = X.groupby(lab).mean()                          # who they are
        self.size = lab.value_counts().sort_index()
        d = np.sqrt(((self.sz.transform(Z)[:, None, :] - self.km.cluster_centers_[None]) ** 2).sum(-1))
        self.tau = float(np.median(d.min(1))) or 1.0               # softness: typical distance to the nearest persona

    def _space(self, X):
        return self.reg.predict(self.sx.transform(X)) if self.cluster_on == "predicted" else self.sx.transform(X)

    def weights(self, ids) -> pd.DataFrame:
        """Each area as a mixture of personas."""
        Z = self.sz.transform(self._space(areas().loc[ids, self.cols]))
        d2 = ((Z[:, None, :] - self.km.cluster_centers_[None]) ** 2).sum(-1)
        w = np.exp(-d2 / (2 * self.tau ** 2))
        return pd.DataFrame(w / w.sum(1, keepdims=True), index=ids, columns=self.profile.index)

    def predict(self, ids, soft=True) -> pd.DataFrame:
        w = self.weights(ids)
        if not soft:
            w = pd.DataFrame(np.eye(w.shape[1])[w.values.argmax(1)], index=ids, columns=w.columns)
        return pd.DataFrame(w.values @ self.profile.values, index=ids, columns=CATS)

    def direct(self, ids) -> pd.DataFrame:
        return pd.DataFrame(self.reg.predict(self.sx.transform(areas().loc[ids, self.cols])), index=ids, columns=CATS)


def tab_predict(Xtr: pd.DataFrame, Ytr: pd.DataFrame, Xte: pd.DataFrame) -> pd.DataFrame:
    """In-context tabular model, one pass per category: known areas are the context, new areas are the query."""
    from . import tabular
    return pd.DataFrame({c: tabular.regressor().fit(Xtr, Ytr[c]).predict(Xte) for c in CATS}, index=Xte.index)


def _score(pred: pd.DataFrame, actual: pd.DataFrame) -> dict:
    r = {c: round(float(spearmanr(pred[c], actual[c])[0]), 3) for c in CATS}
    prof = [float(np.corrcoef(pred.loc[i], actual.loc[i])[0, 1]) for i in pred.index]   # per area, across the 17 categories
    return {"mean_r_across_areas": round(float(np.mean(list(r.values()))), 3), "positive": sum(v > 0 for v in r.values()),
            "mean_r_within_area": round(float(np.mean(prof)), 3), "per_category": r}


def evaluate(seed: int = 0) -> dict:
    ids = areas().index.intersection(purchases("year").index)
    rng = np.random.default_rng(seed)
    test = pd.Index(rng.choice(ids, int(0.3 * len(ids)), replace=False))
    train = ids.difference(test)
    actual = _mean_periods(TEST_MONTHS).loc[test]
    out = {"areas": len(ids), "train_areas": len(train), "test_areas": len(test), "train_months": TRAIN_MONTHS, "test_months": TEST_MONTHS,
           "metric": "rank correlation across held-out areas between predicted and actual category index, mean over 17 categories", "results": {}}
    out["results"]["no personas: every area gets the London average"] = {"mean_r_across_areas": 0.0, "positive": 0, "mean_r_within_area": None}
    for sens in (False, True):
        tag = "with ethnicity, religion, birthplace" if sens else "without ethnicity, religion, birthplace"
        for how in ("demographic", "predicted"):
            p = Personas(train, TRAIN_MONTHS, sensitive=sens, cluster_on=how)
            label = "clustered on demographics" if how == "demographic" else "clustered on predicted purchases"
            out["results"][f"28 personas {label}, nearest persona ({tag})"] = _score(p.predict(test, soft=False), actual)
            out["results"][f"28 personas {label}, mixture ({tag})"] = _score(p.predict(test, soft=True), actual)
        out["results"][f"no personas: regression straight from demographics ({tag})"] = _score(p.direct(test), actual)
    from . import tabular
    p = Personas(train, TRAIN_MONTHS, sensitive=False)
    Ytr = _mean_periods(TRAIN_MONTHS).loc[train]
    out["results"][f"28 personas, {tabular.BACKEND} reads each area's persona mixture (without ethnicity, religion, birthplace)"] = _score(tab_predict(p.weights(train), Ytr, p.weights(test)), actual)
    out["results"][f"no personas: {tabular.BACKEND} straight from demographics (without ethnicity, religion, birthplace)"] = _score(tab_predict(areas().loc[train, p.cols], Ytr, areas().loc[test, p.cols]), actual)
    return out


STYLES = {"spontaneous": "decides fast and on impulse: frequent small top-up trips, often in the evening",
          "methodical": "plans and compares: few large stock-up trips, more own label",
          "competitive": "wants the best deal: highest share of items bought on promotion",
          "humanistic": "buys on preference more than price: full price, branded, fewer promotions"}
# The four decision-making styles in Salesforce's buyer-persona guide (competitive, spontaneous, humanistic, methodical),
# measured here from shopping habits in the household panel rather than asked in an interview.


@lru_cache(maxsize=1)
def styles() -> pd.Series:
    """Decision style of each of the 28 behavioural personas in the panel."""
    from . import retail
    P = retail.persona_fit()[1].set_index("persona")
    z = P[["p_h_trips", "p_h_lines", "p_h_small", "p_h_evening", "p_h_own", "p_h_promo"]]
    z = (z - z.mean()) / z.std()
    score = pd.DataFrame({"spontaneous": z.p_h_small + z.p_h_trips + 0.5 * z.p_h_evening, "methodical": z.p_h_lines + 0.5 * z.p_h_own - z.p_h_small,
                          "competitive": 2 * z.p_h_promo, "humanistic": -z.p_h_promo - z.p_h_own})
    return score.idxmax(axis=1)


def _name(z: pd.Series, prof: pd.Series) -> str:
    who = [f"{'high' if v > 0 else 'low'} {k}" for k, v in z.sort_values(key=abs, ascending=False).head(3).items()]
    buy = prof.sort_values()
    return ", ".join(who) + f" | buys more {buy.index[-1].replace('_', ' ')}, {buy.index[-2].replace('_', ' ')}; less {buy.index[0].replace('_', ' ')}"


def build(sensitive: bool = False):
    ev = evaluate()
    (CACHE / "uk_eval.json").write_text(json.dumps(ev, indent=1))
    ids = areas().index.intersection(purchases("year").index)
    p = Personas(ids, ["year"], sensitive=sensitive)                 # production fit: every area, the whole year
    order = p.size.sort_values(ascending=False).index
    pid = {c: f"U{i + 1:02d}" for i, c in enumerate(order)}
    zdemo = (p.demo - areas().loc[ids, p.cols].mean()) / areas().loc[ids, p.cols].std()
    pop = pd.read_csv(DATA / "tesco" / "year_msoa_grocery.csv").set_index("area_id").population
    W = p.weights(ids).rename(columns=pid)
    P = pd.DataFrame([{"persona": pid[c], "name": f"{pid[c]} {_name(zdemo.loc[c], p.profile.loc[c])}", "areas": int(p.size[c]),
                       "population": int((W[pid[c]] * pop.reindex(ids)).sum()),
                       **{f"buy_{k}": round(float(v), 3) for k, v in p.profile.loc[c].items()},
                       **{f"who_{k}": round(float(v), 3) for k, v in p.demo.loc[c].items()}} for c in order])
    P.to_parquet(CACHE / "uk_personas.parquet")
    table.cache_clear(); bridge.cache_clear()
    st = bridge().T.groupby(styles()).sum().T.reindex(columns=list(STYLES)).fillna(0)        # each UK persona's mix of decision styles
    for k in STYLES:
        P[f"style_{k}"] = st[k].round(3).values
    P["style"] = st.idxmax(axis=1).values
    P["name"] = [f"{pid_} {sty.capitalize()} | {rest.split(' ', 1)[1]}" for pid_, sty, rest in zip(P.persona, P["style"], P.name)]
    P["rule"] = P.name
    P.to_parquet(CACHE / "uk_personas.parquet")
    table.cache_clear(); bridge.cache_clear()
    W.reset_index(names="area_id").to_parquet(CACHE / "uk_weights.parquet")
    # final area prediction by the in-context model reading persona mixtures; stores use it to scale the persona split
    Y = _mean_periods(["year"]).loc[ids]
    T = tab_predict(p.weights(ids), Y, p.weights(ids)).clip(0.2, 5)
    mix = pd.DataFrame(p.weights(ids).values @ p.profile.values, index=ids, columns=CATS)
    (T / mix).clip(0.5, 2).reset_index(names="area_id").to_parquet(CACHE / "uk_area_adjust.parquet")
    print(json.dumps({k: {m: v[m] for m in ("mean_r_across_areas", "positive", "mean_r_within_area")} for k, v in ev["results"].items()}, indent=1))
    print(P[["name", "areas", "population"]].to_string())
    print(P["style"].value_counts().to_dict(), styles().value_counts().to_dict())


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "uk_personas.parquet")


@lru_cache(maxsize=1)
def area_weights() -> pd.DataFrame:
    return pd.read_parquet(CACHE / "uk_weights.parquet").set_index("area_id")


@lru_cache(maxsize=1)
def area_adjust() -> pd.DataFrame:
    """Per area and category: in-context model prediction over the plain persona mixture."""
    return pd.read_parquet(CACHE / "uk_area_adjust.parquet").set_index("area_id")


def names() -> dict:
    return dict(zip(table().persona, table().rule))


# ------------------------------------------------------------------ timing for UK personas
# Tesco data has no time of day. Each UK persona borrows when it shops, how often and how big its trips are from the
# behavioural personas in the household panel whose category mix it most resembles.
@lru_cache(maxsize=1)
def bridge() -> pd.DataFrame:
    """UK persona x panel persona weights (rows sum to 1): similarity of category mix over the 17 shared categories."""
    from . import retail
    H, _ = retail.persona_fit()
    L = retail.lines()
    L = L[L.category.isin(TESCO_OF)].merge(H, on="household_id")
    us = pd.crosstab(L.persona, L.category.map(TESCO_OF)).reindex(columns=CATS, fill_value=0) + 1
    us = us.div(us.sum(1), axis=0)
    us = np.log(us / us.mean())
    uk = np.log(table().set_index("persona")[[f"buy_{c}" for c in CATS]].clip(lower=0.05))
    uk.columns = CATS
    corr = pd.DataFrame(np.corrcoef(uk.values, us.values)[:len(uk), len(uk):], index=uk.index, columns=us.index)
    w = np.exp(corr / 0.15)
    w = w.where(w.rank(axis=1, ascending=False) <= 5, 0)             # the five closest panel personas
    return w.div(w.sum(1), axis=0)


@lru_cache(maxsize=1)
def load() -> dict:
    """The retail tables re-keyed to UK personas, in the shape store_sim expects."""
    from . import retail
    R, B = retail.load(), bridge()

    hh = retail.persona_fit()[1].set_index("persona").households.reindex(B.columns)
    A = pd.DataFrame(np.tile((hh / hh.sum()).values, (len(B), 1)), index=B.index, columns=B.columns)   # the panel average, same for every UK persona

    def blend(df, who, value, B=B):
        keys = [c for c in df.columns if c not in (who, value)]
        wide = df.pivot_table(index=keys, columns=who, values=value).reindex(columns=B.columns).fillna(0) if keys else None
        if wide is None:
            return pd.DataFrame({who: B.index, value: B.values @ df.set_index(who)[value].reindex(B.columns).fillna(0).values})
        out = pd.DataFrame(wide.values @ B.values.T, index=wide.index, columns=B.index)
        return out.stack().rename(value).reset_index().rename(columns={"persona": who, out.columns.name or "level_%d" % len(keys): who})
    P = table().copy()
    P["households"] = P.population
    ev = {"uk_personas": json.loads((CACHE / "uk_eval.json").read_text()), "behavioural_personas_us_panel": R["eval"]}
    # What a trip contains by hour comes from the panel average, so that a UK persona's own taste (from Tesco) is applied once, not twice.
    # When, how often and how big come from the panel personas it resembles.
    return {"pick": blend(R["pick"], "persona", "p", A), "within": blend(R["within"], "life", "share", A), "trips": blend(R["trips"], "persona", "trips_per_day"),
            "hours": blend(R["hours"], "life", "share"), "bigshare": blend(R["bigshare"], "persona", "p_big"), "depth": blend(R["depth"], "life", "lines", A),
            "personas": P, "meta": {**R["meta"], "personas": "28 UK personas (London MSOA Atlas + Tesco Grocery 1.0); timing borrowed from the household panel"}, "eval": ev}


if __name__ == "__main__":
    build()
