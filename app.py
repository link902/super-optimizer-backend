import streamlit as st
import requests

st.set_page_config(page_title="Optimizador de Despensa", page_icon="🛒", layout="wide")

API_URL = "https://super-optimizer-backend.onrender.com"

st.title("🛒 Optimizador Inteligente de Compras")
st.caption("Arma tu lista de compras personalizada y descubre cuánto ahorras cambiando a marcas equivalentes.")

@st.cache_data(ttl=60)
def get_pilot_prices():
    try:
        response = requests.get(f"{API_URL}/pilot-prices", timeout=18)
        if response.status_code == 200:
            return response.json(), None
        return [], f"El backend respondió HTTP {response.status_code}."
    except requests.exceptions.RequestException:
        return [], "El backend no respondió todavía; los precios del catálogo no se modificaron."

def clp(value):
    if value is None:
        return "—"
    return "$" + f"{int(value):,} CLP".replace(",", ".")

st.subheader("Precios y ofertas automáticas · piloto de 7 lácteos y 4 conservas")
pilot_prices, pilot_error = get_pilot_prices()
if pilot_error:
    st.info(pilot_error)
elif not pilot_prices:
    st.info("El backend aún no devolvió los once productos del piloto.")
else:
    display_rows = []
    for item in pilot_prices:
        store = "Líder" if item.get("supermarket_id") == 1 else "Jumbo"
        general = "Oferta general" if item.get("offer_type") == "general" else "Sin oferta general confirmada"
        display_rows.append({
            "Supermercado": store,
            "Producto": f"{item.get('brand') or ''} · {item.get('product_name') or ''}",
            "Precio vigente": clp(item.get("price")),
            "Precio normal": clp(item.get("regular_price")),
            "Oferta general": general,
            "Beneficio condicionado": item.get("conditional_offer") or "—",
            "Consultado (UTC)": item.get("price_checked_at") or "Pendiente de actualización",
        })
    st.dataframe(display_rows, use_container_width=True, hide_index=True)
    with st.expander("Fichas oficiales de los productos piloto"):
        for item in pilot_prices:
            store = "Líder" if item.get("supermarket_id") == 1 else "Jumbo"
            st.markdown(f"- {store}: [{item.get('product_name')}]({item.get('source_url')})")

# Selector de supermercado
st.sidebar.header("Supermercado de Destino")
super_options = {"Líder (Walmart)": 1, "Jumbo (Cencosud)": 2}
selected_super_name = st.sidebar.selectbox("Selecciona dónde vas a comprar:", list(super_options.keys()))
super_id = super_options[selected_super_name]

@st.cache_data(ttl=30)
def get_catalog(supermarket_id):
    try:
        r = requests.get(
            f"{API_URL}/items",
            params={"supermarket_id": supermarket_id},
            timeout=12,
        )
        if r.status_code == 200:
            return r.json()
    except requests.exceptions.RequestException:
        pass
    return []

catalog = get_catalog(super_id)
if not catalog:
    st.warning("No hay categorías piloto verificadas disponibles para este supermercado. El catálogo general permanece oculto.")
else:
    st.subheader("1. Selecciona productos con ficha oficial y precio confirmado")
    st.caption("El selector y la comparación incluyen solo productos verificados para el supermercado elegido.")
    options_map = {f"{item['name']} — [{item['category']}]": item["id"] for item in catalog}
    selected_items = st.multiselect(
        "Busca o elige los productos que necesitas comprar:",
        options=list(options_map.keys()),
        default=list(options_map.keys())[:2],
        key=f"verified_items_{super_id}",
    )
    order_items = []
    if selected_items:
        st.write("#### 2. Define las unidades para cada producto:")
        cols = st.columns(min(len(selected_items), 4))
        for idx, item_label in enumerate(selected_items):
            col = cols[idx % len(cols)]
            item_id = options_map[item_label]
            short_name = item_label.split(" — ")[0]
            with col:
                qty = st.number_input(f"{short_name}", min_value=1, max_value=30, value=1, key=f"item_{item_id}")
                order_items.append({"generic_item_id": item_id, "quantity": qty})
        st.write("---")
        if st.button("🚀 Comparar y Optimizar Canasta", type="primary", use_container_width=True):
            payload = {"supermarket_id": super_id, "items": order_items}
            with st.spinner("Analizando sustituciones óptimas y calculando ahorro..."):
                try:
                    res = requests.post(f"{API_URL}/optimize", json=payload, timeout=20)
                    if res.status_code == 200:
                        data = res.json()
                        st.balloons()
                        st.success(f"🎉 **¡Ahorro total: " + "$" + f"{data['savings_amount']:,} CLP ({data['savings_percentage']}%)!**")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Costo Marcas Tradicionales", "$" + f"{data['total_baseline']:,} CLP")
                        m2.metric("Costo Marcas Sugeridas", "$" + f"{data['total_optimal']:,} CLP")
                        m3.metric("Bolsillo Protegido", "$" + f"{data['savings_amount']:,} CLP", delta=f"{data['savings_percentage']}%")
                        st.write("### Detalle de Góndola")
                        col_opt, col_base = st.columns(2)
                        with col_opt:
                            st.info("💡 **Canasta Optimizada (Marcas Propias / Alternativas)**")
                            st.dataframe(data["optimal_cart"], use_container_width=True)
                        with col_base:
                            st.error("🛒 **Canasta Tradicional (Marcas Líderes)**")
                            st.dataframe(data["baseline_cart"], use_container_width=True)
                    else:
                        st.error("No se pudo calcular la canasta. Verifica que los productos existan en el supermercado elegido.")
                except requests.exceptions.RequestException:
                    st.error("El servidor backend está tardando en responder. Espera unos segundos y vuelve a presionar el botón.")
