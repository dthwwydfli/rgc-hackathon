"""Download every data source and build the model tables.  Run from the repo root:  python scripts/setup_data.py

Nothing third-party is stored in this repository; see SOURCES.md for what each file is and its licence.
About 700 MB of downloads and 15 minutes of builds on a laptop. Add --with-stations for the older station-kiosk model
(NHANES and TfL, another 250 MB and about 10 minutes).
This script was assembled from the commands used on the day; it has not been run end to end from a clean checkout.
"""
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data"
UA = {"User-Agent": "Mozilla/5.0 (moment-ledger setup)"}


def get(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    print("downloading", dest.relative_to(D), flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def module(name: str, *args: str):
    print("\n== python -m", name, *args, flush=True)
    subprocess.run([sys.executable, "-m", name, *args], check=True, cwd=D.parent)


def main():
    (D / "cache").mkdir(parents=True, exist_ok=True)
    # dunnhumby The Complete Journey (via the completejourney R package)
    for f in ("transactions.rds", "demographics.rda", "products.rda"):
        get(f"https://github.com/bradleyboehmke/completejourney/raw/master/data/{f}", D / "dunnhumby" / f)
    import pyreadr
    for f, out in (("transactions.rds", "transactions"), ("demographics.rda", "demographics"), ("products.rda", "products")):
        if not (D / "dunnhumby" / f"{out}.parquet").exists():
            list(pyreadr.read_r(str(D / "dunnhumby" / f)).values())[0].to_parquet(D / "dunnhumby" / f"{out}.parquet")
    # Tesco Grocery 1.0, MSOA level
    for name, fid in (("year", 18848378), ("Jan", 18847976), ("Apr", 18847847), ("Jul", 18848015), ("Oct", 18848225), ("Dec", 18847916)):
        get(f"https://ndownloader.figshare.com/files/{fid}", D / "tesco" / f"{name}_msoa_grocery.csv")
    # Geolytix Retail Points
    z = D / "stores" / "geolytix.zip"
    get("https://drive.google.com/uc?export=download&id=1B8M7m86rQg2sx2TsHhFa2d-x-dZ1DbSy", z)
    if not (D / "stores" / "geolytix").exists():
        zipfile.ZipFile(z).extractall(D / "stores" / "geolytix")
    # London MSOA Atlas (an .xls file despite the name on the server)
    get("https://data.london.gov.uk/download/msoa-atlas/39fdd8eb-e977-4d32-85a4-f65b92f29dcb/msoa-data.csv", D / "london" / "msoa-data.xls")
    # ONS MSOA population-weighted centroids, joined to the Tesco file
    if not (D / "london" / "msoa_centroids.csv").exists():
        import pandas as pd
        base = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/MSOA_Dec_2011_PWC_in_England_and_Wales_2022/FeatureServer/0/query"
        rows, off = [], 0
        while True:
            q = urllib.parse.urlencode({"where": "1=1", "outFields": "*", "outSR": 4326, "f": "json", "resultOffset": off, "resultRecordCount": 2000})
            feats = json.load(urllib.request.urlopen(base + "?" + q, timeout=60)).get("features", [])
            if not feats:
                break
            rows += [{"area_id": x["attributes"]["msoa11cd"], "lon": x["geometry"]["x"], "lat": x["geometry"]["y"]} for x in feats]
            off += len(feats)
        t = pd.read_csv(D / "tesco" / "year_msoa_grocery.csv", usecols=["area_id", "population", "representativeness_norm", "num_transactions"])
        t.merge(pd.DataFrame(rows), on="area_id").to_csv(D / "london" / "msoa_centroids.csv", index=False)
    # FSA Food and You 2, Wave 11
    get("https://fsaopendata.blob.core.windows.net/opendatacatalog/2407752501FoodandYou2Wave11AbridgedDataThreeCountriesV1.csv", D / "fy2" / "fy2_w11_abridged.csv")
    # dunnhumby Let's Get Sort-of-Real, 50,000-customer sample (synthetic)
    get("https://downloads.ctfassets.net/psj0p18eh7z1/12PzBBsw5BGLhQlhu5qWlT/a645c6913b42d6987ec97c28a2dfce80/dunnhumby_Let-s-Get-Sort-of-Real-_Sample-50K-customers_.zip", D / "sortofreal" / "sample_50k.zip")
    # calendar, weather, health-claims register
    get("https://www.gov.uk/bank-holidays.json", D / "context" / "uk_bank_holidays.json")
    get("https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12&hourly=temperature_2m,precipitation&timezone=Europe%2FLondon&past_days=7&forecast_days=14", D / "context" / "london_weather_forecast.json")
    get("https://assets.publishing.service.gov.uk/media/6a0c4faf229555d0fe826835/great-britain-nutrition-and-health-claims-spreadsheet-19-may-2026.xlsx",
        D / "claims" / "great-britain-nutrition-and-health-claims-spreadsheet-19-may-2026.xlsx")

    for m in ("backend.stores", "backend.catchment", "backend.retail", "backend.uk_personas", "backend.survey_personas", "backend.sortofreal"):
        module(m)
    for m, a in (("backend.shopper_personas", ()), ("backend.backtest", ()), ("backend.uk_backtest", ()), ("backend.calibrate", ("retail",))):
        module(m, *a)

    if "--with-stations" in sys.argv:
        for f in ("DEMO_L", "WHQ_L", "PAQ_L", "DRXFCD_L", "DR1IFF_L", "DR2IFF_L"):
            get(f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/{f}.xpt", D / "nhanes" / f"{f}.xpt")
        tfl = "https://s3-eu-west-1.amazonaws.com/crowding.data.tfl.gov.uk"
        get(f"{tfl}/Network%20Demand/StationFootfall_2025_2026%20.csv", D / "tfl" / "StationFootfall_2025_2026.csv")
        for d in ("MON", "TWT", "FRI", "SAT", "SUN"):
            get(f"{tfl}/NUMBAT/NUMBAT%202025/NBT25{d}_Outputs.xlsx", D / "tfl" / f"NBT25{d}_Outputs.xlsx")
        get("https://raw.githubusercontent.com/luis-alarcon/Kaggle_BreadBasket/master/dataset/BreadBasket_DMS.csv", D / "bakery" / "BreadBasket_DMS.csv")
        get("https://archive-api.open-meteo.com/v1/archive?latitude=55.95&longitude=-3.19&start_date=2016-10-30&end_date=2017-04-09&hourly=temperature_2m,precipitation&timezone=Europe%2FLondon",
            D / "context" / "edinburgh_weather_2016_2017.json")
        module("backend.picks")
        module("backend.calibrate")
    print("\nready:  uvicorn backend.api:app --port 8000")


if __name__ == "__main__":
    main()
