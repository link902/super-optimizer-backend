"""Daily, allowlisted price refresh for 27 verified Super-Optimizer rows.

Only product pages that were manually verified and are pinned below can be fetched.
Failed, ambiguous, identity-mismatched, or unparseable pages are skipped without
changing the prior valid price or checked timestamp. Secrets are read only from env.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from supabase import create_client

# These are the verified existing rows; this job never inserts product rows.
PILOT = {
    240: {
        "supermarket_id": 2, "brand": "Colun", "brand_aliases": ["colun"],
        "source_url": "https://www.jumbo.cl/leche-entera-colun-caja-1-l-natural/p",
        "name_tokens": ["leche", "entera"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])",
        "size_ml": 1000,
    },
    246: {
        "supermarket_id": 1, "brand": "Nestlé", "brand_aliases": ["nestle"],
        "source_url": "https://www.lider.cl/ip/cremas/crema-de-leche-para-batir-y-cocinar-caja/00780295002232",
        "name_tokens": ["crema", "batir"], "size_regex": r"(?<!\d)200\s*ml(?![a-z])",
        "size_ml": 200,
    },
    250: {
        "supermarket_id": 2, "brand": "Colun", "brand_aliases": ["colun"],
        "source_url": "https://www.jumbo.cl/crema-de-leche-colun-caja-200-ml/p",
        "name_tokens": ["crema", "leche"], "size_regex": r"(?<!\d)200\s*ml(?![a-z])",
        "size_ml": 200,
    },
    251: {
        "supermarket_id": 1, "brand": "Líder", "brand_aliases": ["lider"],
        "source_url": "https://super.lider.cl/ip/reposteria/leche-evaporada-tarro/00040000766328",
        "name_tokens": ["leche", "evaporada"], "size_regex": r"(?<!\d)410\s*g(?![a-z])",
        "size_ml": 410,
    },
    252: {
        "supermarket_id": 2, "brand": "Ideal", "brand_aliases": ["ideal"],
        "source_url": "https://www.jumbo.cl/leche-evaporada-ideal-390g-1976555/p",
        "name_tokens": ["leche", "evaporada"], "size_regex": r"(?<!\d)390\s*g(?![a-z])",
        "size_ml": 390,
    },
    281: {
        "supermarket_id": 2, "brand": "Soprole", "brand_aliases": ["soprole"],
        "source_url": "https://www.jumbo.cl/queso-crema-dos-alamos-soprole-200-g/p",
        "name_tokens": ["queso", "crema"], "size_regex": r"(?<!\d)200\s*g(?![a-z])",
        "size_ml": 200,
    },
    282: {
        "supermarket_id": 2, "brand": "Colun", "brand_aliases": ["colun"],
        "source_url": "https://www.jumbo.cl/queso-crema-colun-200-g/p",
        "name_tokens": ["queso", "crema"], "size_regex": r"(?<!\d)200\s*g(?![a-z])",
        "size_ml": 200,
    },
    283: {
        "supermarket_id": 1, "brand": "Líder", "brand_aliases": ["lider"],
        "source_url": "https://super.lider.cl/ip/conservas/atun-lomitos-en-agua/00040000114316",
        "name_tokens": ["atun", "lomitos", "agua"], "size_regex": r"91\s*g.*140\s*g",
        "size_ml": 140,
    },
    284: {
        "supermarket_id": 2, "brand": "Cuisine & Co", "brand_aliases": ["cuisine & co"],
        "source_url": "https://www.jumbo.cl/atun-cuisine-and-co-lomitos-en-agua-91-g-drenado-140-g-neto-2017687/p",
        "name_tokens": ["atun", "lomitos"], "size_regex": r"140\s*g(?![a-z])",
        "size_ml": 140,
    },
    285: {
        "supermarket_id": 1, "brand": "San José", "brand_aliases": ["san jose"],
        "source_url": "https://super.lider.cl/ip/pescados-y-mariscos/filete-de-jurel-al-natural/00780123500563",
        "name_tokens": ["filete", "jurel", "natural"], "size_regex": r"125\s*g(?![a-z])",
        "size_ml": 125,
    },
    286: {
        "supermarket_id": 2, "brand": "San José", "brand_aliases": ["san jose"],
        "source_url": "https://www.jumbo.cl/filet-jurel-natur-2085295/p",
        "name_tokens": ["filete", "jurel", "natural"], "size_regex": r"80\s*g(?![a-z])",
        "size_ml": 80,
    },
    4: {
        "supermarket_id": 1, "brand": "Colun", "brand_aliases": ["colun"],
        "source_url": "https://super.lider.cl/ip/leche/00780292077754",
        "name_tokens": ["leche", "entera"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000,
    },
    11: {
        "supermarket_id": 2, "brand": "Cuisine & Co", "brand_aliases": ["cuisine & co"],
        "source_url": "https://www.jumbo.cl/leche-entera-1-l-cuisine-and-co-1858321/p",
        "name_tokens": ["leche", "entera"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000,
    },
    287: {"supermarket_id": 1, "brand": "Surlat", "brand_aliases": ["surlat"], "source_url": "https://super.lider.cl/ip/leche/leche-entera/00780461747028", "name_tokens": ["leche", "entera"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    288: {"supermarket_id": 2, "brand": "Colun", "brand_aliases": ["colun"], "source_url": "https://www.jumbo.cl/leche-descremada-colun-1-l-2/p", "name_tokens": ["leche", "descremada"], "exclude_tokens": ["semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    289: {"supermarket_id": 1, "brand": "Colun", "brand_aliases": ["colun"], "source_url": "https://super.lider.cl/ip/leche/leche-semidescremada-natural-caja/00780292000009", "name_tokens": ["leche", "semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    290: {"supermarket_id": 1, "brand": "Surlat", "brand_aliases": ["surlat"], "source_url": "https://super.lider.cl/ip/leche/leche-descremada/00780461747030", "name_tokens": ["leche", "descremada"], "exclude_tokens": ["semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    291: {"supermarket_id": 2, "brand": "Surlat", "brand_aliases": ["surlat"], "source_url": "https://www.jumbo.cl/leche-descremada-surlat-b-a-1l-1991552/p", "name_tokens": ["leche", "descremada"], "exclude_tokens": ["semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    292: {"supermarket_id": 2, "brand": "Surlat", "brand_aliases": ["surlat"], "source_url": "https://www.jumbo.cl/leche-entera-surlat-b-a-1l-1991554/p", "name_tokens": ["leche", "entera"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    293: {"supermarket_id": 1, "brand": "Colun", "brand_aliases": ["colun"], "source_url": "https://super.lider.cl/ip/leche/leche-descremada-natural-caja-1-l/00780292000008", "name_tokens": ["leche", "descremada"], "exclude_tokens": ["semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    294: {"supermarket_id": 2, "brand": "Surlat", "brand_aliases": ["surlat"], "source_url": "https://www.jumbo.cl/leche-semidesc-surlat-b-a-1l-1991553/p", "name_tokens": ["leche", "semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    295: {"supermarket_id": 2, "brand": "Colun", "brand_aliases": ["colun"], "source_url": "https://www.jumbo.cl/leche-colun-semi-descremada-1-litro/p", "name_tokens": ["leche", "semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    296: {"supermarket_id": 1, "brand": "Surlat", "brand_aliases": ["surlat"], "source_url": "https://super.lider.cl/ip/leche/leche-semidescremada/00780461747029", "name_tokens": ["leche", "semidescremada"], "size_regex": r"(?<!\d)1\s*(?:l|lt|litro)(?![a-z])", "size_ml": 1000},
    297: {"supermarket_id": 1, "brand": "Oikos", "brand_aliases": ["oikos"], "source_url": "https://super.lider.cl/ip/yoghurt/yoghurt-griego-natural-sin-azucar-pote/00780295500779", "name_tokens": ["yoghurt", "griego", "natural"], "size_regex": r"(?<!\d)150\s*g(?![a-z])", "size_ml": 150},
    298: {"supermarket_id": 2, "brand": "Oikos", "brand_aliases": ["oikos"], "source_url": "https://www.jumbo.cl/yoghurt-natural-danone-150-g/p", "name_tokens": ["yogurt", "griego", "natural"], "size_regex": r"(?<!\d)150\s*g(?![a-z])", "size_ml": 150},
    299: {"supermarket_id": 1, "brand": "Colun", "brand_aliases": ["colun"], "source_url": "https://super.lider.cl/ip/yoghurt/yoghurt-origen-natural/00780292001206", "name_tokens": ["yoghurt", "origen", "natural"], "size_regex": r"(?<!\d)150\s*g(?![a-z])", "size_ml": 150},
    300: {"supermarket_id": 2, "brand": "Colun", "brand_aliases": ["colun"], "source_url": "https://www.jumbo.cl/yogurt-natur-150gr-2065862/p", "name_tokens": ["yogurt", "natural", "colun"], "size_regex": r"(?<!\d)150\s*g(?![a-z])", "size_ml": 150},
}
PRICE_KEYS = {"price", "saleprice", "currentprice", "sellingprice", "offerprice", "priceamount", "finalprice"}
REGULAR_KEYS = {"regularprice", "originalprice", "listprice", "oldprice", "wasprice", "previousprice", "pricebeforediscount", "pricebeforediscount"}
CONDITIONAL_RE = re.compile(r".{0,70}(?:mi\s*club|club\s*jumbo|tarjeta|con\s+tu\s+tarjeta|comprando\s+\d|segunda\s+unidad|banco\s+).{0,100}", re.I)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).lower().strip()


def parse_clp(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(round(float(value)))
    else:
        digits = re.sub(r"[^0-9]", "", str(value))
        if not digits:
            return None
        number = int(digits)
    return number if 50 <= number <= 2_000_000 else None


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def collect_values(obj, keys):
    values = []
    for node in walk(obj):
        for key, value in node.items():
            if norm(key).replace("_", "").replace("-", "") in keys:
                price = parse_clp(value)
                if price is not None:
                    values.append(price)
    return values


def _schema_price(obj):
    """Collect current and explicitly labeled list prices from Product JSON-LD."""
    products = []
    for node in walk(obj):
        types = node.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if any(norm(t).endswith("product") for t in types):
            products.append(node)
    current, regular, descriptions = [], [], []
    for product in products:
        offers = product.get("offers", {})
        offer_list = offers if isinstance(offers, list) else [offers]
        for offer in offer_list:
            if not isinstance(offer, dict):
                continue
            for key in ("price", "lowPrice"):
                value = parse_clp(offer.get(key))
                if value is not None:
                    current.append(value)
            descriptions.extend(str(x) for x in [offer.get("description"), offer.get("name")] if x)
            specs = offer.get("priceSpecification", [])
            specs = specs if isinstance(specs, list) else [specs]
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                value = parse_clp(spec.get("price") or spec.get("minPrice"))
                if value is None:
                    continue
                price_type = norm(spec.get("priceType") or spec.get("name") or spec.get("@type"))
                if any(word in price_type for word in ("listprice", "regular", "original", "before")):
                    regular.append(value)
                elif any(word in price_type for word in ("sale", "offer", "discount")):
                    current.append(value)
        # Explicit original/list-price fields are stored outside Offers on some retailer schemas.
        for node in walk(product):
            for key, value in node.items():
                key_norm = norm(key).replace("_", "").replace("-", "")
                if key_norm in REGULAR_KEYS:
                    price = parse_clp(value)
                    if price is not None:
                        regular.append(price)
        if not offer_list or not isinstance(offers, (dict, list)):
            for key in ("price", "lowPrice"):
                value = parse_clp(product.get(key))
                if value is not None:
                    current.append(value)
    return products, current, regular, descriptions


def parse_product_page(html: str, product_id: int) -> dict:
    """Parse one rendered official product page; raise instead of guessing."""
    spec = PILOT[product_id]
    soup = BeautifulSoup(html, "html.parser")
    title_parts = []
    if soup.title:
        title_parts.append(soup.title.get_text(" ", strip=True))
    for selector in ("h1", "meta[property='og:title']", "meta[name='twitter:title']", "meta[property='og:description']", "meta[name='description']", "meta[property='product:brand']", "meta[itemprop='brand']"):
        for tag in soup.select(selector):
            val = tag.get("content") if tag.name == "meta" else tag.get_text(" ", strip=True)
            if val:
                title_parts.append(str(val))
    identity = norm(" ".join(title_parts))
    if not all(token in identity for token in spec["name_tokens"]):
        raise ValueError("ficha no coincide con producto/tipo esperado")
    if not re.search(spec["size_regex"], identity, re.I):
        raise ValueError("formato/gramaje no coincide")
    if any(token in identity for token in spec.get("exclude_tokens", [])):
        raise ValueError("tipo de leche no coincide")
    hostname = (urlparse(spec["source_url"]).hostname or "").lower()
    if (spec["supermarket_id"] == 1 and "lider.cl" not in hostname) or (spec["supermarket_id"] == 2 and "jumbo.cl" not in hostname):
        raise ValueError("supermercado de la ficha no coincide")
    # Some retailer headings omit the brand although the product data/description includes it.
    brand_identity = norm(identity + " " + soup.get_text(" ", strip=True))
    if not any(alias in brand_identity for alias in spec["brand_aliases"]):
        raise ValueError("marca no confirmada en la ficha")

    current_candidates, regular_candidates, offer_text = [], [], []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text()
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        products, current, regular, descriptions = _schema_price(data)
        if products:
            # Match a product node to the expected identity, rather than recommended products.
            matching = [p for p in products if all(t in norm(p.get("name", "")) for t in spec["name_tokens"]) and re.search(spec["size_regex"], norm(p.get("name", "")), re.I)]
            if matching:
                for product in matching:
                    _, cur, reg, desc = _schema_price(product)
                    current_candidates.extend((p, 100) for p in cur)
                    regular_candidates.extend((p, 100) for p in reg)
                    offer_text.extend(desc)
        else:
            current_candidates.extend((p, 90) for p in current)
            regular_candidates.extend((p, 90) for p in regular)

    # Standard product metadata is a high-confidence current-price source.
    for tag in soup.select("meta[property='product:price:amount'], meta[itemprop='price'], meta[name='price']"):
        price = parse_clp(tag.get("content"))
        if price:
            current_candidates.append((price, 95))
    # Retailer data attributes commonly expose a page's product price; never scan arbitrary page numbers.
    for tag in soup.select("[data-price], [data-product-price], [data-price-amount]"):
        for key in ("data-price", "data-product-price", "data-price-amount"):
            price = parse_clp(tag.get(key))
            if price:
                current_candidates.append((price, 70))

    # ScraperAPI may return JSON when the retailer is recognized by its product parser.
    if not current_candidates and not soup.find("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        for pattern in (
            r"(?:precio\s+actual|precio\s+web|precio\s+oferta)\s*(?:es|:)?\s*(?:CLP\s*)?\$\s*([\d.,]+)",
            r"(?:precio|price)\s*[:=]\s*[\"']?\$?([\d.,]+)",
        ):
            match = re.search(pattern, soup.get_text(" ", strip=True), re.I)
            if match:
                price = parse_clp(match.group(1))
                if price:
                    current_candidates.append((price, 60))
                    break

    if not current_candidates:
        raise ValueError("precio oficial no parseable; no se escribe")
    best_priority = max(priority for _, priority in current_candidates)
    best_prices = {price for price, priority in current_candidates if priority == best_priority}
    if len(best_prices) != 1:
        raise ValueError("precio ambiguo; no se escribe")
    current_price = best_prices.pop()

    regular_candidates = list(dict.fromkeys(regular_candidates))
    valid_regular = {price for price, priority in regular_candidates if price > current_price}
    regular_price = max(valid_regular) if len(valid_regular) == 1 else current_price
    conditional = []
    for candidate in offer_text:
        for match in CONDITIONAL_RE.finditer(candidate):
            conditional.append(re.sub(r"\s+", " ", match.group(0)).strip())
    visible = soup.get_text("\n", strip=True)
    for line in visible.splitlines():
        if "$" in line and CONDITIONAL_RE.search(line):
            conditional.append(re.sub(r"\s+", " ", line).strip())
    conditional_offer = " | ".join(dict.fromkeys(conditional))[:500] or None
    is_general_sale = regular_price > current_price
    offer_type = "general" if is_general_sale else "none"
    offer_details = (f"Precio regular ${regular_price:,}; oferta general ${current_price:,} CLP" if is_general_sale else "Sin oferta general confirmada en la ficha")
    return {
        "current_price": current_price,
        "regular_price": regular_price,
        "offer_type": offer_type,
        "offer_details": offer_details,
        "conditional_offer": conditional_offer,
        "identity": " ".join(title_parts)[:400],
    }


def unit_price_for(price: int, size: int) -> int:
    return int(round(price * 1000 / size))


def main() -> int:
    scraper_key = os.getenv("SCRAPERAPI_KEY", "").strip()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    if not all((scraper_key, supabase_url, supabase_key)):
        print("ERROR: faltan uno o más secretos requeridos; valores omitidos por seguridad.")
        return 2

    db = create_client(supabase_url, supabase_key)
    rows = db.table("products").select("id,supermarket_id,brand,product_name,price,unit_price,source_url,sku").in_("id", list(PILOT)).execute().data
    indexed = {int(row["id"]): row for row in rows}
    if set(indexed) != set(PILOT):
        print("ERROR: no se recibieron las 23 filas verificadas; no se insertó ninguna fila.")
        return 3

    session = requests.Session()
    failures = 0
    for product_id, spec in PILOT.items():
        row = indexed[product_id]
        if int(row.get("supermarket_id") or 0) != spec["supermarket_id"] or row.get("source_url") != spec["source_url"]:
            print(f"SKIP id={product_id}: supermercado o ficha cambió; no se actualiza.")
            failures += 1
            continue
        if norm(row.get("brand")) != norm(spec["brand"]):
            print(f"SKIP id={product_id}: marca en base no coincide; no se actualiza.")
            failures += 1
            continue
        try:
            response = session.get(
                "https://api.scraperapi.com/",
                params={"api_key": scraper_key, "url": spec["source_url"], "render": "true", "country_code": "cl"},
                timeout=100,
            )
        except requests.RequestException:
            print(f"SKIP id={product_id}: error de red al consultar supermercado; no se actualiza.")
            failures += 1
            continue
        if response.status_code != 200:
            first_status = response.status_code
            # Retry once without headless rendering; some official product pages
            # return provider-side 5xx only on rendered requests.
            try:
                retry_response = session.get(
                    "https://api.scraperapi.com/",
                    params={"api_key": scraper_key, "url": spec["source_url"], "country_code": "cl"},
                    timeout=100,
                )
            except requests.RequestException:
                retry_response = None
            if retry_response is None or retry_response.status_code != 200:
                final_status = retry_response.status_code if retry_response is not None else "network error"
                print(f"SKIP id={product_id}: ScraperAPI render HTTP {first_status}; no-render retry {final_status}; no se actualiza.")
                failures += 1
                continue
            response = retry_response
            print(f"RETRY id={product_id}: respuesta sin render; validar ficha y precio antes de guardar.")
        try:
            parsed = parse_product_page(response.text, product_id)
        except ValueError as exc:
            print(f"SKIP id={product_id}: {exc}.")
            failures += 1
            continue
        checked_at = datetime.now(timezone.utc).isoformat()
        update = {
            "price": parsed["current_price"],
            "unit_price": unit_price_for(parsed["current_price"], spec["size_ml"]),
            "regular_price": parsed["regular_price"],
            "offer_type": parsed["offer_type"],
            "offer_details": parsed["offer_details"],
            "conditional_offer": parsed["conditional_offer"],
            "price_checked_at": checked_at,
            "updated_at": checked_at,
        }
        try:
            saved = db.table("products").update(update).eq("id", product_id).eq("supermarket_id", spec["supermarket_id"]).select("id,price,regular_price,offer_type,price_checked_at").execute().data
        except Exception:
            # Do not include exception text: request/driver errors can contain URLs or headers.
            print(f"ERROR id={product_id}: escritura a Supabase falló; se preserva el precio anterior.")
            failures += 1
            continue
        if len(saved) != 1 or int(saved[0].get("price") or 0) != parsed["current_price"]:
            print(f"ERROR id={product_id}: no se confirmó la fila guardada.")
            failures += 1
            continue
        print(f"OK id={product_id} precio=${parsed['current_price']:,} oferta={parsed['offer_type']} consultado={checked_at}")
    print(f"Resultado piloto: {len(PILOT) - failures}/{len(PILOT)} filas actualizadas; catálogo sin inserciones ni borrados.")
    return 0 if failures == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
