"""Presentación local del resultado de Líder, frente al extremo verificado."""
import requests
import streamlit as st
from basket_example import compare_selected
from expensive_scenario import compare_by_100g


def clp(value):
    return '$' + f'{int(value):,}'.replace(',', '.') + ' CLP'


def show_lider_result(api_url, order, options, excluded_brands=(), enforce_example_cap=False):
    try:
        first = requests.get(f'{api_url}/pilot-prices',timeout=18)
        first.raise_for_status()
        before = first.json()
        second = requests.get(f'{api_url}/pilot-prices',timeout=18)
        second.raise_for_status()
        after = second.json()
        if not isinstance(before,list) or not isinstance(after,list):
            raise ValueError('La respuesta de precios no tiene el formato esperado.')
        comparison = compare_selected(before,after,order,excluded_brands=excluded_brands)
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as error:
        st.warning('No se pudo completar la comparación. Vuelve a intentarlo.')
        return

    if enforce_example_cap and all(item['quantity'] == 1 for item in order) and comparison['total']:
        total = comparison['total']
        exceeds_cap = 10 * total['diferencia'] > 3 * total['referencia']
        exceeds_cap |= any(10 * p['diferencia'] > 3 * p['cara']['subtotal'] for p in comparison['pairs'].values())
        if exceeds_cap:
            st.warning('Los precios cambiaron. Actualiza la página o selecciona otros productos para compararlos.')
            return

    st.subheader('Frente a la opción más cara verificada')
    offers = []
    total = comparison['total']
    if total:
        percent = 100 * total['diferencia'] / total['referencia'] if total['referencia'] else 0
        percent_text = f'{percent:.2f}'.replace('.', ',') + '%'
        st.success(f"Ahorro: {clp(total['diferencia'])} ({percent_text})")
        m1,m2,m3=st.columns(3)
        m1.metric('Total de referencia',clp(total['referencia']))
        m2.metric('Total optimizado',clp(total['optimizado']))
        m3.metric('Diferencia',clp(total['diferencia']),delta=percent_text)
        reference=[]; optimized=[]
        for item in order:
            pair=comparison['pairs'][item['generic_item_id']]
            for table, key in [(optimized,'barata'),(reference,'cara')]:
                row=pair[key]
                table.append({'Producto':row['producto'],'Marca':row['marca'],'Formato':row['formato'],
                    'Envases':row['envases'],'Precio por envase':clp(row['precio_envase']),
                    'Subtotal':clp(row['subtotal'])})
        left,right=st.columns(2)
        with left:
            st.info('Canasta optimizada · menor precio verificado')
            st.dataframe(optimized,use_container_width=True,hide_index=True)
        with right:
            st.info('Referencia · opción más cara verificada')
            st.dataframe(reference,use_container_width=True,hide_index=True)
    else:
        names = [next((n.split(' — ')[0] for n,i in options.items() if i==gid), str(gid))
                 for gid in comparison['missing']]
        products = ', '.join(names)
        st.warning(f'No hay dos alternativas comparables verificadas para {products}; quita estos productos de la selección para comparar el resto.' if len(names) > 1 else f'No hay dos alternativas comparables verificadas para {products}; quita este producto de la selección para comparar el resto.')

    st.write('### Detalle por grupo')
    for item in order:
        gid=item['generic_item_id']; qty=item['quantity']; pair=comparison['pairs'][gid]
        name=next((n for n,i in options.items() if i==gid),str(gid))
        variable = None
        if not pair:
            allowed_rows = [r for r in before if (r.get('brand') or '').strip().casefold() not in {b.casefold() for b in excluded_brands}]
            variable = compare_by_100g(allowed_rows,1,gid,qty)
            if not variable:
                continue
        st.write(f'#### {name}')
        if pair:
            st.caption(f"Cantidad equivalente por opción: {pair['cantidad']} {pair['unidad']}, usando envases enteros.")
            rows=[]
            for title,key in [('Optimizada · menor precio verificado','barata'),('Referencia · opción más cara verificada','cara')]:
                row=pair[key]
                rows.append({'Opción':title,'Producto':row['producto'],'Marca':row['marca'],
                    'Formato':row['formato'],'Envases':row['envases'],
                    'Precio por envase':clp(row['precio_envase']),'Subtotal':clp(row['subtotal']),
                    'Consultado (UTC)':row['consulta'],'Ficha oficial':row['ficha']})
            st.dataframe(rows,use_container_width=True,hide_index=True)
            for key in ('barata','cara'):
                row=pair[key]
                if row['condicional']:
                    offers.append(f"{row['marca']}: {row['condicional']}")
            st.write(f"Diferencia frente a la opción más cara: **{clp(pair['diferencia'])} ({pair['porcentaje']:.1f}%)**")
            continue
        st.caption('Formatos distintos: referencia por 100 g y compras de envases enteros. Los pesos entregados difieren; estos costos no se suman a una canasta equivalente.')
        rows=[]
        for title,key in [('Optimizada · menor precio por 100 g','barata'),('Referencia · mayor precio por 100 g','cara')]:
            row=variable[key]
            rate=f"${row['precio_100g']:,.2f}".replace(',','X').replace('.',',').replace('X','.')
            rows.append({'Opción':title,'Producto':row['producto'],'Marca':row['marca'],'Formato':row['formato'],
                'Precio por 100 g':rate,'Envases enteros':row['envases'],'Contenido total':f"{row['contenido_g']} g",
                'Precio por envase':clp(row['precio_envase']),'Costo envases':clp(row['subtotal']),
                'Consultado (UTC)':row['consulta'],'Ficha oficial':row['ficha']})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        for key in ('barata','cara'):
            row=variable[key]
            if row['condicional']:
                offers.append(f"{row['marca']}: {row['condicional']}")

    with st.expander('Información sobre la comparación'):
        st.write('Los precios y la disponibilidad pueden cambiar. Se utilizan fichas con stock verificado y precios consultados dentro de las últimas 72 horas.')
        if excluded_brands:
            st.write('La referencia es la opción más cara entre los productos comparables verificados en el catálogo, sin Ecoterra. No necesariamente es la más cara de toda la tienda ni representa un ahorro típico.')
        else:
            st.write('La referencia es la opción más cara entre los productos comparables verificados en el catálogo. No necesariamente es la más cara de toda la tienda ni representa un ahorro típico.')
        st.write('La comparación de canasta usa cantidades equivalentes en envases enteros. Las promociones sujetas a condiciones no se aplican; el precio final puede variar si se cumplen sus condiciones.')
        if offers:
            st.write('Beneficios condicionados no aplicados:')
            for offer in dict.fromkeys(offers):
                st.write(f'• {offer}')
