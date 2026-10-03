import streamlit as st
import requests

st.set_page_config(page_title="Optimizador de Despensa", page_icon="🛒", layout="wide")

API_URL = "https://super-optimizer-backend.onrender.com"

st.title("🛒 Optimizador Inteligente de Compras")
st.caption("Arma tu lista de compras personalizada y descubre cuánto ahorras cambiando a marcas equivalentes.")

# 1. Selector de supermercado
st.sidebar.header("Supermercado de Destino")
super_options = {
    "Líder (Walmart)": 1,
    "Jumbo (Cencosud)": 2
}
selected_super_name = st.sidebar.selectbox("Selecciona dónde vas a comprar:", list(super_options.keys()))
super_id = super_options[selected_super_name]

# 2. Obtener catálogo dinámico desde el backend
@st.cache_data(ttl=30)
def get_catalog():
    try:
        r = requests.get(f"{API_URL}/items", timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

catalog = get_catalog()

if not catalog:
    st.warning("Cargando catálogo desde el servidor... Si tarda unos segundos, es porque el backend gratuito de Render está despertando.")
else:
    # Agrupar ítems por categoría
    categories = sorted(list(set(item["category"] for item in catalog)))
    
    st.subheader("1. Selecciona los productos de tu despensa")
    
    # Selector filtrado o global
    options_map = {f"{item['name']} — [{item['category']}]": item["id"] for item in catalog}
    
    selected_items = st.multiselect(
        "Busca o elige los productos que necesitas comprar:",
        options=list(options_map.keys()),
        default=[list(options_map.keys())[0], list(options_map.keys())[1]] if len(options_map) >= 2 else []
    )

    # 3. Asignar cantidades por producto
    order_items = []
    if selected_items:
        st.write("#### 2. Define las unidades para cada producto:")
        cols = st.columns(min(len(selected_items), 4))
        
        for idx, item_label in enumerate(selected_items):
            col = cols[idx % len(cols)]
            item_id = options_map[item_label]
            short_name = item_label.split(" — ")[0]
            with col:
                qty = st.number_input(
                    f"{short_name}",
                    min_value=1,
                    max_value=30,
                    value=1,
                    key=f"item_{item_id}"
                )
                order_items.append({"generic_item_id": item_id, "quantity": qty})

        st.write("---")

        # 4. Botón de optimización
        if st.button("🚀 Comparar y Optimizar Canasta", type="primary", use_container_width=True):
            payload = {
                "supermarket_id": super_id,
                "items": order_items
            }
            with st.spinner("Analizando sustituciones óptimas y calculando ahorro..."):
                try:
                    res = requests.post(f"{API_URL}/optimize", json=payload, timeout=20)
                    if res.status_code == 200:
                        data = res.json()
                        
                        st.balloons()
                        st.success(f"🎉 **¡Ahorro total: ${data['savings_amount']:,} CLP ({data['savings_percentage']}%)!**")
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Costo Marcas Tradicionales", f"${data['total_baseline']:,} CLP")
                        m2.metric("Costo Marcas Sugeridas", f"${data['total_optimal']:,} CLP")
                        m3.metric("Bolsillo Protegido", f"${data['savings_amount']:,} CLP", delta=f"{data['savings_percentage']}%")

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