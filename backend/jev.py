"""Jev (TypeSafe AI's System One model) for the typed decisions in the loop.

Jev takes a piece of state and named questions and returns typed answers with probabilities: a Choice among
options we define, a Score on a rubric, or a Noul (probability that a statement is true). It writes no text, which
suits a ledger: every decision is one of a fixed set, with a probability that can be scored later.

Three jobs here:
    classify_product   free-text product -> shelf category and attributes        (classification)
    decide             a forecast cell with its evidence -> what to do            (decision)
    persona_choice     persona in a moment facing a shelf -> which item           (simulation, for items with no sales history)

Needs TYPESAFE_API_KEY. Without it every function falls back to a transparent rule and says so in "source".
"""
import json
import os

from .retail import CATEGORIES, GROUP_OF

ACTIONS = {
    "stock_up": "Forecast demand is well above what the shelf holds and the evidence is solid; add facings or an extra delivery.",
    "hold": "Forecast is within what the current range and stock can serve; change nothing.",
    "cut_back": "Forecast is well below current stock and waste is the larger risk; reduce the order.",
    "test_first": "The forecast suggests a change but evidence is thin or uncalibrated; run a small trial before committing.",
}
EVIDENCE_SCALE = ["No real purchases behind this cell; a guess.", "A few purchases, or only from a different country or format.",
                  "Enough purchases, but this store has no scored forecasts yet.", "Enough purchases and some scored forecasts at this store.",
                  "Many purchases and a record of accurate scored forecasts at this store."]


def available() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY"))


def _ask(state, questions: dict) -> dict | None:
    """One System One call. Returns {name: answer} or None when Jev cannot be reached."""
    if not available():
        return None
    import typesafe_sdk as ts
    try:
        with ts.TypeSafeClient() as client:
            return dict(client.system_one(state=state, questions=questions).answers)
    except ts.TypeSafeAuthenticationError:
        return None
    except (ts.TypeSafeRateLimitError, ts.TypeSafeAPITimeoutError, ts.TypeSafeAPIConnectionError, ts.TypeSafeAPIError):
        return None


def classify_product(text: str) -> dict:
    """Shelf category and attributes for a product described in free text (a label, a listing, a brand deck line)."""
    from typesafe_sdk import Choice, Noul
    ans = _ask(text, {
        "category": Choice(instructions="Which supermarket category does this product belong in?", criteria={c: f"{c} ({GROUP_OF[c]})" for c in CATEGORIES}),
        "caffeinated": Noul(instructions="The product contains at least 30 mg of caffeine per serving."),
        "high_protein": Noul(instructions="At least 20% of the product's energy comes from protein."),
        "sugary": Noul(instructions="At least 40% of the product's energy comes from sugars."),
        "food_to_go": Noul(instructions="The product is meant to be eaten or drunk immediately, without preparation."),
    })
    if ans:
        c = ans["category"]
        return {"category": c.choice, "group": GROUP_OF[c.choice], "confidence": c.confidence, "probabilities": dict(c.probabilities),
                **{k: ans[k].noul for k in ("caffeinated", "high_protein", "sugary", "food_to_go")}, "source": "jev"}
    t = text.lower()
    rules = [("coffee", "coffee"), ("tea", "tea"), ("kombucha", "tea"), ("energy", "sports & energy drinks"), ("water", "water"), ("juice", "juice"),
             ("cola", "soft drinks"), ("yogurt", "yogurt"), ("skyr", "yogurt"), ("crisp", "crisps & savoury snacks"), ("bar", "confectionery"),
             ("sandwich", "food to go & deli"), ("wrap", "food to go & deli"), ("salad", "salad"), ("croissant", "sweet bakery"), ("beer", "beer & cider")]
    cat = next((c for w, c in rules if w in t), "store cupboard")
    return {"category": cat, "group": GROUP_OF[cat], "confidence": None, "probabilities": None, "source": "keyword rule (no TYPESAFE_API_KEY)"}


def decide(cell: dict) -> dict:
    """What to do about one store-moment-category cell. `cell` carries forecast, range, current stock and the sceptic's checks."""
    from typesafe_sdk import Choice, Noul, Score
    ans = _ask(cell, {
        "action": Choice(instructions="Choose the stocking action for this store, moment and category given the forecast and its evidence.", criteria=ACTIONS),
        "evidence": Score(instructions="How strong is the evidence behind this forecast?", criteria=EVIDENCE_SCALE),
        "needs_review": Noul(instructions="A category manager should review this before it is acted on."),
    })
    if ans:
        return {"action": ans["action"].choice, "action_probabilities": dict(ans["action"].probabilities), "confidence": ans["action"].confidence,
                "evidence_score": ans["evidence"].score, "needs_review": ans["needs_review"].noul, "source": "jev"}
    f, stock, flags = cell.get("forecast_units", 0), cell.get("current_stock"), cell.get("flags", [])
    thin = any("thin" in x or "no scored sales" in x for x in flags)
    if stock is None:
        action = "test_first" if thin else "hold"
    else:
        action = "test_first" if thin and abs(f - stock) > 0.25 * max(stock, 1) else "stock_up" if f > 1.15 * stock else "cut_back" if f < 0.7 * stock else "hold"
    return {"action": action, "action_probabilities": None, "confidence": None, "evidence_score": 1 if thin else 3, "needs_review": 1.0 if thin else 0.2,
            "source": "threshold rule (no TYPESAFE_API_KEY)"}


def persona_choice(persona: str, moment: str, store: str, items: list) -> dict:
    """Which of these items this persona picks in this moment. Used only to split a category's forecast among items that have no sales history."""
    from typesafe_sdk import Choice
    if len(items) < 2:
        return {"shares": {i["name"]: 1.0 for i in items}, "source": "single item"}
    ans = _ask({"shopper": persona, "moment": moment, "store": store},
               {"pick": Choice(instructions="Which one of these products does this shopper put in the basket on this trip?",
                               criteria={i["name"]: json.dumps({k: i.get(k) for k in ("brand", "kcal", "protein_g", "sugar_g", "caffeine_mg", "labels")}) for i in items})})
    if ans:
        return {"shares": dict(ans["pick"].probabilities), "source": "jev"}
    return {"shares": {i["name"]: 1 / len(items) for i in items}, "source": "equal split (no TYPESAFE_API_KEY)"}
