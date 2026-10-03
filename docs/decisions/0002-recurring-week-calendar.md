# 0002 — Recurring week calendar

## Context

The month grid repeated the same four moment chips on every day while copy said date does not change the score. Users asked for a Google Calendar–style week with brand products placed only in their best moment slot.

## Decision

Use a **recurring week** display chassis (Mon–Sun × hours). Events repeat across weekdays. Weekday is decorative; scores stay persona × moment. Primary axis is brand → products → one best-fit moment. Click opens an opportunity panel; Drill-down is removed from nav.

## Alternatives rejected

- Persona × moment matrix as the only view — clearer data model, but rejects the confirmed calendar metaphor.
- Date-keyed week with prev/next navigation — implies Tuesday differs from Wednesday; no DOW data exists.
- Cell-level shared `actions` — lies once a brand has multiple products; replaced with `actions_by_product`.

## Cost and revisit trigger

Weekdays look like a real calendar while scores do not vary by day. Revisit when store-level or DOW footfall lands, or if judges consistently misread the chassis as scheduling.
