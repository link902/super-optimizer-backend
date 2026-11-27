import streamlit as st
import requests
from expensive_scenario import compare_group, compare_basket, compare_by_100g

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

st.subheader("Precios y ofertas · productos con ficha y precio verificados")
pilot_prices, pilot_error = get_pilot_prices()
if pilot_error:
    st.info(pilot_error)
elif not pilot_prices:
    st.info("Aún no hay productos con ficha oficial y precio confirmado disponibles.")
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
    options_map = {f"{('Yogurt natural 150 g' if super_id == 1 and item['id'] == 79 else item['name'])} — [{item['category']}]": item["id"] for item in catalog}
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
        scenario = "Solo referencia habitual"
        if super_id == 1:
            scenario = st.radio(
                "Escenario adicional", ["Solo referencia habitual", "Contra la opción más cara"], index=1,
                help="La referencia habitual se conserva. El escenario adicional muestra extremos por grupo, no un ahorro típico.",
            )
        if st.button("🚀 Comparar y Optimizar Canasta", type="primary", use_container_width=True):
            payload = {"supermarket_id": super_id, "items": order_items}
            with st.spinner("Analizando sustituciones óptimas y calculando ahorro..."):
                try:
                    before = None
                    if scenario == "Contra la opción más cara":
                        try:
                            snapshot = requests.get(f"{API_URL}/pilot-prices", timeout=18)
                            snapshot.raise_for_status()
                            before = snapshot.json()
                        except (requests.exceptions.RequestException, ValueError):
                            pass
                    res = requests.post(f"{API_URL}/optimize", json=payload, timeout=20)
                    if res.status_code == 200:
                        data = res.json()
                        after = None
                        if before is not None:
                            try:
                                snapshot = requests.get(f"{API_URL}/pilot-prices", timeout=18)
                                snapshot.raise_for_status()
                                after = snapshot.json()
                            except (requests.exceptions.RequestException, ValueError):
                                pass
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
                        if scenario == "Contra la opción más cara":
                            st.subheader("Contra la opción más cara")
                            st.caption("Diferencia frente a la opción más cara, por grupo y tienda; no representa ahorro típico. Precios generales de la última consulta, no promociones con condiciones. Stock y precios pueden cambiar.")
                            st.caption("Solo fichas verificadas con stock y consulta de hasta 72 horas. La comparación de canasta usa envases enteros que suman exactamente la cantidad nominal del selector. Cuando no existe un par de ese tamaño, se muestran por separado los extremos por 100 g y el costo de envases enteros. Los extremos son los del catálogo verificado, no necesariamente los de todo el supermercado.")
                            st.caption("Las promociones condicionadas no se aplican en la referencia habitual; el cobro real puede ser distinto. En el escenario adicional se excluyen productos cuando la cantidad alcanza una promoción conocida.")
                            if before is None or after is None:
                                st.warning("No se pudo confirmar la estabilidad del catálogo; no se compararán los totales.")
                            else:
                                try:
                                    basket = compare_basket(before, after, super_id, order_items, data)
                                    st.write("#### La misma canasta: dos referencias")
                                    st.dataframe([
                                        {"Escenario": "Referencia habitual", "Total optimizado": clp(basket['optimizado']), "Total referencia": clp(basket['habitual']), "Porcentaje": f"{basket['porcentaje_habitual']}%"},
                                        {"Escenario": "Contra la opción más cara", "Total optimizado": clp(basket['optimizado']), "Total referencia": clp(basket['mas_cara']), "Porcentaje": f"{basket['porcentaje_mas_cara']}%"},
                                    ], use_container_width=True, hide_index=True)
                                    st.write(f"**Diferencia: {basket['diferencia_pp']:+.1f} puntos porcentuales**")
                                    st.caption("El costo optimizado es idéntico. La variación del porcentaje se debe exclusivamente a cambiar la referencia, no a una reducción real adicional del costo.")
                                except (ValueError, KeyError, TypeError) as error:
                                    st.warning(f"No se pueden comparar los totales de la misma canasta: {error}")
                            for selected in order_items:
                                label = next((name for name, gid in options_map.items() if gid == selected['generic_item_id']), str(selected['generic_item_id']))
                                result = compare_group(before, super_id, selected['generic_item_id'], selected['quantity']) if before is not None and after == before else None
                                st.write(f"#### {label}")
                                if not result:
                                    variable = compare_by_100g(before, super_id, selected['generic_item_id'], selected['quantity']) if before is not None and after == before else None
                                    if variable:
                                        st.caption("Formatos distintos: extremos ordenados por precio general por 100 g. El costo mostrado compra envases enteros, no una porción fraccionada. Los pesos entregados difieren: estos subtotales no son ahorro comparable ni se suman a la comparación de canasta.")
                                        table = []
                                        for title, row in [("Optimizada · menor precio por 100 g", variable['barata']), ("Referencia · mayor precio por 100 g", variable['cara'])]:
                                            rate = f"${row['precio_100g']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                                            table.append({"Opción":title, "Producto":row['producto'], "Marca":row['marca'], "Formato":row['formato'], "Precio por 100 g":rate, "Envases enteros":row['envases'], "Contenido total":f"{row['contenido_g']} g", "Precio por envase":clp(row['precio_envase']), "Costo envases":clp(row['subtotal']), "Consultado (UTC)":row['consulta'], "Ficha oficial":row['ficha']})
                                        st.dataframe(table, use_container_width=True, hide_index=True)
                                        for row in (variable['barata'], variable['cara']):
                                            if row['condicional']:
                                                st.caption(f"Promoción condicional no aplicada para {row['marca']}: {row['condicional']}. El costo real puede variar si cumples las condiciones.")
                                    else:
                                        st.info("Sin dos alternativas comparables verificadas y recientes para esta tienda. No se calcula la diferencia.")
                                    continue
                                st.write(f"Cantidad equivalente: **{result['cantidad']} {result['unidad']}**")
                                table = []
                                for title, row in [("Optimizada · más económica verificada", result['barata']), ("Referencia · más cara verificada", result['cara'])]:
                                    table.append({"Opción": title, "Producto": row['producto'], "Marca": row['marca'], "Formato": row['formato'], "Envases": row['envases'], "Precio por envase": clp(row['precio_envase']), "Subtotal": clp(row['subtotal']), "Consultado (UTC)": row['consulta'], "Ficha oficial": row['ficha']})
                                st.dataframe(table, use_container_width=True, hide_index=True)
                                for row in (result['barata'], result['cara']):
                                    if row['condicional']:
                                        st.caption(f"Promoción condicional no aplicada para {row['marca']}: {row['condicional']}. El total real puede variar si cumples sus condiciones.")
                                st.write(f"**Diferencia frente a la opción más cara: {clp(result['diferencia'])} ({result['porcentaje']}%)**")
                    else:
                        st.error("No se pudo calcular la canasta. Verifica que los productos existan en el supermercado elegido.")
                except requests.exceptions.RequestException:
                    st.error("El servidor backend está tardando en responder. Espera unos segundos y vuelve a presionar el botón.")
