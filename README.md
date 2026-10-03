# Moments

Timetable for a challenger snack brand: which shopper moments it wins and loses, why, and the cheapest next action. Predicts first, scores against real choices after.

## How to run

```bash
npm install
npm run dev
```

Open the URL Vite prints (usually [http://127.0.0.1:5173/](http://127.0.0.1:5173/)). Week calendar is the main screen; hamburger opens Validation and What-if. Loaders try `/config` and `/out` first, then `web/mock`.

Swimlanes HTML (`/variations/week-swimlanes.html`) calls Moment Ledger through Vite’s `/api` proxy. Without the API it uses fixtures under `web/mock/`.

### Moment Ledger API (optional)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python scripts/setup_data.py          # ~700 MB download; ~15 min
uvicorn backend.api:app --port 8000
```

Then restart `npm run dev` so `/api` proxies to `:8000`. Main call: `GET /recommend?store=&weekday=&hour=&weeks=12`. Details: [`backend/README.md`](backend/README.md).

## How to test

```bash
npm test
npm run build
```

- Frontend: week grid shows all products as events in best-fit slots; click opens next step / cost / owner / how hard; hamburger reaches Validation and What-if.
- Backend: `sim/` stubs raise until T3–T7. Add pytest under `sim/tests/` per module.

## What breaks it

- Editing `out/predictions.json` after the T4 lock
- Serving only `web/` without Vite middleware for `/config` and `/out` and without `web/mock`
- Putting names, emails, or locations on the form
- Claiming mock accuracy as validated

## Coding standards

[`CLAUDE.md`](CLAUDE.md) is always on.

## Spec split

- Frontend: `web/` (React + TypeScript + Vite)
- Prediction engine: [`backend/`](backend/) (Moment Ledger API)
- Earlier FE handoff notes: [`docs/BACKEND.md`](docs/BACKEND.md)

## Assets

Retailer SVGs from [theSVG](https://thesvg.org/). Pack photos from Open Food Facts. See [`web/assets/ATTRIBUTION.md`](web/assets/ATTRIBUTION.md).
