# Sources

Nothing below is stored in this repository except the two files marked "in repo". `scripts/setup_data.py` downloads the rest from the publisher.

## Data used by the engine

| Source | What it holds | Used for | Licence | Link |
|---|---|---|---|---|
| dunnhumby, The Complete Journey (2017), via the `completejourney` R package | 1.47M line items, 2,469 US households, 457 stores, every line timestamped; demographics for 801 households | Personas from till behaviour; when people shop; what a trip contains; calendar effects; the end-to-end backtest | dunnhumby source files, free for research use; terms not reviewed in full | https://github.com/bradleyboehmke/completejourney , https://www.dunnhumby.com/source-files/ |
| Tesco Grocery 1.0 | Clubcard purchases in 2015 aggregated to 983 London MSOAs: 17 category shares, nutrients, population | UK category levels; neighbourhood taste; the UK test | CC BY 4.0 | https://figshare.com/collections/Tesco_Grocery_1_0/4769354 , https://www.nature.com/articles/s41597-020-0397-7 |
| Geolytix Retail Points v46 (June 2026) | 19,299 UK supermarket and convenience locations with retailer, fascia, size band | Stores as locations; store size in the catchment model | Geolytix open data licence | https://geolytix.com/blog/supermarket-retail-points/ |
| London MSOA Atlas | 2011 Census and related indicators for 983 London MSOAs | Who lives around each store; neighbourhood model | OGL v3 | https://data.london.gov.uk/dataset/msoa-atlas |
| ONS MSOA population-weighted centroids (2011) | A centre point per MSOA | Distances in the catchment model | OGL v3 | https://geoportal.statistics.gov.uk/ |
| FSA Food and You 2, Wave 11 | 5,898 UK adults, 2025: food attitudes and behaviours with age, deprivation, urban/rural, region | Five personas measured in the UK; persona mix by kind of neighbourhood | OGL v3 | https://www.data.gov.uk/dataset/a10cbe40-b769-45a8-987b-4bd53972ad1d/food-and-you-2-survey-wave-11 |
| dunnhumby, Let's Get Sort-of-Real (50,000-customer sample) | **Synthetic** till data built to mimic real patterns: customer, store format, region, hour, basket type | Which personas favour which store format; a check on the hourly curve | dunnhumby source files; terms not reviewed | https://www.dunnhumby.com/source-files/ |
| gov.uk bank holidays (in repo) | Bank holidays to 2028 | Calendar | OGL v3 | https://www.gov.uk/bank-holidays.json |
| Open-Meteo | Hourly weather forecast and history | Shown alongside each slot; not a model input | CC BY 4.0 | https://open-meteo.com/ |
| Open Food Facts (13 products, in repo as `data/catalogue.json`) | Brand, nutrition and labels for example UK products | Example products per category | ODbL | https://world.openfoodfacts.org/ |
| GB nutrition and health claims register (19 May 2026) | 2,557 health claims with authorised or not | Checking which health benefits may be claimed | OGL v3 | https://www.gov.uk/government/publications/great-britain-nutrition-and-health-claims-nhc-register |
| postcodes.io | Postcode to MSOA and borough | Placing stores in neighbourhoods | Open (ONS data, OGL) | https://postcodes.io/ |

## Used by the earlier station-kiosk model (optional, `--with-stations`)

| Source | What it holds | Licence | Link |
|---|---|---|---|
| NHANES Aug 2021-Aug 2023 dietary recall | What 4,983 US adults ate, with clock time, place and nutrients | US public domain | https://wwwn.cdc.gov/nchs/nhanes/ |
| TfL station footfall and NUMBAT 2025 | Daily taps per station and typical quarter-hour flows | TfL open data terms | http://crowding.data.tfl.gov.uk/ |
| The Bread Basket, Edinburgh | Till data from one bakery, 2016-17 | CC0 | https://github.com/luis-alarcon/Kaggle_BreadBasket |

## Models and tools

| Tool | Use | Licence |
|---|---|---|
| TabICL 2.2.0 | In-context tabular model for every prediction | BSD-3 |
| TabFM 1.0.0 (Google) | Same interface, supported by `TAB_BACKEND=tabfm`; not used, the 12 GB weights did not download | Code Apache-2.0, weights non-commercial |
| Jev (TypeSafe AI), `typesafe-sdk` | Typed classification and decisions; wired in, not called | Commercial API |
| Claude (Anthropic SDK) | Review agent; wired in, not called | Commercial API |

## Looked at and not used

| Source | Why not |
|---|---|
| Co-op and Sainsbury's loyalty data at the Consumer Data Research Centre | Safeguarded: needs an approved research application |
| Kantar Worldpanel, Circana | Commercial licence |
| Open banking transaction feeds | Need customer consent or a commercial agreement |
| YouGov supermarket rankings 2025 | Scores for five brands only; tried as a brand weight in the catchment model and made no difference |
| Kantar social-grade figures via The Grocer | From 2015, discounters only |
| CDRC Priority Places for Food Index, Internet User Classification | Duplicates what the survey already gives |
| Google popular times | Scraping breaks the terms of use |
| FreshRetailNet-50K, Open e-commerce 1.0, Twin-2K-500, USDA FoodAPS | Not UK, or not grocery baskets by time |

## Papers and articles

- Aiello et al. 2020, Tesco Grocery 1.0, Scientific Data: https://www.nature.com/articles/s41597-020-0397-7
- Syrjälä et al. 2025, the persona in market segmentation, Journal of Business Research: https://doi.org/10.1016/j.jbusres.2025.115387
- Whelan and Davies 2006, own-brand and national-brand consumers, Journal of Retailing and Consumer Services: https://doi.org/10.1016/j.jretconser.2006.02.004
- Khatri et al. 2022, personality from behaviour in a virtual store, Frontiers in Psychology: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.752073/full
- Salesforce, buyer persona guide: https://www.salesforce.com/sales/buyer-persona/
- Do Synthetic Personas Predict Real Audience Response? arXiv 2609.25010
- When Can Digital Personas Reliably Approximate Human Survey Findings? arXiv 2605.10659
- When Can You Trust Your Synthetic Users? arXiv 2609.13148
- LLM-Powered Virtual Population for Demand Simulation and Pricing, arXiv 2606.16183
- Leeds/CDRC work on grocery store sales by time of day: https://eprints.whiterose.ac.uk/id/eprint/118231/
- Loyalty-card data donation pilot (Tesco Clubcard portability): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10895564/
- UK Smart Data schemes under the Data (Use and Access) Act 2025: https://technologyquotient.freshfields.com/post/102kq6j/uk-data-reforms-unpacked-the-new-smart-data-schemes-and-what-businesses-need-to
