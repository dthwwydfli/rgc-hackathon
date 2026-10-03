"""The pick model: P(category and attributes | persona, moment), learned in context from real occasions.

Build step (python -m backend.picks) writes four cached tables:
  pick_grid      persona x hour x weekend x category -> probability
  attr_grid      persona x hour x weekend -> P(caffeinated), P(high protein), P(sugary)
  mix            hour x weekend x persona -> share of people buying to go
  propensity     hour x weekend -> to-go purchases per adult per day in that hour
and pick_eval.json, the held-out score against two baselines.
"""
import json
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupShuffleSplit

from . import tabular
from .config import CACHE, HOURS, MOMENT_FIELDS, PERSONA_FIELDS, PERSONAS
from .data import items, togo_items

FEATS = PERSONA_FIELDS + MOMENT_FIELDS
ATTRS = ["caffeinated", "high_protein", "sugary"]
N_CONTEXT, N_MEMBERS = 5000, 8   # 8 real members x 6 personas x 19 hours x 2 day types = 1,824 query rows


def _query_rows(t: pd.DataFrame, rng) -> pd.DataFrame:
    """Real members of each persona, placed in every hour of a weekday (Wed) and a weekend day (Sat)."""
    people = t.drop_duplicates("SEQN")
    rows = []
    for p in PERSONAS:
        m = people[people.persona == p]
        m = m.sample(min(N_MEMBERS, len(m)), random_state=0)
        for we, dow in [(0, 4), (1, 7)]:
            for h in HOURS:
                q = m[["SEQN", "persona"] + PERSONA_FIELDS].copy()
                q["hour"], q["dow"], q["weekend"] = h, dow, we
                rows.append(q)
    return pd.concat(rows, ignore_index=True)


def evaluate(t: pd.DataFrame) -> dict:
    """Held-out people. Is persona-in-moment better than moment alone, and than the overall mix?"""
    tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=0).split(t, groups=t.SEQN))
    a, b = t.iloc[tr], t.iloc[te].sample(min(3000, len(te)), random_state=0)
    cats = sorted(t.category.unique())
    y = b.category.values

    def score(P):
        P = np.clip(P, 1e-6, 1); P = P / P.sum(1, keepdims=True)
        top3 = np.argsort(-P, 1)[:, :3]
        idx = np.array([cats.index(c) for c in y])
        return {"log_loss": round(float(log_loss(y, P, labels=cats)), 3),
                "top1": round(float((top3[:, 0] == idx).mean()), 3),
                "top3": round(float((top3 == idx[:, None]).any(1).mean()), 3)}

    out = {"n_train_items": len(a), "n_test_items": len(b), "n_categories": len(cats)}
    base = a.category.value_counts(normalize=True).reindex(cats, fill_value=0).values
    out["overall mix"] = score(np.tile(base, (len(b), 1)))
    byh = (pd.crosstab([a.hour, a.weekend], a.category).reindex(columns=cats, fill_value=0) + 1)
    byh = byh.div(byh.sum(1), axis=0)
    out["moment only (hour x weekend table)"] = score(np.vstack([byh.loc[(h, w)].values if (h, w) in byh.index else base for h, w in zip(b.hour, b.weekend)]))
    ctx = a.sample(min(N_CONTEXT, len(a)), random_state=0)
    m = tabular.classifier().fit(ctx[FEATS], ctx.category)
    P = pd.DataFrame(m.predict_proba(b[FEATS]), columns=m.classes_).reindex(columns=cats, fill_value=0).values
    out[f"persona + moment ({tabular.BACKEND}, {len(ctx)} context rows)"] = score(P)
    return out


def build():
    t0 = time.time()
    t = togo_items()
    rng = np.random.default_rng(0)
    f = CACHE / "pick_eval.json"
    done = json.loads(f.read_text()) if f.exists() else {}
    if done.get("model", {}).get("backend") == tabular.BACKEND and "--force-eval" not in sys.argv:
        print("held-out score already saved for this backend; pass --force-eval to redo it", flush=True)
    else:
        ev = evaluate(t)
        ev["model"] = tabular.describe()
        f.write_text(json.dumps(ev, indent=1))
        print(json.dumps(ev, indent=1), f"\n[{time.time()-t0:.0f}s]", flush=True)

    ctx = t.sample(min(N_CONTEXT, len(t)), random_state=1)
    q = _query_rows(t, rng)
    m = tabular.classifier().fit(ctx[FEATS], ctx.category)
    P = pd.DataFrame(m.predict_proba(q[FEATS]), columns=m.classes_)
    g = pd.concat([q[["persona", "hour", "weekend"]], P], axis=1).groupby(["persona", "hour", "weekend"]).mean()
    grid = g.stack().rename("p").reset_index().rename(columns={"level_3": "category"})
    grid.to_parquet(CACHE / "pick_grid.parquet")
    print("pick grid", grid.shape, f"[{time.time()-t0:.0f}s]", flush=True)

    A = q[["persona", "hour", "weekend"]].copy()
    for a in ATTRS:
        ma = tabular.classifier().fit(ctx[FEATS], ctx[a])
        A[a] = ma.predict_proba(q[FEATS])[:, list(ma.classes_).index(1)]
    A.groupby(["persona", "hour", "weekend"], as_index=False).mean().to_parquet(CACHE / "attr_grid.parquet")

    occ = t.drop_duplicates(["SEQN", "recall_day", "DR_020"])
    mix = (pd.crosstab([occ.hour, occ.weekend], occ.persona) + 1)
    mix = mix.div(mix.sum(1), axis=0).stack().rename("share").reset_index()
    mix.to_parquet(CACHE / "mix.parquet")
    days = items().drop_duplicates(["SEQN", "recall_day"]).groupby("weekend").size()   # adult recall-days
    prop = occ.groupby(["hour", "weekend"]).size().rename("n").reset_index()
    prop["per_adult_day"] = prop.n / prop.weekend.map(days)
    prop.to_parquet(CACHE / "propensity.parquet")
    n = t.groupby(["persona", "hour", "weekend"]).size().rename("n_items").reset_index()
    n.to_parquet(CACHE / "support.parquet")                                           # evidence count per cell
    meta = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": tabular.describe(), "context_rows": len(ctx),
            "togo_items": len(t), "adults": int(t.SEQN.nunique()), "members_per_persona": N_MEMBERS,
            "persona_sizes": t.drop_duplicates("SEQN").persona.value_counts().to_dict()}
    (CACHE / "pick_meta.json").write_text(json.dumps(meta, indent=1))
    print("done", f"[{time.time()-t0:.0f}s]", flush=True)


def load() -> dict:
    return {"pick": pd.read_parquet(CACHE / "pick_grid.parquet"), "attr": pd.read_parquet(CACHE / "attr_grid.parquet"),
            "mix": pd.read_parquet(CACHE / "mix.parquet"), "prop": pd.read_parquet(CACHE / "propensity.parquet"),
            "support": pd.read_parquet(CACHE / "support.parquet"), "meta": json.loads((CACHE / "pick_meta.json").read_text()),
            "eval": json.loads((CACHE / "pick_eval.json").read_text())}


if __name__ == "__main__":
    build()
