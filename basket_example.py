"""Canasta de ejemplo y comparación exacta para Líder; solo precios verificados."""
from fractions import Fraction
import json
from expensive_scenario import compare_group


def compare_selected(before, after, order, now=None, excluded_brands=()):
    """Dos lecturas estables. Nunca suma grupos sin dos opciones equivalentes."""
    ids = [x['generic_item_id'] for x in order]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Selecciona grupos distintos para calcular la canasta.')
    if before is None or after is None:
        raise ValueError('No se pudieron confirmar los precios antes y después.')
    def snapshot(rows):
        selected = [r for r in rows if r.get('supermarket_id') == 1 and r.get('generic_item_id') in ids]
        keys = [r.get('id') for r in selected]
        if len(keys) != len(set(keys)):
            raise ValueError('Hay fichas duplicadas en el catálogo.')
        return json.dumps(sorted(selected, key=lambda r:r['id']), sort_keys=True, ensure_ascii=False)
    if snapshot(before) != snapshot(after):
        raise ValueError('El catálogo cambió durante la comparación; vuelve a intentarlo.')
    excluded = {brand.casefold().strip() for brand in excluded_brands}
    eligible_rows = [r for r in before if (r.get('brand') or '').casefold().strip() not in excluded]
    pairs = {}
    for item in order:
        gid, qty = item['generic_item_id'], item['quantity']
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            raise ValueError('La cantidad debe ser un entero positivo.')
        pairs[gid] = compare_group(eligible_rows, 1, gid, qty, now)
    missing = [gid for gid in ids if pairs[gid] is None]
    if missing:
        return {'pairs':pairs, 'missing':missing, 'total':None}
    optimized = sum(v['barata']['subtotal'] for v in pairs.values())
    reference = sum(v['cara']['subtotal'] for v in pairs.values())
    difference = reference - optimized
    return {'pairs':pairs, 'missing':[], 'total':{
        'optimizado':optimized, 'referencia':reference, 'diferencia':difference,
        'porcentaje':round(100*difference/reference,1) if reference else 0.0}}


EXAMPLE_EXCLUDED_BRANDS = ('Ecoterra',)
EXAMPLE_GROUPS = (1, 4, 81)  # arroz 1 kg, spaghetti y tallarines 400 g


def best_example(rows, catalog, now=None):
    """Precarga la canasta acordada si sus pares siguen siendo válidos.

    No inventa ni congela precios: si faltan fichas vigentes, cantidades
    equivalentes o se supera el tope real del 30%, no precarga el ejemplo.
    """
    if not rows or len({r['id'] for r in rows}) != len(rows):
        return None
    if not set(EXAMPLE_GROUPS).issubset({item['id'] for item in catalog}):
        return None
    clean = [r for r in rows if (r.get('brand') or '').strip().casefold() != 'ecoterra']
    pairs = {gid:compare_group(clean,1,gid,1,now) for gid in EXAMPLE_GROUPS}
    if any(not p or Fraction(p['diferencia'],p['cara']['subtotal']) > Fraction(3,10) for p in pairs.values()):
        return None
    optimized = sum(p['barata']['subtotal'] for p in pairs.values())
    reference = sum(p['cara']['subtotal'] for p in pairs.values())
    score = Fraction(reference-optimized,reference)
    if score > Fraction(3,10):
        return None
    return {'ids':list(EXAMPLE_GROUPS),'optimizado':optimized,'referencia':reference,
            'diferencia':reference-optimized,'porcentaje':round(float(score*100),1),
            'pares':pairs}
