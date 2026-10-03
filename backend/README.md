# Moment Ledger backend

Answers one question: **at which time, at which store, does which persona buy what?** Then turns each answer into a logged stocking decision that is scored when sales arrive.

Rebuilt 3 Oct 2026 on retail data; the team's 28 personas added 15:15. Every number below was computed on this machine; commands are at the end.

## Inputs and output

```
 location            28 personas             time            calendar
 a store: retailer,  built from shopping     hour, day of    bank holidays, the three
 format, postcode,   habits of 1,730 real    week            days before one, weather
 neighbourhood       households
      |                   |                    |                 |
      +-------------------+---------+----------+-----------------+
                                    v
   TRIPS    how many trips each persona makes to this store in each hour      (panel rates x neighbourhood)
   PICKS    P(trip contains product group | persona, hour, day, calendar, mission)   <- TabICL / TabFM
   UNITS    trips x picks x lines per group x category split x neighbourhood taste x calibration
                                    |
                                    v
   per store, date, hour: units by category and by persona, with a range and an order quantity
                                    |
   PLAN LOOP     sceptic checks -> typed decision (Jev) -> ledger
   LEARN LOOP    actual sales -> score -> recalibrate -> next plan
```

A location is a store. `GET /stores` lists 2,059 London supermarkets and convenience stores from Geolytix Retail Points (June 2026): 522 Tesco stores, plus Sainsbury's, Co-op, M&S, Lidl, Waitrose and others. A TfL station still works as a location for a kiosk, using the earlier footfall model.

## Data

| Role | Dataset | Size | Licence |
|---|---|---|---|
| Who shops when and what a trip contains | dunnhumby The Complete Journey, 2017 | 1.47M line items, 2,469 households, 457 stores, every line timestamped | dunnhumby source files, free for research; do not commit to a public repo |
| Stores | Geolytix Retail Points v46 | 19,299 UK stores; 2,059 in Greater London used | Geolytix open data licence |
| Neighbourhood taste and age structure | Tesco Grocery 1.0 (Clubcard purchases, 2015) | 983 London MSOAs, 17 categories; 1,856 of the stores matched | CC BY 4.0 |
| Calendar | gov.uk bank holidays; Open-Meteo | to 2028 | OGL; CC BY 4.0 |
| Product attributes and claims | Open Food Facts; GB health claims register | as before | ODbL; OGL |

Kept from the earlier build only where it still helps: TfL footfall (station kiosks), NHANES (time of day and nutrients of what people eat, not what they buy in a store), the Edinburgh bakery (first loop test). dunnhumby is the data-science arm of Tesco, but this panel is a US grocer: shopping behaviour is American, stores and neighbourhoods are British.

Two fixes made to the raw data: timestamps are UTC and were moved to US Eastern (trips then peak at 17:00 and bottom out at 03:00); non-food lines are dropped.

## The 28 personas

The personas are the team's 28 shopper types: **kinds of individual**, not places. `shopper_personas.py`. Location is a separate input (next section).

Each household in the panel is scored on 17 habits measured at the till, and each persona is a stated combination of those habits. A household's persona is the one on which it is most unusual.

| Measured from till behaviour (15) | How |
|---|---|
| Bargain Hunter | items on promotion, trips using a coupon |
| Luxury Loyalist | pays above the category's typical price, branded, rarely on promotion |
| Value Optimizer | own label, below-typical prices |
| Comparison Expert | splits trips across many stores |
| Ethical Consumer | share of organic and natural products |
| Impulse Buyer | checkout-lane confectionery and magazines |
| Mission Shopper | small, frequent baskets of things bought before |
| Habitual Creature | same products, same store |
| Seasonal Splurger | spend concentrated before holidays |
| Bulk Buyer | few, very large trips |
| Spontaneous Adventurer | share of products never bought before |
| Methodical Perfectionist | fixed day and hour |
| Humanistic Connector | spend at staffed counters |
| Decisive Alpha | quick small trips at lunch and after work |
| Gift-Giver | cards, wrap, party supplies, flowers |

**Thirteen cannot be measured from till data** and carry no weight until a survey links them: Window Shopper (buys nothing), Multi-Size Guard (apparel returns), Digital-First, Brick-and-Mortar Traditionalist, Webroomer, Showroomer, Click-and-Collect Devotee, Tech Innovator (channel and technology use are not in the panel), Skeptical Critic, Status Seeker (attitudes), Social Groupie, Trend Follower (social influence), Community Advocate (avoids chains, so is absent from a chain's data).

Each of the 15 has 95 to 159 households out of 1,864. The definitions are ours and can be edited in `MEASURED` at the top of the file.

### Test: do the personas predict what a trip contains?

Fast version, about two minutes: profile households on 10 weeks sampled from the first half of the year, predict their trips in 8 weeks sampled from the second half, score only on 457 households the model never saw. Mean AUC over six product groups; 0.5 is chance. TabICL throughout.

| What the model is given | Mean AUC |
|---|---|
| Demographics | 0.524 |
| When only (hour, day type, pre-holiday) | 0.548 |
| One named persona + when | 0.561 |
| Data-driven clusters, 1 of 28, + when | 0.590 |
| Scores on all 15 personas + when | 0.615 |
| When + trip mission (top-up or stock-up) | 0.708 |
| One named persona + when + mission | 0.712 |
| Scores on all 15 personas + when + mission | **0.727** |

- A single persona label adds little (0.548 to 0.561) and does less well than unnamed clusters (0.590). People are blends: giving the model the shopper's score on every persona recovers the loss and beats the clusters (0.615).
- Trip mission, which the store format sets, is the largest single input (0.548 to 0.708).
- Recommendation: show the primary persona in the product, predict from the full score profile.

### UK survey: more personas, and persona mix by kind of place

`survey_personas.py`, from the FSA's Food and You 2 (Wave 11, 5,898 UK adults, OGL). It has no question on which store people use, so it says which personas live in which kind of neighbourhood.

- **Five more personas are measured in the UK:** Digital-First (53% of adults have ordered through a delivery app), Community Advocate (23% started buying local), Tech Innovator (18% used a food-sharing app), Skeptical Critic (16% not confident in the supply chain), Trend Follower (6.5% ordered through social media). They have a local share at every store (`local_personas`) but no basket behaviour, so no unit forecast. Eight personas still have no data.
- **Does the kind of place predict the persona?** TabICL from age band, deprivation quintile, urban/rural and region, on held-out respondents (AUC): Digital-First 0.84, Trend Follower 0.73, Tech Innovator 0.72, Community Advocate 0.62, Value Optimizer 0.59, Ethical Consumer 0.57, Decisive Alpha 0.56; Bargain Hunter, Impulse Buyer, Methodical Perfectionist, Humanistic Connector and Skeptical Critic 0.50-0.54. Channel and technology personas depend on place and age; price and attitude personas are spread almost evenly.
- **Use:** the store's persona mix is tilted only for the three till personas above 0.55. The tilt is small (0.8 to 1.2).

### Which persona goes to which store format (synthetic data)

`sortofreal.py`, from dunnhumby's "Let's Get Sort-of-Real" 50,000-customer sample. **This dataset is synthetic**: dunnhumby built it to replicate patterns in real till data, and its terms of use were not read. Ten of the personas can be measured in it. Fast run (48 seconds): 10 weeks sampled across the first year to profile 21,100 customers, 6 later weeks to test.

| Persona | Convenience | Small supermarket | Supermarket | Superstore |
|---|---|---|---|---|
| Mission Shopper | x1.30 | x1.24 | x0.88 | x0.83 |
| Decisive Alpha | x1.30 | x1.13 | x0.92 | x0.83 |
| Bulk Buyer | x0.50 | x0.72 | x1.16 | x1.23 |
| Value Optimizer | x0.71 | x0.79 | x1.08 | x1.32 |
| Habitual Creature | x0.67 | x0.95 | x1.08 | x0.94 |

(share of the persona's trips at that format over the all-customer share; the other five personas are within 0.85-1.15). These multipliers set each store's persona mix by format.

Held-out test, customers the model never saw, later weeks (AUC):

| Predicting | When only | One named persona + when | Scores on all 10 + when |
|---|---|---|---|
| Trip is a full shop | 0.50 | 0.68 | 0.76 |
| Trip is at a convenience or small store | 0.52 | 0.53 | 0.57 |
| Trip is in the evening | 0.48 | 0.53 | 0.56 |

Personas predict the kind of trip well, and the store format and hour only weakly.

**Hour curve check.** The model's hourly trip curve (from the US panel) correlates 0.59 to 0.61 with this dataset's curve for the same format, and peaks later (17:00 against 12:00 for convenience, 14:00 for superstores). Time of day is the least certain part of the model.

### Earlier persona designs

Neighbourhood types fitted to Tesco purchases (`uk_personas.py`) are kept as the location model, and are returned with each store as `neighbourhood`. Their test is in the UK check below.

## The engine tested on UK data, in one pass

`uk_backtest.py`, 3 minutes. The product's own engine (`store_sim.simulate`) is run for all 522 London Tesco stores (1,044 simulations) with its real inputs: store locations and formats, catchments, the personas with their survey tilt and format preferences, hours, calendar, UK category levels. The output is traced back through the catchments to where the shoppers live and compared with what residents really bought at Tesco.

Held back to keep it honest: 294 of 983 neighbourhoods have their Tesco purchases hidden. For those the engine gets a taste predicted from who lives there (TabICL, fitted on the other neighbourhoods using January, April and July) and is scored on their real purchases in October and December.

| Test on the held-out neighbourhoods | Engine | For comparison |
|---|---|---|
| Basket mix (16 category shares), correlation with the real basket | 0.97, average gap 1.1 share points | 0.75 for the US panel's basket with no UK data; 0.99 for giving every neighbourhood the London average |
| How neighbourhoods differ from each other, rank correlation per category | 0.40, positive for 15 of 16 categories | 0 for the London average; 0.64 for the neighbourhood model before it passes through stores and catchments |
| Tesco trips by residents of each neighbourhood, rank correlation | 0.27 | no baseline; relative only |

- The engine turns an American basket into a recognisably London one (0.75 to 0.97). A one-number-per-category calibration, learned on the training neighbourhoods only, took it from 0.93 to 0.97 and is now used by the product.
- It predicts the direction in which neighbourhoods differ (0.40), but passing through stores and catchments blurs that signal: the neighbourhood model alone reaches 0.64. On the basket-mix measure, the plain London average is still slightly closer than the engine.
- Volume is the weakest part (0.27).
- Tesco's data has no time of day and no personas, so hours and personas are not tested here. They are tested on the household panel below.

## End-to-end backtest

`backtest.py`, 90 seconds. Everything the model uses is rebuilt from weeks 1-40 of the household panel only: persona assignment, trip rates, hour shapes, the TabICL pick grid, basket depth, category split, calendar uplift. It then predicts six later weeks (42, 44, 46, 47, 50, 52; 42 days) and is scored against what the same 1,838 households actually bought (126,592 line items). The panel is treated as one store, so this tests who, when and what, not location.

| Question | Result |
|---|---|
| Total units over the 42 days | predicted 127,435, actual 126,592 (0.7% over) |
| Total trips | predicted 13,861, actual 13,446 (3% over) |
| When: trips by persona and hour (255 cells) | correlation 0.95, error 17% of trips |
| When: trips by hour, all personas | correlation 0.99, error 6% |
| What: units by persona, moment and category (3,570 cells) | correlation 0.94, error 26% of units |
| Same cells if every persona bought the average mix | correlation 0.82, error 38% |
| Same cells from each persona's own weeks 1-40 average | correlation 0.95, error 25% |

Day by day (units by date, moment and product group; error as a share of units):

| Forecast | All 42 days | 3 holiday or pre-holiday days |
|---|---|---|
| Persona model, frozen at week 40 | 0.256 | 0.368 |
| Mean of the last 4 weeks (updated every week) | 0.251 | 0.419 |
| Same weekday last week | 0.313 | 0.393 |

- Personas matter for the "what": removing them takes the error from 26% to 38%.
- The model does no better than each persona's plain historical average on these cells. Its use is that it produces the same accuracy from parts (trips, hours, picks) that can be recombined for a new store, date or calendar event.
- Frozen at week 40 and predicting up to twelve weeks ahead, it matches a 4-week mean that is refreshed weekly, and does better on the three holiday days.
- What makes each persona distinctive is predicted with a correlation of 0.59 (Seasonal Splurger) to 0.98 (Humanistic Connector); 12 of 15 are above 0.7.
- Limits: the test households are the ones the personas were assigned from (a loyalty-card setting), it is US data, and three holiday days is a small sample.

## Where TabICL / TabFM sits

`fit()` stores context rows and `predict()` is one forward pass, so new data is usable as soon as it is loaded. `TAB_BACKEND=tabicl|tabfm|gbm`; TabFM has the same interface but its 6 GB weights did not download on the venue network.

| Use | Module | Context | Predicts | Held-out result |
|---|---|---|---|---|
| Picks | `retail.py` | 6,000 real trips with the persona's 18 habits, hour, day type, pre-holiday, mission | Whether a trip contains each of 10 product groups | Table above |
| Sales | `calibrate.py` | 6,000 day-moment-group cells with lags and calendar flags | Units | Table below |

The pick grid (28 personas x 17 hours x 2 day types x 2 calendar states x 2 missions, 10 models) builds in under 3 minutes and is cached; requests take about 0.2 seconds per store-day.

### Sales backtest on retail data

dunnhumby panel, units per day, moment and product group. 302 days to learn from, the last 56 held out (179,333 units, including Thanksgiving and Christmas). Absolute error as a share of units.

| Forecast | All held-out days | 11 holiday and pre-holiday days |
|---|---|---|
| Same weekday last week | 0.392 | 0.532 |
| Mean of the last 4 weeks | 0.310 | 0.472 |
| In-context model | 0.291 | 0.471 |
| In-context model + calendar flags | **0.285** | **0.451** |

The in-context model with calendar flags is 8% better than the 4-week mean overall and 4% better on holiday days. One split.

## UK check against real Tesco purchases

No open dataset has sales for an individual UK store, so a store-level test is not possible yet. Tesco Grocery 1.0 (real Clubcard purchases, 983 London areas) allows two area-level tests, with the Tesco data used as the answer and not as an input. `exploration/t1_uk_check.py`.

**A. Does the US panel's basket look like a London Tesco basket?** Partly. Across 17 shared categories the shares correlate at r = 0.63, with an average gap of 3.8 share points. London buys about twice the share of fruit and vegetables (28% against 13%) and a third of the soft drinks (3% against 10%), and more wine and water. Uncorrected, the model put soft drinks top in every time block, which is an American result. Category levels are now scaled to the Tesco ones.

**B. Can a neighbourhood's purchases be predicted from who lives there?** Yes. Fitted on 688 neighbourhoods using January, April and July and scored on the other 295 using October and December, rank correlation between predicted and actual category index, averaged over 17 categories: 0.00 for the first design (US personas tilted by age), 0.62 for 28 neighbourhood types, 0.65 with TabICL reading the mixture of types, 0.69 for TabICL straight from 32 demographic fields. Inside London the product uses each neighbourhood's real Tesco profile; this model is what would carry it to places without Tesco data.

Caveats: Tesco's 17 categories are narrower than ours (its "ready-made" is not all food to go), the data is 2015 and all Tesco formats together, and after the scaling test A can no longer be used as validation.

## Store catchments

`catchment.py`. A Huff gravity model: a resident's chance of using a store rises with its floor space and falls with the square of distance, against every other store within 3 km. Built from the 2,059 store locations and the population-weighted centres of 983 London neighbourhoods.

- A store's shoppers no longer come only from the neighbourhood it stands in. The median store draws 24% of its resident shoppers from its own neighbourhood; the rest come from those around it. Taste, persona tilt and neighbourhood type are now averaged over the catchment.
- Baskets per day is the store's share of the resident demand around it, not a fixed number per size band: median 247 for a convenience store, about 3,400 for a superstore. The level rests on an assumed 0.19 grocery trips per resident per day.
- **Check against real data:** the share of each neighbourhood's trips the model sends to Tesco stores correlates at 0.40 (rank correlation, 983 areas) with Tesco's real Clubcard penetration there. Moderate. Distance decay of 2 and a 3 km reach were the best of the settings tried on that same check, so it is a calibration, not an independent test.
- Residents only. Commuters and visitors are still not modelled; that needs workplace population or footfall around each store.
- YouGov's 2025 brand consideration scores were tried as a brand weight and did not improve the check (0.395 against 0.397), so they are not used. Only five brands had a published score.

## Store simulation

`store_sim.py`. For a Tesco Express in Camden on a Friday the model returns 1,137 trips. Fruit, vegetables and bread lead in the morning and at lunch, confectionery leads from 17:00, and ice cream over-indexes late (x1.5). `P24` (frequent top-up) makes 15% of the trips and leads confectionery; `P14` buys beer and wine at 17:00; `P09` comes at 13:00 for fruit, bread and milk.

What the store contributes:
- **Format.** Size band sets the store's pull in the catchment model and the mission: convenience and small formats are modelled with top-up trips (five lines or fewer), larger ones with stock-up trips. The panel has too few small-store trips to model format directly.
- **UK level.** Each category is scaled by London Tesco share over US panel share (see the UK check), clipped to 0.3-3.5.
- **Neighbourhood taste.** The area's Tesco category share against the London mean, e.g. wine x1.32 and tea and coffee x0.81 around one Camden store.
- **Neighbourhood age.** Personas with more older or family households gain weight where the area has more over-65s or children.

`GET /persona` answers the question for one persona at one store (when they come, what they buy). `GET /where` ranks stores for a persona.

## The product call

The user picks a store, a day of the week and an hour. `GET /recommend` returns, for the next 12 weeks:

- **stock most:** categories ranked by expected units in that hour, with a range, a stock quantity (85th percentile), the persona that buys most of it, and example products where the catalogue has one;
- **sells unusually well in this slot:** categories whose share in that hour is highest against their share over the whole day;
- **shoppers in this slot,** the store's neighbourhood types and local persona shares;
- **week by week,** with the weeks that differ: bank holidays, the three days before one, and Christmas Day (closed).

Example, Tesco Express in Camden, Fridays 17:00-18:00: stock most fruit, vegetables, bread, milk, confectionery; unusually strong wine (x1.39), ice cream and beer (x1.24); 28% of shoppers are Mission Shoppers. Saturdays 21:00: beer x1.49, ice cream x1.41, wine x1.33. A Camden superstore, Wednesdays 12:00: food to go and deli x1.25, coffee x1.15.

Two things to know. The model has no seasonal trend, so every ordinary week in the 12 gets the same forecast and only calendar events change it. And it recommends kinds of product (34 categories); named products appear only where the 13-item catalogue has one.

## Jev and the agent loops

Jev (TypeSafe AI's System One model) returns typed answers with probabilities: a Choice among options, a Score on a rubric, a Noul (probability a statement is true). It writes no text, which is what a ledger needs. `jev.py` uses the `typesafe-sdk` package and is wired in three places:

| Job | Type | Where |
|---|---|---|
| Free-text product to shelf category and attributes | Choice over 34 categories, four Nouls | `POST /classify` |
| What to do about a store-moment-category cell: stock up, hold, cut back, test first; evidence strength 1-5; needs review | Choice, Score, Noul | Plan loop, top five categories per moment |
| Which item a persona picks from a shelf, to split a category among items with no sales history | Choice with probabilities | `jev.persona_choice` |

**Jev has not been called.** There is no `TYPESAFE_API_KEY` on this machine, so each function ran its fallback rule and says so in its `source` field. The request shapes were checked against the installed SDK (0.7.2). Set the key and the same calls go to Jev.

Numbers never come from Jev or from an LLM. The tabular model produces every forecast; Jev classifies and decides around it.

| Loop | What it does | Status |
|---|---|---|
| Plan | Simulate a store-day, group hours into moments, run the sceptic, take a typed decision for the top categories, write one ledger entry per moment | Runs |
| Sceptic | Flags assumed volume, stores with no scored sales, personas resting on fewer than 10 households, unsupported health claims | Runs, rule-based |
| Learn | Scores decisions against actual sales, refits a scalar per category then per moment, logs it | Runs |
| Review | Claude agent reads the ledger, backtest and claims register through tools and records a verdict | Written, not run (no Anthropic credentials) |

The learn loop was tested earlier on the bakery tills: from a cold start it cut error from about 1.4 to 0.66 by week 2. It has not been replayed on the retail data.

## Shelf plan

The forecast is hourly; the action should not be. `shelf.py` reads the simulation and returns the refill hours that keep the most margin after labour, per day type, with expected lost units from Poisson demand against shelf capacity.

Week of 5 Oct 2026, per fixture, against one refill per moment: Bank and Monument +£891 (seven weekday visits, four before 11:00, cut lost units from 247.5 to 26.9 a day), London Bridge +£292, Camden Town +£85 (two visits a day instead of six).

It also places items by zone using basket size at the bakery tills as a stand-in for time in store. On the data in hand that moves 0 of 13 items against best-sellers-by-the-door, so it is reported as a null result.

All figures are computed on the forecast. Wage (£12.71/h), minutes per visit (15), margin (£1 a unit) and fixture size (40 facings of 8) are assumptions set at the top of the file.

## Modules

| File | Job |
|---|---|
| `shopper_personas.py` | The team's 28 personas: definitions, assignment, fast test |
| `survey_personas.py` | UK survey: five more personas, persona mix by kind of neighbourhood |
| `sortofreal.py` | Synthetic till data: persona by store format and hour |
| `uk_personas.py` | Location model: neighbourhood types and their test |
| `retail.py` | dunnhumby loader, panel personas, pick model, trip rates |
| `stores.py` | Store table: Geolytix joined to Tesco neighbourhood profiles |
| `catchment.py` | Gravity model: each store's catchment and share of demand, with its check |
| `store_sim.py` | Store simulation, persona view, store ranking |
| `jev.py` | Typed classification and decisions, with rule fallbacks |
| `uk_backtest.py` | The engine tested on UK data in one pass |
| `backtest.py` | End-to-end backtest on the household panel |
| `calibrate.py` | Sales model and backtests (retail, bakery) |
| `agents.py` | Plan, sceptic, learn and review loops |
| `ledger.py` | Append-only, hash-chained record |
| `shelf.py` | Shelf plan: layout and refill visits |
| `simulate.py` | Dispatch by location; the earlier station model |
| `picks.py`, `data.py`, `catalogue.py`, `claims.py`, `config.py`, `tabular.py` | Station pick model, loaders, products, claims register, shared rules, model switch |
| `api.py` | HTTP API |

## API

`station` in the calls below takes a store id (or a station name).

| Call | Returns |
|---|---|
| `GET /stores?q=&retailer=&borough=` | Stores with id, fascia, format, postcode |
| `GET /stores/{id}` | One store with its neighbourhood profile |
| `GET /personas` | The 28 personas: which are measured, head counts, habits, and the test |
| `GET /neighbourhoods` | Neighbourhood types and their test |
| `GET /recommend?store=&weekday=&hour=&weeks=12` | **The main product call.** For a day of the week and an hour: what to stock most, what sells unusually well in that slot, how much, for which personas, week by week, and which weeks differ because of the calendar |
| `GET /simulate?station=&date=` | Trips per hour with persona mix; units per moment and category with range, order quantity, leading persona, split by persona and hour |
| `GET /persona?persona=&store=&date=` | When that persona comes and what they buy |
| `GET /where?persona=&date=&borough=` | Stores ranked for that persona, with peak hour |
| `POST /classify` | Jev product classification |
| `GET /calendar?station=&start=&days=` | One row per day and moment, with any decision and score |
| `GET /shelfplan?station=&start=&days=` | Layout and refill plan |
| `POST /plan`, `POST /actuals` | Plan loop; learn loop |
| `GET /ledger` | Records plus a chain check |
| `GET /meta`, `GET /products`, `GET /stations`, `POST /replay/bakery` | From the earlier build |

## Run

```bash
.venv/bin/python -m backend.stores            # store table (20 postcode look-ups)
.venv/bin/python -m backend.catchment         # store catchments and the Tesco penetration check (5 s)
.venv/bin/python -m backend.retail            # panel personas, pick grid, trip rates (3 min)
.venv/bin/python -m backend.shopper_personas  # fast persona test on sampled weeks (2 min)
.venv/bin/python -m backend.survey_personas   # UK survey personas by kind of place (50 s)
.venv/bin/python -m backend.sortofreal        # persona by store format, synthetic data (50 s)
.venv/bin/python -m backend.uk_personas       # neighbourhood model and its test (90 s)
.venv/bin/python -m backend.calibrate retail  # retail sales backtest
.venv/bin/uvicorn backend.api:app --port 8000
```

## Limits

- **Timing, personas and calendar effects are American and from 2017.** Category levels, stores, neighbourhood taste and age structure are UK data. No open UK dataset has timestamped baskets per household; a retailer's own loyalty data would replace the panel without code changes.
- **Baskets per day comes from a resident-only gravity model** and an assumed trip rate, so absolute units are illustrative until a store has scored sales. The shape across hours, personas and categories is the modelled part.
- **Neighbourhood data is from 2015** and covers London only.
- **The persona mix at a store rests on weak evidence:** a small survey-based tilt by neighbourhood and format preferences from synthetic data. No real UK data links an individual persona to a specific store.
- **Eight of the 28 personas have no data behind them;** five more are measured only in the survey and have no basket behaviour.
- **Time of day is the least certain part** (see the hour curve check).
- **Persona definitions are ours.** They are stated rules over till habits, not validated against people's own description of themselves.
- **Product groups are coarse** (10 groups, 34 categories; "store cupboard" is a catch-all).
- Ranges are Poisson only. Jev and the Claude review have not been run.
