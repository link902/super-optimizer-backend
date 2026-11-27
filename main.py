from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from expensive_scenario import FORMATS, TARGET_AMOUNTS

SUPABASE_URL = "https://djxjwxidzjtpgqdcnnlz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRqeGp3eGlkemp0cGdxZGNubmx6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5NTkzNTMsImV4cCI6MjEwNjUzNTM1M30.YZvLforZ2ccR22-0MRc8Z82GL5Q-DDhDjP6HWc0CB_A"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Grocery Optimizer API")

# Allowlist: manually verified product rows only. Records outside this list remain
# in Supabase but are hidden from the selector and excluded from comparisons.
VERIFIED_PILOT = {
    331: (1, 65, "Ideal", "Leche Evaporada Lata 390 g", "https://www.lider.cl/ip/Leche-Evaporada-Lata-390-g/00844529102808"),
    332: (1, 78, "Quillayes", "Yoghurt Griego Sabor Natural no endulzado Pote 400 g", "https://super.lider.cl/ip/yoghurt/yoghurt-griego-sabor-natural-no-endulzado-pote/00780293000473"),
    333: (1, 79, "Colun", "Yoghurt Colun Origen Natural 900 g", "https://www.lider.cl/ip/Yoghurt-Colun-Origen-Natural-900-g/00780292001105"),
    334: (1, 79, "Colun", "Yoghurt Origen Sabor Natural Pote 120 g", "https://www.lider.cl/ip/Yoghurt-Origen-Sabor-Natural-Pote-120-g/00780292001058"),
    3: (1, 2, "Líder", "Leche Natural Entera caja. 1 L", "https://super.lider.cl/ip/leche/leche-natural-entera-caja/00040000720074"),
    247: (1, 71, "Colun", "Crema de leche natural para batir 200ml Colun", "https://super.lider.cl/ip/cremas/crema-de-leche-natural-para-batir-caja/00780292077728"),
    322: (1, 76, "Líder", "Leche Semidescremada. 1 L", "https://super.lider.cl/ip/leche/leche-semidescremada/00780870950045"),
    323: (1, 77, "Líder", "Leche Blanca Descremada Caja 1 L", "https://super.lider.cl/ip/leche/leche-blanca-descremada-caja/00780870950044"),
    324: (1, 2, "Ecoterra", "Leche de Vacas Libres a Pastoreo Entera 1 L", "https://super.lider.cl/ip/leche/leche-de-vacas-libres-a-pastoreo-entera/00780464445049"),
    325: (1, 77, "Ecoterra", "Leche Descremada de Vacas Libre Pastoreo 1 L", "https://super.lider.cl/ip/leche/leche-descremada-de-vacas-libre-pastoreo/00780464445052"),
    326: (1, 81, "Líder", "Fideo Pasta Tallarines N°77 Bolsa 400 g", "https://super.lider.cl/ip/pastas-y-salsas/fideo-pasta-tallarines-n-77-bolsa/00040000726875"),
    327: (1, 4, "Selección", "Fideo Pasta Spaghetti Bolsa 400 g", "https://www.lider.cl/ip/Fideo-Pasta-Spaghetti-Bolsa-400-g/00780460822181"),
    328: (1, 74, "Robinson Crusoe", "Atún Agua Drenado 91 g - Neto 140 g", "https://super.lider.cl/ip/conservas/atun-agua/00780462147225"),
    329: (1, 2, "Loncoleche", "Leche Natural Entera Lonco Leche 1 L", "https://www.lider.cl/ip/Leche-Natural-Entera-Lonco-Leche-1-L/00780291000725"),
    330: (1, 76, "Loncoleche", "Leche Natural Semidescremada Lonco Leche 1 L", "https://www.lider.cl/ip/Leche-Natural-Semidescremada-Lonco-Leche-1-L/00780291000726"),
    240: (2, 2, "Colun", "Leche Colun Entera 1 L", "https://www.jumbo.cl/leche-entera-colun-caja-1-l-natural/p"),
    246: (1, 71, "Nestlé", "Crema de leche para batir y cocinar 200ml Nestlé", "https://www.lider.cl/ip/cremas/crema-de-leche-para-batir-y-cocinar-caja/00780295002232"),
    250: (2, 71, "Colun", "Crema de leche Colun caja 200ml", "https://www.jumbo.cl/crema-de-leche-colun-caja-200-ml/p"),
    251: (1, 65, "Líder", "Leche evaporada en tarro 410g Líder", "https://super.lider.cl/ip/reposteria/leche-evaporada-tarro/00040000766328"),
    252: (2, 60, "Ideal", "Leche evaporada 390g Ideal", "https://www.jumbo.cl/leche-evaporada-ideal-390g-1976555/p"),
    281: (2, 28, "Soprole", "Queso Crema Soprole 200 g", "https://www.jumbo.cl/queso-crema-dos-alamos-soprole-200-g/p"),
    282: (2, 28, "Colun", "Queso Crema Colun 200 g", "https://www.jumbo.cl/queso-crema-colun-200-g/p"),
    283: (1, 74, "Líder", "Atún Lomitos en Agua. Drenado 91 g - Neto 140 g", "https://super.lider.cl/ip/conservas/atun-lomitos-en-agua/00040000114316"),
    284: (2, 74, "Cuisine & Co", "Atún Lomitos en Agua 91 g drenado, 140 g neto", "https://www.jumbo.cl/atun-cuisine-and-co-lomitos-en-agua-91-g-drenado-140-g-neto-2017687/p"),
    285: (1, 75, "San José", "Filete De Jurel Al Natural 125 g", "https://super.lider.cl/ip/pescados-y-mariscos/filete-de-jurel-al-natural/00780123500563"),
    286: (2, 75, "San José", "Filete Jurel San Jose Natural 80 g drenado", "https://www.jumbo.cl/filet-jurel-natur-2085295/p"),
    4: (1, 2, "Colun", "Leche Entera UHT 1L Colun", "https://super.lider.cl/ip/leche/00780292077754"),
    11: (2, 2, "Cuisine & Co", "Leche Entera 1L Cuisine & Co", "https://www.jumbo.cl/leche-entera-1-l-cuisine-and-co-1858321/p"),
    287: (1, 2, "Surlat", "Leche Entera Surlat 1 L", "https://super.lider.cl/ip/leche/leche-entera/00780461747028"),
    288: (2, 77, "Colun", "Leche Colun Descremada Natural 1 L", "https://www.jumbo.cl/leche-descremada-colun-1-l-2/p"),
    289: (1, 76, "Colun", "Leche Semidescremada Natural Caja 1 L Colun", "https://super.lider.cl/ip/leche/leche-semidescremada-natural-caja/00780292000009"),
    290: (1, 77, "Surlat", "Leche Descremada Surlat 1 L", "https://super.lider.cl/ip/leche/leche-descremada/00780461747030"),
    291: (2, 77, "Surlat", "Leche Descremada Surlat 1 L", "https://www.jumbo.cl/leche-descremada-surlat-b-a-1l-1991552/p"),
    292: (2, 2, "Surlat", "Leche Entera Surlat 1 L", "https://www.jumbo.cl/leche-entera-surlat-b-a-1l-1991554/p"),
    293: (1, 77, "Colun", "Leche Descremada Natural Caja 1 L Colun", "https://super.lider.cl/ip/leche/leche-descremada-natural-caja-1-l/00780292000008"),
    294: (2, 76, "Surlat", "Leche Semidescremada Surlat 1 L", "https://www.jumbo.cl/leche-semidesc-surlat-b-a-1l-1991553/p"),
    295: (2, 76, "Colun", "Leche Colun Semidescremada 1 L", "https://www.jumbo.cl/leche-colun-semi-descremada-1-litro/p"),
    296: (1, 76, "Surlat", "Leche Semidescremada Surlat 1 L", "https://super.lider.cl/ip/leche/leche-semidescremada/00780461747029"),
    297: (1, 78, "Oikos", "Yoghurt Griego Natural sin Azúcar Pote 150 g", "https://super.lider.cl/ip/yoghurt/yoghurt-griego-natural-sin-azucar-pote/00780295500779"),
    298: (2, 78, "Oikos", "Yogurt Griego Natural Sin Endulzar Oikos Danone 150 g", "https://www.jumbo.cl/yoghurt-natural-danone-150-g/p"),
    299: (1, 79, "Colun", "Yoghurt Origen Natural 150 g", "https://super.lider.cl/ip/yoghurt/yoghurt-origen-natural/00780292001206"),
    300: (2, 79, "Colun", "Yogurt Natural Colun Origen 150 g", "https://www.jumbo.cl/yogurt-natur-150gr-2065862/p"),
    301: (1, 79, "Soprole", "Yoghurt Natural Aflanado 155 g", "https://www.lider.cl/ip/Yoghurt-Natural-Aflanado-155-g/00780290013011"),
    302: (2, 79, "Soprole", "Yogurt natural aflanado Soprole 155 g", "https://www.jumbo.cl/yoghurt-batido-soprole-155-g-natural/p?idsku=7164"),
    8: (1, 4, "Carozzi", "Spaghetti N°5 400g Carozzi", "https://www.lider.cl/ip/Fideo-Pasta-Spaghetti-N-5-Bolsa-400-g/00780257500443"),
    16: (2, 4, "Carozzi", "Spaghetti N°5 400g Carozzi", "https://www.jumbo.cl/spaghetti-n-5-carozzi-bolsa-400-g-2/p"),
    303: (2, 4, "Lucchetti", "Spaghetti N°5 Lucchetti 400 g", "https://www.jumbo.cl/spaghetti-n-5-lucchetti-bolsa-400-g/p"),
    304: (1, 4, "Lucchetti", "Fideo Pasta Spaghetti N°5 Bolsa 400 g", "https://super.lider.cl/ip/pastas-y-salsas/fideo-pasta-spaghetti-n-5-bolsa/00780250000005"),
    305: (2, 81, "Carozzi", "Pasta Tallarín N°87 Carozzi 400 g", "https://www.jumbo.cl/tallarines-n-87-carozzi-bolsa-400-g-2/p"),
    306: (2, 81, "Lucchetti", "Tallarín N°77 Lucchetti 400 g", "https://www.jumbo.cl/tallarines-n-77-lucchetti-bolsa-400-g/p"),
    307: (1, 81, "Carozzi", "Fideo Pasta Tallarines N°87 Bolsa 400 g", "https://www.lider.cl/ip/Fideo-Pasta-Tallarines-N-87-Bolsa-400-g/00780257500463"),
    308: (1, 81, "Lucchetti", "Fideo Pasta Tallarines N°77 Bolsa 400 g", "https://super.lider.cl/ip/pastas-y-salsas/fideo-pasta-tallarines-n-77-bolsa/00780250000003"),
    309: (2, 82, "Cuisine & Co", "Penne Cuisine & Co 100% Trigo Duro 400 g", "https://www.jumbo.cl/penne-100-trigo-duro-c-and-co-400-gr-1922155/p"),
    2: (1, 1, "Tucapel", "Arroz Grano Largo Grado 1 1kg Tucapel", "https://super.lider.cl/ip/arroz-y-legumbres/arroz-grado-1-grano-largo-bolsa/00780142025014"),
    241: (1, 1, "Banquete", "Arroz Grado 1 Grano Largo Bolsa. 1 kg", "https://www.lider.cl/ip/arroz-y-legumbres/arroz-grado-1-grano-largo-bolsa/00780311010221"),
    310: (1, 1, "Miraflores", "Arroz Grado 1 Grano Largo Bolsa. 1 Kg", "https://super.lider.cl/ip/arroz-y-legumbres/arroz-grado-1-grano-largo-bolsa/00780261500655"),
    226: (2, 1, "Banquete", "Arroz Grado 1 Banquete Premium Grano Largo y Ancho 1 kg", "https://www.jumbo.cl/arroz-grado-1-banquete-1-kg-premium-grano-largo-y-ancho/p"),
    231: (2, 1, "Cuisine & Co", "Arroz Grado 1 Cuisine & Co Grano Largo y Ancho 1 kg", "https://www.jumbo.cl/arroz-cuisine-and-co-g1-grano-largo-ancho1kg-1888808/p"),
    233: (2, 1, "Miraflores", "Arroz Grado 1 Miraflores Grano Largo y Ancho 1 kg", "https://www.jumbo.cl/arroz-grado-1-miraflores-1-kg-grano-largo-y-ancho/p"),
    235: (2, 1, "Tucapel", "Arroz Grado 1 Tucapel Gran Selección Grano Largo y Ancho 1 kg", "https://www.jumbo.cl/arroz-grado-1-tucapel-gran-seleccion-grano-largo-y-ancho-1-kg/p"),
    311: (1, 83, "Líder", "Cous cous Bolsa 500 g", "https://www.lider.cl/ip/Cous-cous-Bolsa-500-g/00780874360586"),
    312: (1, 83, "Carozzi", "Cous cous Doypack 250 g", "https://www.lider.cl/ip/Cous-cous-Doypack-250-g/00780257503118"),
}

def is_verified_pilot(row):
    try:
        product_id = int(row.get("id") or 0)
        price = int(row.get("price") or 0)
    except (TypeError, ValueError):
        return False
    expected = VERIFIED_PILOT.get(product_id)
    if not expected:
        return False
    supermarket_id, generic_item_id, brand, product_name, source_url = expected
    return (
        row.get("supermarket_id") == supermarket_id
        and row.get("generic_item_id") == generic_item_id
        and row.get("brand") == brand
        and row.get("product_name") == product_name
        and row.get("source_url") == source_url
        and bool(row.get("price_checked_at"))
        and price > 0
    )


# Habilitar CORS para permitir conexiones desde cualquier frontend en la web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ItemInput(BaseModel):
    generic_item_id: int
    quantity: int

class OptimizeRequest(BaseModel):
    supermarket_id: int
    items: List[ItemInput]

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Grocery Optimizer API funcionando en la nube"}

@app.get("/items")
def get_items(supermarket_id: Optional[int] = None):
    if supermarket_id not in (None, 1, 2):
        raise HTTPException(status_code=400, detail="Supermercado no válido.")

    query = (
        supabase.table("products")
        .select("id,supermarket_id,generic_item_id,brand,product_name,price,price_checked_at,source_url,in_stock")
        .in_("id", list(VERIFIED_PILOT))
    )
    if supermarket_id is not None:
        query = query.eq("supermarket_id", supermarket_id)
    verified_rows = [row for row in query.execute().data if is_verified_pilot(row) and row.get("in_stock", True)]
    item_ids = sorted({row["generic_item_id"] for row in verified_rows})
    if not item_ids:
        return []
    items = supabase.table("generic_items").select("*").in_("id", item_ids).order("id").execute()
    return items.data

@app.get("/pilot-prices")
def get_pilot_prices():
    # Solo lectura: expone los registros con identidad, ficha y precio confirmados.
    response = (
        supabase.table("products")
        .select("id,supermarket_id,generic_item_id,brand,product_name,price,regular_price,offer_type,offer_details,conditional_offer,price_checked_at,source_url,in_stock")
        .in_("id", list(VERIFIED_PILOT))
        .order("id")
        .execute()
    )
    return [row for row in response.data if is_verified_pilot(row)]

@app.post("/optimize")
def optimize_cart(request: OptimizeRequest):
    if request.supermarket_id not in (1, 2):
        raise HTTPException(status_code=400, detail="Supermercado no válido.")
    item_ids = [item.generic_item_id for item in request.items]
    quantities = {item.generic_item_id: item.quantity for item in request.items}
    if not item_ids:
        raise HTTPException(status_code=400, detail="Selecciona al menos un producto verificado.")

    # Consultar solo filas incluidas en el allowlist y validadas por identidad.
    response = (
        supabase.table("products")
        .select("*")
        .eq("supermarket_id", request.supermarket_id)
        .in_("generic_item_id", item_ids)
        .in_("id", list(VERIFIED_PILOT))
        .execute()
    )
    rows = [
        row for row in response.data
        if is_verified_pilot(row) and row.get("in_stock", True) and row.get("price") is not None
    ]
    available_ids = {row["generic_item_id"] for row in rows}
    if not rows or any(gid not in available_ids for gid in item_ids):
        raise HTTPException(status_code=404, detail="No hay ficha oficial y precio confirmado para todos los productos seleccionados.")

    optimal_cart = []
    baseline_cart = []
    total_optimal = 0
    total_baseline = 0

    for gid in item_ids:
        matches = [p for p in rows if p["generic_item_id"] == gid and p.get("in_stock", True)]
        # En Líder, una unidad es la cantidad nominal del selector, no un
        # envase arbitrario. La ficha de 155 g permanece visible, pero no es
        # equivalente a un pote de 150 g. Para cuscús, 2 x 250 g sí suman 500 g.
        target = TARGET_AMOUNTS.get(gid) if request.supermarket_id == 1 else None
        if request.supermarket_id == 1:
            matches = [p for p in matches if target and p['id'] in FORMATS
                       and FORMATS[p['id']][0] == gid and target % FORMATS[p['id']][1] == 0]
        if not matches:
            if request.supermarket_id == 1:
                raise HTTPException(status_code=404, detail="No hay un formato comparable verificado para el grupo solicitado.")
            continue

        qty = quantities[gid]

        def packs_per_unit(product):
            return target // FORMATS[product['id']][1] if target else (2 if product['id'] == 312 else 1)

        cheapest = min(matches, key=lambda x: x["price"] * packs_per_unit(x))
        subtotal_opt = cheapest["price"] * qty * packs_per_unit(cheapest)
        total_optimal += subtotal_opt
        optimal_cart.append({
            "Producto": cheapest["product_name"],
            "Marca": cheapest["brand"],
            "Precio Unitario": f"${cheapest['price']:,} CLP",
            "Cantidad": qty * packs_per_unit(cheapest),
            "Subtotal": f"${subtotal_opt:,} CLP"
        })

        # Producto premium o tradicional (canasta de referencia)
        premium_options = [p for p in matches if p.get("is_premium_tier")]
        baseline = premium_options[0] if premium_options else max(matches, key=lambda x: x["price"] * packs_per_unit(x))
        subtotal_base = baseline["price"] * qty * packs_per_unit(baseline)
        total_baseline += subtotal_base
        baseline_cart.append({
            "Producto": baseline["product_name"],
            "Marca": baseline["brand"],
            "Precio Unitario": f"${baseline['price']:,} CLP",
            "Cantidad": qty * packs_per_unit(baseline),
            "Subtotal": f"${subtotal_base:,} CLP"
        })

    savings_amount = total_baseline - total_optimal
    savings_percent = round((savings_amount / total_baseline) * 100, 1) if total_baseline > 0 else 0

    return {
        "supermarket_id": request.supermarket_id,
        "total_optimal": total_optimal,
        "total_baseline": total_baseline,
        "savings_amount": savings_amount,
        "savings_percentage": savings_percent,
        "optimal_cart": optimal_cart,
        "baseline_cart": baseline_cart
    }
