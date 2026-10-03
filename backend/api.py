"""HTTP API for the calendar front end.  Run: .venv/bin/uvicorn backend.api:app --reload --port 8000"""
import json
from datetime import date as Date, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agents, catalogue, claims, jev, ledger, picks, retail, shelf, simulate, store_sim, stores, survey_personas, uk_personas
from .config import CACHE, EVIDENCE, PERSONAS
from .data import day_info, footfall, stations

app = FastAPI(title="Moment Ledger")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _station(name: str) -> str:
    """A location: a store id from /stores (the default) or a TfL station name."""
    if str(name) not in set(stores.table().id) and name not in stations():
        raise HTTPException(404, f"unknown location: {name}")
    return str(name)


@app.get("/meta")
def meta():
    """Personas with head counts, the model in use and its held-out scores, and every data source with its licence."""
    G = picks.load()
    bt = CACHE / "backtest.json"
    return {"personas": [{"id": p, "rule": r, "people": G["meta"]["persona_sizes"].get(p, 0)} for p, r in PERSONAS.items()],
            "model": G["meta"], "pick_eval": G["eval"], "sales_backtest": json.loads(bt.read_text()) if bt.exists() else None,
            "evidence": EVIDENCE, "ledger": ledger.verify()}


@app.get("/stores")
def list_stores(q: str = "", retailer: str = "", borough: str = "", limit: int = 50):
    """London supermarkets and convenience stores (Geolytix Retail Points). Use the id as `station` in the other calls."""
    return stores.search(q, retailer, borough, min(limit, 500))


@app.get("/stores/{store_id}")
def store(store_id: str):
    """One store with its format, assumed volume, and the neighbourhood's Tesco purchase profile."""
    if store_id not in set(stores.table().id):
        raise HTTPException(404, f"unknown store: {store_id}")
    return stores.get(store_id)


@app.get("/personas")
def personas():
    """The team's 28 shopper personas: which 15 are measured from till behaviour (with head counts and habits), which 13 need a survey, and the held-out test."""
    R, M = retail.load(), survey_personas.meta()
    rows = json.loads(R["personas"].to_json(orient="records"))
    for r in rows:                                   # add what the UK survey knows about each persona
        n = r["persona"]
        r["source"] = "till data" if r["measured"] else "UK survey" if n in M["uk_share"] else "no data yet"
        if n in M["uk_share"]:
            r["uk_survey"] = {"share_of_adults": M["uk_share"][n], "answer": M["meaning"][n], "predictable_from_place_and_age_auc": M["eval"][n]["auc"]}
    return {"personas": rows, "eval": R["eval"], "survey_eval": M["eval"], "model": R["meta"], "evidence": store_sim.EVIDENCE}


@app.get("/neighbourhoods")
def neighbourhoods():
    """Location model: 28 London neighbourhood types fitted to Tesco purchases, with their held-out test. Separate from the shopper personas."""
    return {"types": uk_personas.table().to_dict("records"), "eval": json.loads((CACHE / "uk_eval.json").read_text())}


@app.get("/persona")
def persona(persona: str, store: str, date: Date):
    """One persona at one store on one date: when they come and what they buy."""
    if persona not in retail.measured():
        raise HTTPException(404, f"unknown or unmeasured persona: {persona}; see /personas")
    return store_sim.persona_view(persona, _station(store), date)


@app.get("/recommend")
def recommend(store: str, weekday: int, hour: int, weeks: int = 12, start: Date | None = None, top: int = 8):
    """The main product call. Pick a day of the week (0 = Monday) and an hour (6-22): what to stock at this store in that
    slot for each of the next `weeks` weeks, how much, for which personas, and which weeks differ because of the calendar."""
    if not 0 <= weekday <= 6 or hour not in retail.HOURS:
        raise HTTPException(422, "weekday must be 0-6 (Monday = 0) and hour 6-22")
    return store_sim.recommend(_station(store), weekday, hour, min(weeks, 26), start, top)


@app.get("/where")
def where(persona: str, date: Date, borough: str = "", limit: int = 15):
    """Which stores a persona shops at on a date, ranked by expected trips, with their peak hour."""
    if persona not in retail.measured():
        raise HTTPException(404, f"unknown persona: {persona}")
    return store_sim.where(persona, date, borough, min(limit, 100))


class ProductText(BaseModel):
    text: str


@app.post("/classify")
def classify(req: ProductText):
    """Jev classification: free-text product -> shelf category and attributes, with probabilities."""
    return jev.classify_product(req.text)


@app.get("/stations")
def list_stations(q: str = ""):
    return [s for s in stations() if q.lower() in s.lower()][:50]


@app.get("/products")
def products():
    return [{**i, "claims": claims.check(i)} for i in catalogue.load()]


@app.get("/simulate")
def run_simulation(station: str, date: Date, service_level: float = 0.85):
    """Hour-by-hour prediction: what is bought, by which persona, at this location (store id or station) on this date."""
    return simulate.simulate(_station(station), date, service_level=service_level)


@app.get("/shelfplan")
def shelf_plan(station: str, start: Date, days: int = 7):
    """A layout set once and the fewest refill visits per day, with labour and margin against refilling at every moment."""
    return shelf.plan(_station(station), start, min(days, 14))


@app.get("/calendar")
def calendar(station: str, start: Date, days: int = 7):
    """One row per day and moment: people, forecast units, top item, plus any decision, score and review already in the ledger."""
    _station(station)
    out = []
    for k in range(min(days, 14)):
        d = start + timedelta(days=k)
        sim = simulate.simulate(station, d)
        decs = {r["payload"]["moment"]: r for r in ledger.read("decision", location=station, date=d.isoformat())}
        scores = {r["payload"]["decision_id"]: r["payload"] for r in ledger.read("score", location=station, date=d.isoformat())}
        for mom in dict.fromkeys(h["moment"] for h in sim["hours"]):
            hrs = [h for h in sim["hours"] if h["moment"] == mom]
            cells = sorted((c for c in sim["cells"] if c["moment"] == mom), key=lambda c: -c["units"])
            dec = decs.get(mom)
            out.append({"date": d.isoformat(), "day": sim["day"], "moment": mom, "hours": [h["hour"] for h in hrs],
                        "people": sum(h["people"] for h in hrs), "units": round(sum(c["units"] for c in cells), 1),
                        "top_items": [{k2: c[k2] for k2 in ("item", "units", "low", "high")} for c in cells[:3]],
                        "decision_id": dec["id"] if dec else None, "confidence": dec["payload"]["checks"]["confidence"] if dec else None,
                        "score": scores.get(dec["id"]) if dec else None})
    return out


class PlanRequest(BaseModel):
    station: str
    date: Date
    service_level: float = 0.85
    review: bool = False


@app.post("/plan")
def plan(req: PlanRequest):
    """Plan loop: simulate, run the sceptic checks, write one decision per moment. Optionally ask Claude to review."""
    decisions = agents.plan_day(_station(req.station), req.date, req.service_level)
    return {"decisions": decisions, "review": agents.review_with_claude(req.station, req.date) if req.review else None}


class Actual(BaseModel):
    moment: str
    item_id: str
    units: float


class ActualsRequest(BaseModel):
    location: str
    date: Date
    actuals: list[Actual]


@app.post("/actuals")
def actuals(req: ActualsRequest):
    """Learn loop: score that day's decisions against sales and refit the calibration."""
    return agents.score_day(req.location, req.date, [a.model_dump() for a in req.actuals])


@app.get("/ledger")
def read_ledger(kind: str | None = None, location: str | None = None, date: str | None = None, limit: int = 200):
    where = {k: v for k, v in (("location", location), ("date", date)) if v}
    return {"verify": ledger.verify(), "records": ledger.read(kind, **where)[-limit:]}


@app.post("/replay/bakery")
def replay(days: int = 28, source: str = "prior"):
    """Run the full plan-score-recalibrate loop on real Edinburgh till data. source = prior (cold start) | model."""
    return agents.replay_bakery(days, source=source)


@app.get("/footfall")
def get_footfall(station: str, date: Date):
    f = footfall(_station(station), date)
    return {"day": day_info(date), "basis": f.basis.iloc[0], "hours": f[["hour", "people"]].to_dict("records")}
