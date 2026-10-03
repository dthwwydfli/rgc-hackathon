# 0001 — Serve FE from mock until T4 lock

## Context

Frontend must ship before the simulation lock (T4) and live CSV scoring. Judges need a working timetable with solid/dashed cells.

## Decision

Ship `web/mock/*.json` fixtures with the same shapes as `config/` and `out/`. Loaders try live paths first (`../config`, `../out`), then fall back to mock. UI banner labels placeholder data.

## Alternatives rejected

- Block FE until T4 — loses weekend demo path
- Hardcode shares in JS — violates “no magic numbers” and drifts from BE contracts
- Fake “live” without a banner — theatre; banned by CLAUDE.md

## Cost and revisit trigger

Mock accuracy is not validation. Revisit when `out/predictions.json` is locked at T4 and `out/results.json` is produced from the live CSV; then remove the mock banner for those files.
