"""Agent loops. Numbers come from the simulation and the tabular model; agents decide, check and learn.

  plan loop    simulate -> sceptic checks -> decision per moment -> ledger
  learn loop   actuals -> score each decision -> refit calibration -> ledger -> next plan uses it
  review       optional Claude agent that reads the ledger through tools and writes a reviewed note

Every step also runs without an LLM, so the loop is deterministic and testable; Claude adds judgement on top.
"""
import json
from datetime import date as Date, timedelta

import pandas as pd
from scipy.stats import poisson

from . import calibrate, catalogue, claims, jev, ledger, simulate
from .config import CACHE, EVIDENCE

MIN_EVIDENCE = 300      # real purchases behind a moment before we call the evidence thin
MIN_HOUSEHOLDS = 10     # panel households behind a persona before we call it thin
TOP_DECISIONS = 5       # categories per moment that get a typed decision


def _thin_personas() -> set:
    from . import retail
    P = retail.persona_fit()[1]
    return set(P[P.measured & (P.households < MIN_HOUSEHOLDS)].persona)


# ------------------------------------------------------------------ sceptic (rules)
def sceptic(sim: dict, moment: str, cells: list) -> dict:
    hrs = [h for h in sim["hours"] if h["moment"] == moment]
    n = sum(h["evidence_items"] for h in hrs)
    flags = []
    if n < MIN_EVIDENCE:
        flags.append(f"thin evidence: {n} real purchases behind this moment")
    if "actual" not in sim["footfall_basis"]:
        flags.append(f"footfall is an estimate ({sim['footfall_basis']})")
    if not sim["calibration"]["category"] and not sim["calibration"]["moment"]:
        flags.append("no scored sales at this location yet; capture rate is assumed")
    served, unserved = sum(h["units_served"] for h in hrs), sum(h["unserved_buyers"] for h in hrs)
    if unserved > served:
        flags.append(f"shelf misses most demand in this moment ({unserved:.0f} buyers wanted a category not stocked)")
    for c in cells:
        if c["units"] >= 1:
            item = next((i for i in catalogue.load() if i["id"] == c["item_id"]), None)
            for hc in (claims.check(item)["health_claims"] if item else []):
                if hc["authorised"] == 0 and hc["not_authorised"] > 0:
                    flags.append(f"{item['name']}: no authorised GB health claim for {hc['substance'].lower()}; do not sell it on that benefit")
    thin = sorted({c["top_persona"] for c in cells if c.get("top_persona") and c["units"] >= 1} & _thin_personas())
    if thin:
        flags.append(f"leading persona rests on fewer than {MIN_HOUSEHOLDS} panel households: {', '.join(thin)}")
    conf = "low" if n < MIN_EVIDENCE else "medium" if not (sim["calibration"]["category"] or sim["calibration"]["moment"]) else "high"
    return {"evidence_items": n, "flags": sorted(set(flags)), "confidence": conf}


# ------------------------------------------------------------------ plan loop
def plan_day(station: str, d: Date, service_level: float = 0.85, author: str = "planner", stock: dict | None = None) -> list:
    """`station` is any location: a store id or a station name. `stock` maps item or category to units on hand, if known."""
    sim = simulate.simulate(station, d, service_level=service_level)
    out = []
    for mom in dict.fromkeys(c["moment"] for c in sim["cells"]):
        cells = [c for c in sim["cells"] if c["moment"] == mom]
        hrs = [h for h in sim["hours"] if h["moment"] == mom]
        mix = pd.DataFrame([h["persona_mix"] for h in hrs]).mul([h["buyers"] for h in hrs], axis=0).sum()
        checks = sceptic(sim, mom, cells)
        typed = [{"category": c["category"], **jev.decide({"store": sim.get("location", station), "date": d.isoformat(), "moment": mom, "category": c["category"],
                                                            "forecast_units": c["units"], "range": [c["low"], c["high"]], "current_stock": (stock or {}).get(c["item_id"]),
                                                            "leading_persona": c.get("top_persona"), "flags": checks["flags"], "calendar": sim["day"]})}
                 for c in sorted(cells, key=lambda c: -c["units"])[:TOP_DECISIONS]]
        payload = {"location": station, "location_name": sim["station"], "date": d.isoformat(), "moment": mom, "hours": [h["hour"] for h in hrs],
                   "people": sum(h["people"] for h in hrs), "persona_mix": (mix / max(mix.sum(), 1e-9)).round(3).to_dict(),
                   "lines": [{k: c[k] for k in ("item_id", "item", "category", "units", "base_units", "low", "high", "order_qty", "by_persona")} for c in cells],
                   "decision": {"rule": f"stock to the {int(service_level*100)}th percentile of forecast demand", "service_level": service_level, "typed": typed},
                   "checks": checks, "evidence": sim["evidence"], "model": sim["model"]["model"],
                   "calibration": sim["calibration"], "caveats": sim["caveats"], "status": "open"}
        out.append(ledger.append("decision", payload, author))
    return out


# ------------------------------------------------------------------ learn loop
def score_day(location: str, d: Date, actuals: list, author: str = "scorer") -> dict:
    """actuals: [{"moment":..., "item_id":..., "units":...}]. Scores every open decision for that day, then recalibrates."""
    act = {(a["moment"], a["item_id"]): a["units"] for a in actuals}
    scored = {s["payload"]["decision_id"] for s in ledger.read("score")}
    recs = []
    for dec in ledger.read("decision", location=location, date=d.isoformat()):
        if dec["id"] in scored:
            continue
        lines = []
        for l in dec["payload"]["lines"]:
            a = act.get((dec["payload"]["moment"], l["item_id"]))
            if a is None:
                continue
            lines.append({"item_id": l["item_id"], "item": l["item"], "category": l["category"], "forecast": l["units"], "base": l.get("base_units", l["units"]), "actual": a,
                          "error": round(a - l["units"], 1), "in_range": bool(l["low"] <= a <= l["high"]),
                          "sold_out": bool(a >= l["order_qty"] > 0), "waste": max(l["order_qty"] - a, 0)})
        if lines:
            f, a = sum(x["forecast"] for x in lines), sum(x["actual"] for x in lines)
            recs.append(ledger.append("score", {"decision_id": dec["id"], "location": location, "date": d.isoformat(), "moment": dec["payload"]["moment"],
                                                "lines": lines, "forecast": round(f, 1), "actual": a,
                                                "wape": round(sum(abs(x["error"]) for x in lines) / max(a, 1), 3),
                                                "in_range_share": round(sum(x["in_range"] for x in lines) / len(lines), 2)}, author))
    return {"scored": len(recs), "recalibration": recalibrate(location)}


def recalibrate(location: str, window: int = 14) -> dict:
    """Refit one scalar per category, then one per moment on what is left, from the last `window` days of scores.
    Scalars are fitted against the uncalibrated forecast, so they do not compound from day to day, and are pulled toward 1 when evidence is thin."""
    scores = [s["payload"] for s in ledger.read("score", location=location)]
    if not scores:
        return {}
    last = max(s["date"] for s in scores)
    recent = [s for s in scores if s["date"] > (Date.fromisoformat(last) - timedelta(days=window)).isoformat()]
    cal = simulate.calibration(location)
    L = pd.DataFrame([{**l, "moment": s["moment"]} for s in recent for l in s["lines"]])
    cal["category"] = {c: round(calibrate.shrunk_ratio(g.actual.sum(), g.base.sum()), 3) for c, g in L.groupby("category")}
    L["after_category"] = L.base * L.category.map(cal["category"])
    cal["moment"] = {m: round(calibrate.shrunk_ratio(g.actual.sum(), g.after_category.sum()), 3) for m, g in L.groupby("moment")}
    simulate.save_calibration(location, cal)
    return ledger.append("recalibration", {"location": location, "through": last, "days_used": len({s["date"] for s in recent}),
                                           "calibration": cal, "method": "(actual+20)/(uncalibrated forecast+20) per category, then per moment on the remainder; clipped to 0.25-4"}, "learner")["payload"]


# ------------------------------------------------------------------ the loop on real sales (Edinburgh bakery)
def replay_bakery(days: int = 28, service_level: float = 0.85, source: str = "prior") -> dict:
    """Run plan -> score -> recalibrate day by day over the held-out bakery period, on real till data.

    source="prior": cold start. The forecast is the US persona-moment shape scaled to the shop's known total volume, and the
                    loop has to learn the shop's categories and moments from scored decisions.
    source="model": the in-context sales model that already reads the shop's history (cached by calibrate.backtest()).
    Each day's plan uses only scalars learned from earlier days."""
    loc = f"The Bread Basket, Edinburgh ({source})"
    fc = pd.read_parquet(CACHE / "bakery_forecast.parquet")
    meta = json.loads((CACHE / "backtest.json").read_text())
    if source == "prior":
        b = calibrate.frame()
        tr = b[b.date < fc.date.min()]
        scale = tr.units.sum() / tr.prior_us.sum()                       # the shop's total volume is known; its profile is not
        fc = fc.merge(b[["date", "hour", "category", "prior_us"]], on=["date", "hour", "category"])
        fc["base"] = fc.prior_us * scale
    else:
        fc["base"] = fc.f_model
    simulate.save_calibration(loc, {"capture": simulate.DEFAULT_CAPTURE, "category": {}, "moment": {}})
    daily = []
    for d in sorted(fc.date.unique())[:days]:
        day, cal, iso = fc[fc.date == d], simulate.calibration(loc), pd.Timestamp(d).date().isoformat()
        actuals = []
        for mom, g in day.groupby("moment", sort=False):
            lines = []
            for cat, c in g.groupby("category"):
                base = float(c.base.sum())
                mu = base * cal["moment"].get(mom, 1.0) * cal["category"].get(cat, 1.0)
                lines.append({"item_id": cat, "item": cat, "category": cat, "units": round(mu, 1), "base_units": round(base, 2),
                              "low": int(poisson.ppf(0.1, mu)), "high": int(poisson.ppf(0.9, mu)), "order_qty": int(poisson.ppf(service_level, mu)), "by_persona": {}})
                actuals.append({"moment": mom, "item_id": cat, "units": int(c.units.sum())})
            ledger.append("decision", {"location": loc, "date": iso, "moment": mom, "hours": sorted(g.hour.unique().tolist()),
                                       "lines": lines, "decision": {"rule": f"stock to the {int(service_level*100)}th percentile", "service_level": service_level},
                                       "checks": {"flags": [], "confidence": "high" if cal["category"] else "medium", "evidence_items": meta["context_rows"]},
                                       "evidence": [EVIDENCE["bakery"], EVIDENCE["nhanes"]], "model": meta["model"], "calibration": cal, "status": "open"}, "planner")
        score_day(loc, pd.Timestamp(d).date(), actuals)
        L = [l for x in ledger.read("score", location=loc, date=iso) for l in x["payload"]["lines"]]
        act = max(sum(l["actual"] for l in L), 1)
        daily.append({"date": iso, "actual": sum(l["actual"] for l in L), "forecast": round(sum(l["forecast"] for l in L), 1),
                      "wape": round(sum(abs(l["error"]) for l in L) / act, 3),
                      "wape_without_learning": round(sum(abs(l["actual"] - l["base"]) for l in L) / act, 3),
                      "in_range": round(sum(l["in_range"] for l in L) / len(L), 2), "sold_out_lines": sum(l["sold_out"] for l in L), "waste_units": sum(l["waste"] for l in L)})
    D = pd.DataFrame(daily)
    weeks = [D.iloc[i:i + 7] for i in range(0, len(D), 7)]
    return {"location": loc, "source": source, "days": len(D),
            "wape_by_week": [round(float(w.wape.mean()), 3) for w in weeks],
            "wape_by_week_without_learning": [round(float(w.wape_without_learning.mean()), 3) for w in weeks],
            "in_range_share": round(float(D.in_range.mean()), 2), "calibration": simulate.calibration(loc), "daily": daily, "ledger": ledger.verify()}


# ------------------------------------------------------------------ Claude review agent (optional)
REVIEW_SYSTEM = """You review stocking decisions for a food-to-go shelf before a category manager signs them off.
The forecasts come from a statistical model, not from you: never invent or adjust a number. Use the tools to read the
decision, the evidence behind it, the backtest and the health-claims register, then say plainly whether the decision
should stand, what would change your mind, and which claims the team must not make. If the evidence is thin, say so.
Finish by calling record_review exactly once."""


def review_with_claude(station: str, d: Date, model: str = "claude-opus-5-5") -> dict:
    """An agent loop over the ledger. Needs Anthropic credentials (ANTHROPIC_API_KEY or an `ant auth login` profile)."""
    import anthropic
    from anthropic import beta_tool

    client = anthropic.Anthropic()

    @beta_tool
    def get_decisions(moment: str = "") -> str:
        """Read the open stocking decisions for this location and date. Each has forecast lines, ranges, persona mix and rule-based checks.

        Args:
            moment: Optional moment name to filter by, e.g. "quick lunch". Empty string returns every moment.
        """
        rows = [r for r in ledger.read("decision", location=station, date=d.isoformat()) if not moment or r["payload"]["moment"] == moment]
        return json.dumps([{"id": r["id"], **{k: r["payload"][k] for k in ("moment", "hours", "people", "persona_mix", "lines", "checks", "calibration")}} for r in rows])

    @beta_tool
    def get_backtest() -> str:
        """Return the held-out accuracy of the forecast method on real UK till data, against naive baselines, and the pick model's held-out score."""
        from . import picks
        return json.dumps({"sales_backtest": json.loads((CACHE / "backtest.json").read_text()), "pick_model": picks.load()["eval"]})

    @beta_tool
    def check_claim(substance: str) -> str:
        """Look up a nutrient or substance in the GB nutrition and health claims register to see which health claims are authorised.

        Args:
            substance: Substance name as it appears on a label, e.g. "Caffeine", "Protein", "Vitamin B12".
        """
        return json.dumps(claims.lookup(substance))

    @beta_tool
    def get_history() -> str:
        """Return past scores and recalibrations for this location: how earlier forecasts compared with actual sales."""
        s = [x["payload"] for x in ledger.read("score", location=station)][-30:]
        return json.dumps({"scores": [{k: x[k] for k in ("date", "moment", "forecast", "actual", "wape", "in_range_share")} for x in s],
                           "calibration": simulate.calibration(station)})

    saved = {}

    @beta_tool
    def record_review(verdict: str, summary: str, risks: list[str], claims_to_avoid: list[str], would_change_my_mind: str) -> str:
        """Write the review to the ledger. Call once, at the end.

        Args:
            verdict: One of "stand", "stand with changes", "hold".
            summary: Two or three sentences a category manager can act on.
            risks: Specific risks found in the evidence, each one sentence.
            claims_to_avoid: Health or nutrition claims the team must not make for the stocked items.
            would_change_my_mind: The observation that would reverse the verdict.
        """
        saved.update(ledger.append("review", {"location": station, "date": d.isoformat(), "verdict": verdict, "summary": summary, "risks": risks,
                                              "claims_to_avoid": claims_to_avoid, "would_change_my_mind": would_change_my_mind, "model": model}, "claude-reviewer"))
        return "recorded"

    try:
        runner = client.beta.messages.tool_runner(
            model=model, max_tokens=16000, system=REVIEW_SYSTEM, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            tools=[get_decisions, get_backtest, check_claim, get_history, record_review],
            messages=[{"role": "user", "content": f"Review the stocking plan for {station} on {d.isoformat()}."}])
        last = None
        for last in runner:
            pass
        if last is not None and last.stop_reason == "refusal":
            return {"ok": False, "error": "the model declined this request"}
    except anthropic.AuthenticationError:
        return {"ok": False, "error": "no valid Anthropic credentials; set ANTHROPIC_API_KEY or run `ant auth login`"}
    except anthropic.RateLimitError:
        return {"ok": False, "error": "rate limited; retry shortly"}
    except anthropic.APIStatusError as e:
        return {"ok": False, "error": f"API error {e.status_code}: {e.message}"}
    except anthropic.APIConnectionError:
        return {"ok": False, "error": "network error reaching the Anthropic API"}
    return {"ok": bool(saved), "review": saved or None}
