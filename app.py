import streamlit as st
import requests

st.set_page_config(page_title="Optimizador de Despensa", page_icon="🛒", layout="wide")

st.title("🛒 Optimizador Inteligente de Compras")
st.caption("Ahorra en tu despensa básica sustituyendo marcas automáticamente dentro de tu supermercado habitual.")

# Barra lateral para configuración
st.sidebar.header("Supermercado")
super_options = {"Líder": 1, "Jumbo": 2}
selected_super = st.sidebar.radio("Selecciona tu cadena:", list(super_options.keys()))

st.subheader("1. Define tu lista de compras semanal")

col1, col2 = st.columns(2)
with col1:
    qty_arroz = st.number_input("Bolsas de Arroz 1kg", min_value=0, max_value=20, value=2)
    qty_leche = st.number_input("Litros de Leche Entera", min_value=0, max_value=20, value=4)
with col2:
    qty_aceite = st.number_input("Botellas de Aceite 900ml", min_value=0, max_value=20, value=1)
    qty_fideos = st.number_input("Paquetes de Fideos Spaghetti 400g", min_value=0, max_value=20, value=3)

st.write("---")

if st.button("🚀 Optimizar mi Canasta", type="primary", use_container_width=True):
    items = []
    if qty_arroz > 0: items.append({"generic_item_id": 1, "quantity": qty_arroz})
    if qty_leche > 0: items.append({"generic_item_id": 2, "quantity": qty_leche})
    if qty_aceite > 0: items.append({"generic_item_id": 3, "quantity": qty_aceite})
    if qty_fideos > 0: items.append({"generic_item_id": 4, "quantity": qty_fideos})

    if not items:
        st.warning("Debes seleccionar al menos un producto con cantidad mayor a 0.")
    else:
        payload = {
            "supermarket_id": super_options[selected_super],
            "items": items
        }
        try:
            res = requests.post("http://127.0.0.1:8000/optimize", json=payload)
            if res.status_code == 200:
                data = res.json()
                
                st.success(f"🎉 **¡Ahorro total estimado: ${data['savings_amount']:,} CLP ({data['savings_percentage']}%)!**")
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Marcas Tradicionales", f"${data['total_baseline']:,} CLP")
                m2.metric("Total Canasta Optimizada", f"${data['total_optimal']:,} CLP")
                m3.metric("Ahorro Neto", f"${data['savings_amount']:,} CLP", delta=f"{data['savings_percentage']}%")

                st.write("### Desglose comparativo")
                c_opt, c_base = st.columns(2)
                with c_opt:
                    st.info("💡 **Canasta Sugerida (Marcas Económicas / Propias)**")
                    st.dataframe(data["optimal_cart"], use_container_width=True)
                with c_base:
                    st.error("🛒 **Canasta Habitual (Marcas Líderes Tradicionales)**")
                    st.dataframe(data["baseline_cart"], use_container_width=True)
            else:
                st.error("Error al procesar la optimización.")
        except requests.exceptions.ConnectionError:
            st.error("No se pudo conectar con el servidor backend. Asegúrate de tener corriendo 'main.py' en otra ventana de terminal.")