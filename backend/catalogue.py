"""Product attributes from Open Food Facts (ODbL). `python -m backend.catalogue` refreshes data/catalogue.json.

The search endpoint allows about 10 requests a minute, so this is a build step, not a request-time call.
"""
import json
import time
import urllib.parse
import urllib.request

from .config import DATA

UA = {"User-Agent": "eat-hack-moment-ledger/0.1"}
# (Open Food Facts category tag, shelf category, default serving in g or ml, word the product name must contain)
SHELF = [("protein-bars", "protein & cereal bar", 55, ""), ("energy-drinks", "energy & sports drink", 250, ""), ("iced-coffees", "coffee", 250, ""),
         ("sandwiches", "sandwich & wrap", 180, "sandwich|wrap|baguette|roll|sub"), ("crisps", "crisps & salty snacks", 40, ""), ("yogurts", "yogurt", 150, ""),
         ("kombuchas", "tea", 330, ""), ("chocolate-bars", "confectionery", 45, ""), ("orange-juices", "juice & fruit drink", 250, "juice"),
         ("protein-shakes", "protein & nutrition shake", 330, ""), ("croissants", "cake, cookie & pastry", 60, ""),
         ("salads", "salad & veg", 200, "salad"), ("spring-waters", "water", 500, "water"), ("colas", "soft drink", 330, "")]
LIQUID = {"energy & sports drink", "coffee", "tea", "soft drink", "juice & fruit drink", "water", "protein & nutrition shake"}
CAFFEINE_DEFAULT = {"energy & sports drink": 80, "coffee": 90, "soft drink": 32}   # mg per serving when the record has none
MICRO = ("vitamin", "iron", "calcium", "magnesium", "zinc", "potassium")


def to_item(p: dict, category: str, default_serving: float, must: str = "") -> dict | None:
    n = p.get("nutriments", {})
    name, brand = (p.get("product_name") or "").strip(), (p.get("brands") or "").split(",")[0].strip()
    if not name or not brand or not name.isascii() or not brand.isascii() or any(n.get(k) is None for k in ("energy-kcal_100g", "proteins_100g", "sugars_100g")):
        return None
    if must and not any(w in name.lower() for w in must.split("|")) or (category == "salad & veg" and "cream" in name.lower()):
        return None
    if category in LIQUID and n["energy-kcal_100g"] > 120:               # a kJ value typed into the kcal field
        return None
    try:
        serving = float(p.get("serving_quantity") or 0) or default_serving
    except (TypeError, ValueError):
        serving = default_serving
    if not 0.4 * default_serving <= serving <= 2.5 * default_serving:   # crowd-sourced serving sizes are sometimes whole packs
        serving = default_serving
    f = serving / 100
    kcal, prot, sugar = n["energy-kcal_100g"] * f, n["proteins_100g"] * f, n["sugars_100g"] * f
    caff, src = (n.get("caffeine_100g") or 0) * 1000 * f, "label"
    if caff == 0:
        caff, src = CAFFEINE_DEFAULT.get(category, 0), "category default, not on the record" if category in CAFFEINE_DEFAULT else "none"
    return {"id": p["code"], "name": name, "brand": brand, "category": category, "serving_g": round(serving),
            "kcal": round(kcal), "protein_g": round(prot, 1), "sugar_g": round(sugar, 1),
            "fibre_g": round((n.get("fiber_100g") or 0) * f, 1), "salt_g": round((n.get("salt_100g") or 0) * f, 2),
            "caffeine_mg": round(caff), "caffeine_source": src,
            "micros": {k[:-5]: round(v * f, 4) for k, v in n.items() if k.endswith("_100g") and any(m in k for m in MICRO) and isinstance(v, (int, float))},
            "labels": [l.replace("en:", "") for l in p.get("labels_tags", [])][:8],
            "nutriscore": p.get("nutriscore_grade"), "nova": p.get("nova_group"),
            "caffeinated": int(caff >= 30), "high_protein": int(prot >= 10), "sugary": int(sugar * 4 >= 0.4 * kcal and kcal >= 20),
            "source": "Open Food Facts (ODbL)"}


def search(tag: str, tries: int = 4) -> list:
    q = urllib.parse.urlencode({"countries_tags_en": "united-kingdom", "categories_tags_en": tag, "page_size": 30, "sort_by": "unique_scans_n",
                                "fields": "code,product_name,brands,nutriments,labels_tags,nutriscore_grade,nova_group,serving_quantity"})
    for i in range(tries):
        try:
            req = urllib.request.Request("https://world.openfoodfacts.org/api/v2/search?" + q, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=40)).get("products", [])
        except Exception:
            time.sleep(10 * (i + 1))
    return []


def refresh():
    f = DATA / "catalogue.json"
    have = {i["category"]: i for i in (json.loads(f.read_text()) if f.exists() else []) if i["brand"].isascii() and i["kcal"] <= 900}
    for tag, cat, serving, must in SHELF:
        if cat in have:
            continue
        for p in search(tag):
            item = to_item(p, cat, serving, must)
            if item:
                have[cat] = item
                print(cat, "|", item["brand"], "|", item["name"], flush=True)
                break
        f.write_text(json.dumps(list(have.values()), indent=1))
        time.sleep(7)
    print(len(have), "products")


def load() -> list:
    return json.loads((DATA / "catalogue.json").read_text())


if __name__ == "__main__":
    refresh()
