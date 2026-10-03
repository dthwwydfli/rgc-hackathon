# Backend + data handoff

FE owns `web/`. This file is the contract for whoever runs T0–T7 and T10.

## Ownership

| Task | What | Gate |
|------|------|------|
| T0 | Pick 4 products, lock personas/moments/weights into `config/` | Config committed; hunch winners differ by moment |
| T1 | Open Food Facts + pack photos + prices into `config/products.json` | No blank fields; every score has a source |
| T2 | Google Form (exact form spec), Sheet → CSV, QR | <60s on phone; shuffle; no PII; test rows deleted before live |
| T3 | `sim/engine.py` Stage 1+2, seed 42, 1000 shoppers/cell | Deterministic; shares sum 100%; tests in `sim/tests/` |
| T4 | `sim/explain.py` → `out/predictions.json`; commit + timestamp screenshot | Then `predictions.json`, `personas.json`, `moments.json` read-only |
| T5 | `sim/score.py` vs live CSV; baselines random 25% + cheapest-wins | Write `out/results.json`; every % has n; show Other count |
| T6 | Gap analysis into `results.gaps` | Insights link to response IDs |
| T7 | `sim/calibrate.py` on ≥30 scored responses | New weights file only; held-out accuracy; refuse if worse |
| T10 | Optional physical table test | Directional with n |

## Pipeline

```
config/*.json ──► sim/engine.py + explain.py ──► out/predictions.json (lock T4)
Google Form CSV ──► sim/score.py (+ calibrate.py) ──► out/results.json
web/ reads config + out (or web/mock until lock)
```

## File contracts FE already consumes

- `config/products.json` — `price_pence` integer; `image_path` relative to `web/`
- `config/personas.json` — ordered assignment rules + weights
- `config/moments.json` — dwell, zones, visibility assumptions, `tested_live`, `start_minute`, `end_minute` (minutes from midnight; `time_window` is display only)
- `out/predictions.json` — `locked_at`, `git_commit`, `cells[persona|moment]`
- `out/results.json` — accuracy, baselines, cells with `n_real`, evidence, quotes, `actions_by_product`, gaps, calibration

### `actions_by_product` (per cell)

```json
"actions_by_product": {
  "challenger": {
    "next_step": "Lead with grams of protein on front",
    "cost_pence": 500,
    "owner": "brand",
    "expensive_action_avoided": "Blanket price cut before a low-cost pack or fixture test",
    "effort": "S"
  }
}
```

- `cost_pence`: integer pence, or `null` → UI shows "Cost unknown"
- `owner`: `brand` | `retailer`
- `effort`: `S` | `M` | `L`

## Lock ritual (T4)

1. Run sim → write `out/predictions.json`
2. `git add` config + predictions; commit; record hash into file
3. Screenshot file with visible OS timestamp
4. Only then open the form to real respondents
5. Later weight changes → new file (e.g. `out/weights_calibrated.json`), never edit locked files

## Constraints that stop the line

- No LLM for choice predictions
- No PII on the form
- No post-hoc edits to locked predictions/weights except labelled calibration → new files
- Staff only enter spoken answers

## Stack

Python 3, numpy, pandas. Seed 42. Tests: one file per `sim/` module under `sim/tests/`.

## Scaffold status

`sim/*.py` stubs are placeholders so the tree matches the plan. Implement against the product Constraints; do not invent FE numbers.
