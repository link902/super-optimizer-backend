from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from supabase import create_client, Client

SUPABASE_URL = "https://djxjwxidzjtpgqdcnnlz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRqeGp3eGlkemp0cGdxZGNubmx6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5NTkzNTMsImV4cCI6MjEwNjUzNTM1M30.YZvLforZ2ccR22-0MRc8Z82GL5Q-DDhDjP6HWc0CB_A"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Grocery Optimizer API")

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
def get_items():
    # Obtener el catálogo de categorías genéricas para el buscador
    response = supabase.table("generic_items").select("*").execute()
    return response.data

@app.post("/optimize")
def optimize_cart(request: OptimizeRequest):
    item_ids = [item.generic_item_id for item in request.items]
    quantities = {item.generic_item_id: item.quantity for item in request.items}

    # Consultar productos directamente en la base de datos de Supabase
    response = supabase.table("products")\
        .select("*")\
        .eq("supermarket_id", request.supermarket_id)\
        .in_("generic_item_id", item_ids)\
        .execute()
    
    rows = response.data
    if not rows:
        raise HTTPException(status_code=404, detail="No se encontraron productos para los parámetros dados.")

    optimal_cart = []
    baseline_cart = []
    total_optimal = 0
    total_baseline = 0

    for gid in item_ids:
        matches = [p for p in rows if p["generic_item_id"] == gid and p.get("in_stock", True)]
        if not matches:
            continue
        
        qty = quantities[gid]
        
        # Producto más barato (canasta óptima)
        cheapest = min(matches, key=lambda x: x["price"])
        subtotal_opt = cheapest["price"] * qty
        total_optimal += subtotal_opt
        optimal_cart.append({
            "Producto": cheapest["product_name"],
            "Marca": cheapest["brand"],
            "Precio Unitario": f"${cheapest['price']:,} CLP",
            "Cantidad": qty,
            "Subtotal": f"${subtotal_opt:,} CLP"
        })

        # Producto premium o tradicional (canasta de referencia)
        premium_options = [p for p in matches if p.get("is_premium_tier")]
        baseline = premium_options[0] if premium_options else max(matches, key=lambda x: x["price"])
        subtotal_base = baseline["price"] * qty
        total_baseline += subtotal_base
        baseline_cart.append({
            "Producto": baseline["product_name"],
            "Marca": baseline["brand"],
            "Precio Unitario": f"${baseline['price']:,} CLP",
            "Cantidad": qty,
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