import streamlit as st
import requests

st.set_page_config(page_title="Optimizador de Despensa", page_icon="🛒", layout="wide")

API_URL = "https://super-optimizer-backend.onrender.com"

st.title("🛒 Optimizador Inteligente de Compras")
st.caption("Arma tu lista personalizada y descubre el ahorro automático sustituyendo marcas en tu supermercado.")

# 1. Configuración de supermercado
st.sidebar.header("Opciones de Compra")
super_options = {"Líder (Walmart)": 1, "Jumbo (Cencosud)": 2}
selected_super = st.sidebar.selectbox("Selecciona tu supermercado:", list(super_options.keys()))

# 2. Obtener categorías dinámicamente desde el backend
@st.cache_data(ttl=60)
def fetch_catalog():
    try:
        res = requests.get(f"{API_URL}/items", timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    # Respaldo si la conexión tarda
    return [
        {"id": 1, "name": "Arroz Grano Largo 1kg", "category": "Despensa"},
        {"id": 2, "name": "Leche Entera 1L", "category": "Lácteos"},
        {"id": 3, "name": "Aceite Maravilla 900ml", "category": "Despensa"},
        {"id": 4, "name": "Fideos Spaghetti 400g", "category": "Despensa"},
        {"id": 5, "name": "Huevos Blancos Bandeja 30 un", "category": "Huevos y Lácteos"},
        {"id": 6, "name": "Café Soluble 170g", "category": "Despensa"},
        {"id": 7, "name": "Atún Lomitos en Agua 160g", "category": "Conservas"},
        {"id": 8, "name": "Azúcar Blanca 1kg", "category": "Despensa"},
        {"id": 9, "name": "Papel Higiénico 8 rollos Doble Hoja", "category": "Limpieza y Hogar"},
        {"id": 10, "name": "Detergente Líquido 3L", "category": "Limpieza y Hogar"},
    ]

catalog_items = fetch_catalog()
items_dict = {f"{item['name']} ({item.get('category', 'Varios')})": item["id"] for item in catalog_items}

# 3. Selector interactivo de lista de compras
st.subheader("1. Arma tu lista de compras")
selected_names = st.multiselect(
    "Selecciona los productos que necesitas comprar:",
    options=list(items_dict.keys()),
    default=[list(items_dict.keys())[0], list(items_dict.keys())[1], list(items_dict.keys())[4]]
)

order_payload = []
if selected_names:
    st.write("#### Define las cantidades:")
    cols = st.columns(min(len(selected_names), 3))
    
    for idx, name in enumerate(selected_names):
        col = cols[idx % len(cols)]
        item_id = items_dict[name]
        with col:
            qty = st.number_input(f"Cantidad para {name.split(' (')[0]}", min_value=1, max_value=50, value=1, key=f"qty_{item_id}")
            order_payload.append({"generic_item_id": item_id, "quantity": qty})

st.write("---")

# 4. Botón de optimización
if st.button("🚀 Optimizar mi Canasta", type="primary", use_container_width=True):
    if not order_payload:
        st.warning("Debes seleccionar al menos un producto para optimizar tu canasta.")
    else:
        payload = {
            "supermarket_id": super_options[selected_super],
            "items": order_payload
        }
        with st.spinner("Comparando precios y sustituciones óptimas..."):
            try:
                res = requests.post(f"{API_URL}/optimize", json=payload, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    
                    st.success(f"🎉 **¡Ahorro total estimado: ${data['savings_amount']:,} CLP ({data['savings_percentage']}%)!**")
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Canasta Habitual (Marcas Tradicionales)", f"${data['total_baseline']:,} CLP")
                    m2.metric("Total Canasta Inteligente (Marcas Sugeridas)", f"${data['total_optimal']:,} CLP")
                    m3.metric("Ahorro de Bolsillo", f"${data['savings_amount']:,} CLP", delta=f"{data['savings_percentage']}%")

                    st.write("### Desglose y Sugerencias de Góndola")
                    c_opt, c_base = st.columns(2)
                    with c_opt:
                        st.info("💡 **Canasta Sugerida (Marcas Económicas / Propias)**")
                        st.dataframe(data["optimal_cart"], use_container_width=True)
                    with c_base:
                        st.error("🛒 **Canasta Tradicional (Marcas Líderes)**")
                        st.dataframe(data["baseline_cart"], use_container_width=True)
                else:
                    st.error("No se pudo calcular la optimización. Verifica los productos seleccionados.")
            except requests.exceptions.RequestException:
                st.error("El servidor backend está iniciando o no responde. Por favor espera 30 segundos y vuelve a intentar.")