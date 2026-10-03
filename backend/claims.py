"""Health benefits must be legal to say. Checks an item against the GB nutrition and health claims register."""
import glob
from functools import lru_cache

import pandas as pd

from .config import DATA


@lru_cache(maxsize=1)
def register() -> pd.DataFrame:
    f = glob.glob(str(DATA / "claims" / "great-britain-nutrition-and-health-claims*.xlsx"))[0]
    h = pd.read_excel(f, sheet_name="Health_claims", header=2)
    h.columns = ["type", "substance", "claim", "conditions", "relationship", "opinion", "regulation", "status", "entry"]
    h = h.dropna(subset=["substance", "claim"])
    h["authorised"] = h.status.astype(str).str.lower().str.startswith("authorised")
    return h


def lookup(substance: str) -> dict:
    """All register entries for a substance, split into what may and may not be claimed in GB."""
    h = register()
    m = h[h.substance.astype(str).str.contains(substance, case=False, regex=False)]
    ok, no = m[m.authorised], m[~m.authorised]
    return {"substance": substance, "authorised": len(ok), "not_authorised": len(no),
            "may_say": [{"claim": c.strip()[:220], "conditions": str(k).strip()[:260]} for c, k in zip(ok.claim.head(4), ok.conditions.head(4))],
            "may_not_say": [str(r).strip()[:120] for r in no.relationship.head(4)]}


def check(item: dict) -> dict:
    """Nutrition claims the item qualifies for (GB retained Regulation 1924/2006 thresholds) and register look-ups."""
    kcal = max(item.get("kcal", 0), 1)
    per100 = 100 / max(item.get("serving_g", 100), 1)
    liquid = item["category"] in ("coffee", "tea", "soft drink", "energy & sports drink", "juice & fruit drink", "water", "protein & nutrition shake", "milk & dairy drink")
    prot_share = item.get("protein_g", 0) * 4 / kcal
    nutrition = []
    if prot_share >= 0.20: nutrition.append("high protein (20%+ of energy from protein)")
    elif prot_share >= 0.12: nutrition.append("source of protein (12%+ of energy from protein)")
    if item.get("fibre_g", 0) * per100 >= 6: nutrition.append("high fibre (6 g+ per 100 g)")
    elif item.get("fibre_g", 0) * per100 >= 3: nutrition.append("source of fibre (3 g+ per 100 g)")
    if item.get("sugar_g", 0) * per100 <= (2.5 if liquid else 5): nutrition.append("low sugar")
    subs = [s for s, on in (("Protein", prot_share >= 0.12), ("Caffeine", item.get("caffeine_mg", 0) >= 30)) if on]
    return {"item": item["name"], "nutrition_claims_met": nutrition, "health_claims": [lookup(s) for s in subs],
            "source": "GB NHC register, 19 May 2026 (OGL v3)"}
