"""Comparación conservadora por envases enteros, sin modificar el catálogo.

Los formatos se asignan solo a fichas ya validadas por /pilot-prices. Incorporar
un ID nuevo requiere confirmar explícitamente su formato y unidad.
"""
from datetime import datetime, timedelta, timezone
from functools import reduce
from math import lcm
from fractions import Fraction
import json
import re

# id: (grupo, contenido por envase en g/ml, unidad)
FORMATS = {
    2:(1,1000,'g'), 241:(1,1000,'g'), 310:(1,1000,'g'),
    226:(1,1000,'g'), 231:(1,1000,'g'), 233:(1,1000,'g'), 235:(1,1000,'g'),
    4:(2,1000,'ml'), 11:(2,1000,'ml'), 240:(2,1000,'ml'), 287:(2,1000,'ml'), 292:(2,1000,'ml'),
    8:(4,400,'g'), 16:(4,400,'g'), 303:(4,400,'g'), 304:(4,400,'g'),
    281:(28,200,'g'), 282:(28,200,'g'),
    252:(60,390,'g'), 251:(65,410,'g'), 246:(71,200,'ml'), 250:(71,200,'ml'),
    283:(74,91,'g drenado'), 284:(74,91,'g drenado'),
    285:(75,125,'g'), 286:(75,80,'g drenado'),
    289:(76,1000,'ml'), 294:(76,1000,'ml'), 295:(76,1000,'ml'), 296:(76,1000,'ml'),
    288:(77,1000,'ml'), 290:(77,1000,'ml'), 291:(77,1000,'ml'), 293:(77,1000,'ml'),
    297:(78,150,'g'), 298:(78,150,'g'),
    299:(79,150,'g'), 300:(79,150,'g'), 301:(79,155,'g'), 302:(79,155,'g'),
    305:(81,400,'g'), 306:(81,400,'g'), 307:(81,400,'g'), 308:(81,400,'g'),
    309:(82,400,'g'), 311:(83,500,'g'), 312:(83,250,'g'),
    3:(2,1000,'ml'), 247:(71,200,'ml'),
    322:(76,1000,'ml'), 323:(77,1000,'ml'), 324:(2,1000,'ml'),
    325:(77,1000,'ml'), 326:(81,400,'g'), 327:(4,400,'g'), 328:(74,91,'g drenado'),
    329:(2,1000,'ml'), 330:(76,1000,'ml'),
    331:(65,390,'g'), 332:(78,400,'g'), 333:(79,900,'g'), 334:(79,120,'g'),
}

# Variantes específicamente verificadas, no basta coincidir en grupo. El yogur
# aflanado de 155 g no se incluye sin verificar su formulación equivalente.
VARIABLE_FORMAT_IDS = {65:{251,331}, 78:{297,332}, 79:{299,333,334}}
# Cantidad solicitada por unidad del selector. No hacer 31 potes de 150 g
# equivalentes a 30 de 155 g cuando se pidió un solo yogur.
TARGET_AMOUNTS = {1:1000, 2:1000, 4:400, 28:200, 60:390, 65:410, 71:200,
                  74:91, 75:125, 76:1000, 77:1000, 78:150, 79:150,
                  81:400, 82:400, 83:500}
MAX_AGE = timedelta(hours=72)

def eligible(row, store, group, now):
    fmt = FORMATS.get(row.get('id'))
    if not fmt or fmt[0] != group or row.get('generic_item_id') != group or row.get('supermarket_id') != store:
        return False
    if row.get('in_stock') is not True or not (row.get('source_url') or '').startswith('https://'):
        return False
    try:
        checked = datetime.fromisoformat(row['price_checked_at'].replace('Z','+00:00'))
        price, normal = int(row['price']), int(row['regular_price'])
        age = now - checked
    except (KeyError, TypeError, ValueError):
        return False
    if checked.tzinfo is None or age < timedelta(0) or age > MAX_AGE or price <= 0 or normal <= 0:
        return False
    kind = row.get('offer_type')
    return (kind == 'none' and price == normal) or (kind == 'general' and price <= normal)

def conditional_quantity_applies(row, packs):
    """Excluir comparaciones cuando la compra alcanza un descuento por volumen.

    El catálogo no permite calcular fielmente una promoción condicionada. Nunca
    presenta un subtotal de precio normal como el costo real cuando ya se alcanza
    una condición conocida de cantidad (p.ej. 2 x $3.000).
    """
    offer = str(row.get('conditional_offer') or '')
    match = re.search(r'(?<!\d)(\d+)\s*(?:x|por)\s*\$', offer, re.IGNORECASE)
    return bool(match and packs >= int(match.group(1)))


def compare_group(rows, store, group, quantity=1, now=None):
    """Devuelve extremos para una misma cantidad exacta con envases enteros.

    Usa la cantidad nominal del selector y únicamente envases enteros que
    suman exactamente esa cantidad. Cada grupo es independiente.
    """
    now = now or datetime.now(timezone.utc)
    if quantity < 1:
        raise ValueError('La cantidad debe ser positiva')
    target = TARGET_AMOUNTS.get(group)
    if not target:
        return None
    options = [r for r in rows if eligible(r, store, group, now)
               and target % FORMATS[r['id']][1] == 0
               and not conditional_quantity_applies(r, quantity * target // FORMATS[r['id']][1])]
    if len(options) < 2:
        return None
    units = {FORMATS[r['id']][2] for r in options}
    if len(units) != 1:
        return None
    amount = target * quantity
    def option(row):
        packs = amount // FORMATS[row['id']][1]
        return {'id': row['id'], 'producto': row['product_name'], 'marca': row['brand'],
                'formato': f"{FORMATS[row['id']][1]} {FORMATS[row['id']][2]}",
                'envases': packs, 'precio_envase': int(row['price']),
                'subtotal': int(row['price']) * packs, 'consulta': row['price_checked_at'],
                'ficha': row['source_url'], 'oferta': row['offer_type'],
                'condicional': row.get('conditional_offer') or ''}
    ranked = sorted((option(r) for r in options), key=lambda r:(r['subtotal'], r['id']))
    cheap, expensive = ranked[0], ranked[-1]
    diff = expensive['subtotal'] - cheap['subtotal']
    return {'cantidad': amount, 'unidad': next(iter(units)), 'barata': cheap,
            'cara': expensive, 'diferencia': diff,
            'porcentaje': round(100 * diff / expensive['subtotal'], 1)}


def compare_by_100g(rows, store, group, quantity=1, now=None):
    """Ordena por precio general por 100 g y muestra compras de envases enteros.

    No suma precios de tamaños distintos como si fueran iguales, no calcula
    ahorro de canasta y no hace compras fraccionarias. Solo las fichas con
    variantes explícitamente verificadas entran en esta comparación.
    """
    if not isinstance(quantity, int) or quantity < 1:
        raise ValueError('La cantidad debe ser un entero positivo')
    now = now or datetime.now(timezone.utc)
    ids = VARIABLE_FORMAT_IDS.get(group, set()) if store == 1 else set()
    options = [r for r in rows if r.get('id') in ids and eligible(r, store, group, now)
               and not conditional_quantity_applies(r, quantity)]
    if len(options) < 2 or len({r['id'] for r in options}) != len(options):
        return None
    def rate(r):
        return Fraction(100 * int(r['price']), FORMATS[r['id']][1])
    def option(r):
        weight = FORMATS[r['id']][1]
        return {'id':r['id'], 'producto':r['product_name'], 'marca':r['brand'],
                'formato':f'{weight} g', 'contenido_g':weight*quantity,
                'envases':quantity, 'precio_envase':int(r['price']),
                'subtotal':int(r['price'])*quantity, 'precio_100g':float(rate(r)),
                'consulta':r['price_checked_at'], 'ficha':r['source_url'],
                'condicional':r.get('conditional_offer') or ''}
    ranked=sorted(options, key=lambda r:(rate(r),r['id']))
    return {'barata':option(ranked[0]), 'cara':option(ranked[-1])}


def compare_basket(before, after, store, order, habitual, now=None):
    """Contrasta ambos escenarios solo si catálogo, cantidades y óptimo coinciden."""
    now = now or datetime.now(timezone.utc)
    gids = [x['generic_item_id'] for x in order]
    if len(gids) != len(set(gids)) or not gids:
        raise ValueError('La selección contiene grupos duplicados o está vacía.')
    def snapshot(rows):
        selected = [r for r in rows if r.get('supermarket_id') == store and r.get('generic_item_id') in gids]
        return json.dumps(sorted(selected, key=lambda r:r['id']), sort_keys=True, ensure_ascii=False)
    if snapshot(before) != snapshot(after):
        raise ValueError('El catálogo cambió durante la comparación; vuelve a intentarlo.')
    if len(habitual['optimal_cart']) != len(order) or len(habitual['baseline_cart']) != len(order):
        raise ValueError('La canasta habitual no contiene todos los grupos.')
    results = []
    opt_sum = base_sum = 0
    def parse_price(text):
        return int(str(text).replace('$','').replace(' CLP','').replace(',','').replace('.','').strip())
    for index, item in enumerate(order):
        gid, qty = item['generic_item_id'], item['quantity']
        result = compare_group(before, store, gid, qty, now)
        if not result:
            raise ValueError('Faltan dos alternativas elegibles y recientes en algún grupo.')
        for key in ('optimal_cart','baseline_cart'):
            item_row = habitual[key][index]
            matches = [r for r in before if eligible(r,store,gid,now) and r['product_name'] == item_row['Producto'] and r['brand'] == item_row['Marca']]
            if len(matches) != 1:
                raise ValueError('Una referencia habitual no tiene ficha elegible y reciente.')
            row = matches[0]
            packs = item_row['Cantidad']
            if FORMATS[row['id']][1]*packs != result['cantidad'] or parse_price(item_row['Precio Unitario']) != row['price'] or parse_price(item_row['Subtotal']) != row['price']*packs:
                raise ValueError('Las cantidades o precios no coinciden entre escenarios.')
            if key == 'optimal_cart':
                if row['price']*packs != result['barata']['subtotal']:
                    raise ValueError('La opción óptima no coincide entre escenarios.')
                opt_sum += row['price']*packs
            else:
                base_sum += row['price']*packs
        results.append(result)
    if opt_sum != habitual['total_optimal'] or base_sum != habitual['total_baseline']:
        raise ValueError('Los totales de referencia no coinciden con sus productos.')
    expensive = sum(r['cara']['subtotal'] for r in results)
    normal_pct = round((base_sum-opt_sum)*100/base_sum,1) if base_sum else 0
    max_pct = round((expensive-opt_sum)*100/expensive,1) if expensive else 0
    return {'optimizado':opt_sum, 'habitual':base_sum, 'mas_cara':expensive,
            'porcentaje_habitual':normal_pct, 'porcentaje_mas_cara':max_pct,
            'diferencia_pp':round(max_pct-normal_pct,1), 'grupos':results}
