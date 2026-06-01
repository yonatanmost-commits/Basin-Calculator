"""
geometry.py — Pure math engine for basin volume and layout calculations.
No UI, no file I/O dependencies beyond loading state.json.
"""

import json
import math


# ---------------------------------------------------------------------------
# 1. Input Pre-Processing: Auto-Averager
# ---------------------------------------------------------------------------

def parse_dim(value) -> float:
    """Average comma-separated field measurements; pass scalars through."""
    if isinstance(value, str) and ',' in value:
        parts = [float(v.strip()) for v in value.split(',')]
        return sum(parts) / len(parts)
    return float(value) if value is not None else 0.0


# ---------------------------------------------------------------------------
# 2. Frustum Slope Resolver
# ---------------------------------------------------------------------------

def _resolve_slopes(dims: dict) -> tuple:
    """Return (s_N, s_S, s_E, s_W) based on uneven_slopes_enabled flag."""
    if dims.get('uneven_slopes_enabled', False):
        return (
            dims.get('slope_north') or 0.0,
            dims.get('slope_south') or 0.0,
            dims.get('slope_east') or 0.0,
            dims.get('slope_west') or 0.0,
        )
    s = dims.get('slope_uniform') or 0.0
    return s, s, s, s


def _resolve_frustum_dims(dims: dict, slopes: tuple | None = None) -> tuple:
    """Return (l_bot, w_bot, l_top, w_top) honoring dimension_basis.

    basis 'bottom' (default): entered length_bottom/width_bottom; top projected
    by slope (or an explicit length_top/width_top override if both present).
    basis 'top': entered length_top/width_top; bottom derived by subtracting the
    slope projection.
    slopes: optional pre-computed (s_n, s_s, s_e, s_w); recomputed from dims if omitted.
    """
    h = parse_dim(dims['total_height'])
    s_n, s_s, s_e, s_w = slopes if slopes is not None else _resolve_slopes(dims)
    basis = dims.get('dimension_basis', 'bottom')

    if basis == 'top':
        l_top = parse_dim(dims['length_top'])
        w_top = parse_dim(dims['width_top'])
        l_bot = l_top - h * (s_w + s_e)
        w_bot = w_top - h * (s_s + s_n)
        # Precondition: caller must validate l_bot > 0 and w_bot > 0. When the top
        # is too small for slope×height these go non-positive; the UI checks this
        # via geometry.frustum_basis_error (added in a later task) before compute.
        return l_bot, w_bot, l_top, w_top

    l_bot = parse_dim(dims['length_bottom'])
    w_bot = parse_dim(dims['width_bottom'])
    if dims.get('length_top') is not None and dims.get('width_top') is not None:
        l_top = parse_dim(dims['length_top'])
        w_top = parse_dim(dims['width_top'])
    else:
        l_top = l_bot + h * (s_w + s_e)
        w_top = w_bot + h * (s_s + s_n)
    return l_bot, w_bot, l_top, w_top


def frustum_basis_error(dims: dict) -> str | None:
    """Return a human-readable reason if a top-basis frustum's derived bottom is
    non-positive, else None. Pure helper used by the UI for per-row validation."""
    if dims.get('dimension_basis', 'bottom') != 'top':
        return None
    l_bot, w_bot, _l_top, _w_top = _resolve_frustum_dims(dims)
    if l_bot <= 0 or w_bot <= 0:
        return ("top dimensions too small for the slope × height "
                "— derived bottom ≤ 0")
    return None


# ---------------------------------------------------------------------------
# 3. Volume Formulae
# ---------------------------------------------------------------------------

def _prismatoid_volume(a_bot: float, a_top: float, h: float) -> float:
    """Frustum-of-pyramid (prismatoid) volume."""
    return (h / 3.0) * (a_bot + a_top + math.sqrt(a_bot * a_top))


def _compute_frustum(dims: dict) -> dict:
    h     = parse_dim(dims['total_height'])
    d     = parse_dim(dims['water_depth'])
    ud    = min(parse_dim(dims.get('underdrain_height') or 0.0), d)

    s_n, s_s, s_e, s_w = _resolve_slopes(dims)
    l_bot, w_bot, l_top, w_top = _resolve_frustum_dims(dims, (s_n, s_s, s_e, s_w))

    a_bot   = l_bot * w_bot
    a_top   = l_top * w_top
    v_total = _prismatoid_volume(a_bot, a_top, h)

    # Water plane interpolated at depth d using per-side slopes
    l_water = l_bot + d * s_w + d * s_e
    w_water = w_bot + d * s_s + d * s_n
    a_water = l_water * w_water
    v_water = _prismatoid_volume(a_bot, a_water, d)

    # Underdrain: small frustum from z=0 to z=ud, same slopes
    if ud > 0:
        l_ud = l_bot + ud * s_w + ud * s_e
        w_ud = w_bot + ud * s_s + ud * s_n
        v_underdrain = _prismatoid_volume(a_bot, l_ud * w_ud, ud)
    else:
        v_underdrain = 0.0

    return {
        'l_bottom': l_bot, 'w_bottom': w_bot,
        'l_top': l_top,   'w_top': w_top,
        'outer_footprint_x': l_top,
        'outer_footprint_y': w_top,
        'slopes': {'N': s_n, 'S': s_s, 'E': s_e, 'W': s_w},
        'total_height': h,
        'water_depth': d,
        'underdrain_height': ud,
        'v_water': v_water,
        'v_underdrain': v_underdrain,
        'v_process': v_water - v_underdrain,
        'v_total_excavation': v_total,
    }


def _compute_rectangular(dims: dict) -> dict:
    l_int = parse_dim(dims['length_internal'])
    w_int = parse_dim(dims['width_internal'])
    h     = parse_dim(dims['total_height'])
    d     = parse_dim(dims['water_depth'])
    tw    = parse_dim(dims.get('wall_thickness') or 0.0)
    ud    = min(parse_dim(dims.get('underdrain_height') or 0.0), d)

    v_water      = l_int * w_int * d
    v_underdrain = l_int * w_int * ud

    l_outer = l_int + 2.0 * tw
    w_outer = w_int + 2.0 * tw
    v_total = l_outer * w_outer * h

    v_concrete = (l_outer * w_outer - l_int * w_int) * h

    return {
        'l_internal': l_int, 'w_internal': w_int,
        'l_outer': l_outer,  'w_outer': w_outer,
        'outer_footprint_x': l_outer,
        'outer_footprint_y': w_outer,
        'total_height': h,
        'water_depth': d,
        'underdrain_height': ud,
        'v_water': v_water,
        'v_underdrain': v_underdrain,
        'v_process': v_water - v_underdrain,
        'v_total_excavation': v_total,
        'v_concrete': v_concrete,
    }


def _compute_circular(dims: dict) -> dict:
    d_int = parse_dim(dims['diameter_internal'])
    h     = parse_dim(dims['total_height'])
    d     = parse_dim(dims['water_depth'])
    tw    = parse_dim(dims.get('wall_thickness') or 0.0)
    ud    = min(parse_dim(dims.get('underdrain_height') or 0.0), d)

    r_int        = d_int / 2.0
    v_water      = math.pi * r_int ** 2 * d
    v_underdrain = math.pi * r_int ** 2 * ud

    d_outer = d_int + 2.0 * tw
    v_total = math.pi * (d_outer / 2.0) ** 2 * h

    # Concrete = annular ring cross-section × height
    v_concrete = math.pi * ((d_outer / 2.0) ** 2 - r_int ** 2) * h

    return {
        'd_internal': d_int,
        'd_outer': d_outer,
        'outer_footprint_x': d_outer,
        'outer_footprint_y': d_outer,
        'total_height': h,
        'water_depth': d,
        'underdrain_height': ud,
        'v_water': v_water,
        'v_underdrain': v_underdrain,
        'v_process': v_water - v_underdrain,
        'v_total_excavation': v_total,
        'v_concrete': v_concrete,
    }


_DISPATCH = {
    'frustum':     _compute_frustum,
    'rectangular': _compute_rectangular,
    'circular':    _compute_circular,
}


# ---------------------------------------------------------------------------
# 5. Spatial Layout Coordinator
# ---------------------------------------------------------------------------

def compute_layout_coordinates(state: dict) -> list:
    """
    Place all structures sequentially along X, separated by corridor gaps.
    Uses each structure's outer footprint (top for frustums, outer for others).
    Returns list of result dicts: geometry + absolute (x_start, x_end, y_start, y_end).
    """
    corridor = state['global_settings']['corridor_width_m']
    results  = []
    x_cursor = 0.0

    for struct in state['structures']:
        compute_fn = _DISPATCH[struct['type']]
        geom       = compute_fn(struct['dimensions'])

        x_start = x_cursor
        x_end   = x_start + geom['outer_footprint_x']

        results.append({
            'id':         struct['id'],
            'name':       struct['name'],
            'type':       struct['type'],
            'dimensions': struct['dimensions'],
            'geometry':   geom,
            'coordinates': {
                'x_start': x_start,
                'x_end':   x_end,
                'y_start': 0.0,
                'y_end':   geom['outer_footprint_y'],
            },
        })

        x_cursor = x_end + corridor

    return results


def load_and_run(state_path: str = 'state.json') -> list:
    with open(state_path) as f:
        state = json.load(f)
    return compute_layout_coordinates(state)
