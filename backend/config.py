"""Paths, moment rules and persona rules shared by the whole backend."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / "cache"
LEDGER = DATA / "ledger.jsonl"
CACHE.mkdir(parents=True, exist_ok=True)

HOURS = list(range(5, 24))  # trading hours modelled


def moment(hour: int, weekend: bool) -> str:
    if 5 <= hour < 10:
        return "early / rush"
    if 10 <= hour < 12:
        return "mid-morning"
    if 12 <= hour < 14:
        return "quick lunch"
    if 14 <= hour < 17:
        return "afternoon focus"
    if 17 <= hour < 21:
        return "social evening" if weekend else "weekday evening"
    return "late night"


# Persona fields the pick model sees (NHANES names).
PERSONA_FIELDS = ["RIAGENDR", "RIDAGEYR", "RIDRETH3", "DMDEDUC2", "DMDMARTZ", "DMDHHSIZ",
                  "INDFMPIR", "DMDBORN4", "WHQ070", "PAD810Q", "PAD790Q", "PAD680"]
MOMENT_FIELDS = ["hour", "dow", "weekend"]

# Named personas are rules over real respondents, so every persona has a head count.
PERSONAS = {
    "young_active":   "18-34, vigorous exercise at least weekly",
    "young_desk":     "18-34, no regular vigorous exercise",
    "midlife_family": "35-54, household of three or more",
    "midlife_solo":   "35-54, household of one or two",
    "weight_watcher": "55+, tried to lose weight in the past year",
    "older_settled":  "55+, did not try to lose weight",
}


def persona_of(row) -> str:
    age, hh = row["RIDAGEYR"], row["DMDHHSIZ"]
    if age < 35:
        return "young_active" if (row["PAD810Q"] or 0) >= 1 and row["PAD810Q"] < 7777 else "young_desk"
    if age < 55:
        return "midlife_family" if hh >= 3 else "midlife_solo"
    return "weight_watcher" if row["WHQ070"] == 1 else "older_settled"


# Sources that count as "bought to go" (NHANES DR1FS codes): restaurants, fast food, cafeteria,
# vending, sport venue, street vendor, convenience store.
TOGO_SOURCES = [2, 3, 4, 5, 6, 14, 24, 25, 27, 28]

EVIDENCE = {
    "nhanes": {"name": "NHANES Aug 2021-Aug 2023 dietary recall", "licence": "US public domain", "role": "who picks what, when"},
    "tfl": {"name": "TfL NUMBAT 2025 + station footfall to 26 Sep 2026", "licence": "TfL open data terms", "role": "people per station per hour"},
    "bakery": {"name": "The Bread Basket, Edinburgh, till data 2016-17", "licence": "CC0", "role": "real UK hourly sales for calibration"},
    "off": {"name": "Open Food Facts", "licence": "ODbL", "role": "product macros, micros, labels"},
    "claims": {"name": "GB nutrition and health claims register, 19 May 2026", "licence": "OGL v3", "role": "which health benefits may be claimed"},
    "holidays": {"name": "gov.uk bank holidays", "licence": "OGL v3", "role": "calendar"},
}
