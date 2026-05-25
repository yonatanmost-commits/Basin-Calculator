"""
exports.py — Excel, CAD (DXF), and PNG export functions.
Each function is self-contained: accepts results list + optional paths.
"""

import math
import os


# ─────────────────────────────────────────────────────────────────────────────
# Shared: raw dimension summary string (preserves original comma-sep values)
# ─────────────────────────────────────────────────────────────────────────────

def _raw_dim_string(dims: dict, stype: str) -> str:
    """Return a compact human-readable string of the original input dimensions."""
    if stype == 'frustum':
        lb = dims.get('length_bottom', '')
        wb = dims.get('width_bottom', '')
        h  = dims.get('total_height', '')
        sl = dims.get('slope_uniform') if not dims.get('uneven_slopes_enabled') \
             else f"N{dims.get('slope_north',0)} S{dims.get('slope_south',0)} " \
                  f"E{dims.get('slope_east',0)} W{dims.get('slope_west',0)}"
        return f"L={lb} W={wb} h={h} slope={sl}"
    if stype == 'rectangular':
        return (f"L={dims.get('length_internal','')} "
                f"W={dims.get('width_internal','')} "
                f"h={dims.get('total_height','')} "
                f"tw={dims.get('wall_thickness',0)} "
                f"R={dims.get('corner_fillet_radius_m',0)}")
    if stype == 'circular':
        return (f"D={dims.get('diameter_internal','')} "
                f"h={dims.get('total_height','')} "
                f"tw={dims.get('wall_thickness',0)}")
    return ''


def _footprint_string(r: dict) -> str:
    g = r['geometry']
    if r['type'] == 'circular':
        return f"Ø{g['d_outer']:.2f} m"
    fx = g['outer_footprint_x']
    fy = g['outer_footprint_y']
    return f"{fx:.2f} × {fy:.2f} m"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Excel Engine
# ─────────────────────────────────────────────────────────────────────────────

def export_excel(results: list, template_path: str, output_path: str = None) -> str:
    """
    Load existing Excel template, inject a summary table, save.
    Returns the path written to.
    """
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl required: pip install openpyxl")

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Excel template not found: {template_path}")

    wb = openpyxl.load_workbook(template_path)
    ws = wb.active

    # Detect header row: first row whose first cell matches our ID column header.
    # Everything below it is data we own — clear it before each write.
    HEADER_MARKER = 'ID'
    header_row = None
    for i, row in enumerate(ws.iter_rows(min_col=1, max_col=1, values_only=True), start=1):
        if row[0] == HEADER_MARKER:
            header_row = i
            break

    if header_row is None:
        # Template has no header row yet — write one after the last non-empty row
        last_used = ws.max_row
        header_row = last_used + 1
        headers = [
            'ID', 'Name', 'Type',
            'Raw Dimensions',
            'Footprint (m or m²)',
            'Water Volume (m³)',
            'Total Excavation Volume (m³)',
        ]
        ws.append(headers)

    # Delete all rows below the header row so each run is idempotent
    data_start = header_row + 1
    if ws.max_row >= data_start:
        ws.delete_rows(data_start, ws.max_row - header_row)

    for r in results:
        g = r['geometry']
        ws.append([
            r['id'],
            r['name'],
            r['type'],
            _raw_dim_string(r['dimensions'], r['type']),
            _footprint_string(r),
            round(g['v_water'], 3),
            round(g['v_total_excavation'], 3),
        ])

    data_end = data_start + len(results) - 1
    vw_col  = 'F'   # Water Volume
    ve_col  = 'G'   # Excavation Volume
    ws.append([
        'TOTAL', '', '', '', '',
        f'=SUM({vw_col}{data_start}:{vw_col}{data_end})',
        f'=SUM({ve_col}{data_start}:{ve_col}{data_end})',
    ])

    dest = output_path or template_path
    wb.save(dest)
    wb.close()
    return dest


# ─────────────────────────────────────────────────────────────────────────────
# 2. CAD Engine (DXF)
# ─────────────────────────────────────────────────────────────────────────────

_DXF_LAYERS = {
    'outer':    ('SITE_OUTER_BOUNDARIES', 7),   # white/black
    'inner':    ('FLUID_CHANNELS',        5),   # blue
    'roads':    ('MAINTENANCE_ROADS',     1),   # red (standard CAD road colour)
}


def _add_dxf_layers(doc):
    for key, (name, color) in _DXF_LAYERS.items():
        doc.layers.add(name=name, color=color)


def _rect_dxf(msp, x0, y0, x1, y1, layer):
    pts = [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
    msp.add_lwpolyline(pts, dxfattribs={'layer': layer, 'closed': True})


def _circle_dxf(msp, cx, cy, r, layer):
    msp.add_circle((cx, cy), r, dxfattribs={'layer': layer})


def export_cad(results: list, output_path: str = 'site_plan.dxf') -> str:
    """Generate a 2D DXF site plan with three layers. Returns the path written."""
    try:
        import ezdxf
    except ImportError:
        raise ImportError("ezdxf required: pip install ezdxf")

    doc = ezdxf.new(dxfversion='R2010')
    _add_dxf_layers(doc)
    msp = doc.modelspace()

    L_OUTER = _DXF_LAYERS['outer'][0]
    L_INNER = _DXF_LAYERS['inner'][0]
    L_ROADS = _DXF_LAYERS['roads'][0]

    for i, r in enumerate(results):
        g     = r['geometry']
        c     = r['coordinates']
        stype = r['type']
        x0, x1 = c['x_start'], c['x_end']
        y0, y1 = c['y_start'], c['y_end']
        cx, cy = (x0+x1)/2, (y0+y1)/2
        h = g['total_height']

        if stype == 'frustum':
            sl = g['slopes']
            _rect_dxf(msp, x0, y0, x1, y1, L_OUTER)
            _rect_dxf(msp, x0 + h*sl['W'], y0 + h*sl['S'],
                           x1 - h*sl['E'], y1 - h*sl['N'], L_INNER)

        elif stype == 'rectangular':
            _rect_dxf(msp, x0, y0, x1, y1, L_OUTER)
            li, wi = g['l_internal'], g['w_internal']
            _rect_dxf(msp, cx-li/2, cy-wi/2, cx+li/2, cy+wi/2, L_INNER)

        elif stype == 'circular':
            _circle_dxf(msp, cx, cy, g['d_outer']/2,    L_OUTER)
            _circle_dxf(msp, cx, cy, g['d_internal']/2, L_INNER)

        # Corridor gap as road rectangle
        if i < len(results) - 1:
            c_next = results[i+1]['coordinates']
            y_max  = max(y1, c_next['y_end'])
            _rect_dxf(msp, x1, 0, c_next['x_start'], y_max, L_ROADS)

        # Structure label
        msp.add_text(
            f"{r['id']} ({r['type']})",
            dxfattribs={'insert': (cx, cy), 'height': 0.5, 'layer': L_OUTER},
        )

    doc.saveas(output_path)
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# 3. PNG Image Capture
# ─────────────────────────────────────────────────────────────────────────────

def export_png(results: list, output_dir: str = '.') -> list:
    """
    Save the 2D blueprint and one 3D box view per structure as PNG files.
    Requires kaleido: pip install kaleido
    Returns list of file paths written.
    """
    from charts import make_2d_blueprint, make_3d_box

    os.makedirs(output_dir, exist_ok=True)
    paths = []

    # 2D blueprint
    fig2d = make_2d_blueprint(results)
    path2d = os.path.join(output_dir, 'blueprint_2d.png')
    fig2d.write_image(path2d, width=1600, height=900, scale=2)
    paths.append(path2d)

    # 3D per structure
    for r in results:
        fig3d = make_3d_box(r)
        fname = f"3d_{r['id'].replace('-', '_').lower()}.png"
        path3d = os.path.join(output_dir, fname)
        fig3d.write_image(path3d, width=1200, height=900, scale=2)
        paths.append(path3d)

    return paths
