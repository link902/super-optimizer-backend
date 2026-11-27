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
        st.warning(f'No se puede calcular una canasta comparable: {error}')
        return

    if enforce_example_cap and all(item['quantity'] == 1 for item in order) and comparison['total']:
        total = comparison['total']
        exceeds_cap = 10 * total['diferencia'] > 3 * total['referencia']
        exceeds_cap |= any(10 * p['diferencia'] > 3 * p['cara']['subtotal'] for p in comparison['pairs'].values())
        if exceeds_cap:
            st.warning('Los precios cambiaron y el ejemplo ya no cumple el tope de 30%. Recarga la página para generar otro ejemplo.')
            return

    st.subheader('Resultado frente a la opción más cara verificada')
    if excluded_brands:
        st.caption('En Líder, referencia: opción más cara verificada del catálogo excluyendo Ecoterra; no es el máximo absoluto. Precios generales, sin aplicar promociones condicionadas; no representa ahorro típico. Al editar la canasta, el porcentaje puede cambiar y superar 30%.')
    else:
        st.caption('Precios generales de fichas verificadas, no promociones condicionadas. La diferencia es frente a la opción más cara verificada de cada grupo; no representa ahorro típico ni garantiza los extremos de toda la tienda.')
    total = comparison['total']
    if total:
        percent = 100 * total['diferencia'] / total['referencia'] if total['referencia'] else 0
        percent_text = f'{percent:.2f}'.replace('.', ',') + '%'
        st.success(f"Diferencia frente a la opción más cara verificada: {clp(total['diferencia'])} ({percent_text})")
        m1,m2,m3=st.columns(3)
        m1.metric('Referencia más cara verificada',clp(total['referencia']))
        m2.metric('Canasta optimizada verificada',clp(total['optimizado']))
        m3.metric('Diferencia frente a esa referencia',clp(total['diferencia']),delta=percent_text)
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
        st.warning('No se calcula un total ni porcentaje de canasta: al menos un grupo no tiene dos alternativas equivalentes, vigentes y sin promoción condicionada aplicable. Puedes quitarlo para comparar el resto.')

    st.write('### Detalle por grupo')
    for item in order:
        gid=item['generic_item_id']; qty=item['quantity']; pair=comparison['pairs'][gid]
        name=next((n for n,i in options.items() if i==gid),str(gid))
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
                    st.caption(f"Beneficio condicionado no aplicado para {row['marca']}: {row['condicional']}. El cobro real puede variar.")
            st.write(f"Diferencia frente a la opción más cara: **{clp(pair['diferencia'])} ({pair['porcentaje']:.1f}%)**")
            continue
        allowed_rows = [r for r in before if (r.get('brand') or '').strip().casefold() not in {b.casefold() for b in excluded_brands}]
        variable=compare_by_100g(allowed_rows,1,gid,qty)
        if not variable:
            st.info('Sin dos alternativas comparables verificadas para esta cantidad. No se calcula la diferencia.')
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
                st.caption(f"Promoción condicionada no aplicada para {row['marca']}: {row['condicional']}. El costo real puede variar.")
