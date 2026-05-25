"""
charts.py — Plotly chart factory. Accepts geometry results; returns Figure objects.
No file I/O; no geometry math. Depends only on plotly and the result schema from geometry.py.
"""

import math
import plotly.graph_objects as go


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

GREY_OUTER   = '#6b6b6b'
GREY_FILL    = '#c8c8c8'
BLUE_INNER   = '#1a6fbf'
BLUE_WATER   = '#3a9ad9'
ROAD_COLOR   = '#e8e0cc'
BG_COLOR     = '#f5f5f0'


def _closed_rect_xy(x0, y0, x1, y1):
    return [x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0]


def _circle_xy(cx, cy, r, n=72):
    t = [2 * math.pi * i / n for i in range(n + 1)]
    return [cx + r * math.cos(a) for a in t], [cy + r * math.sin(a) for a in t]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Master 2D Blueprint Map
# ─────────────────────────────────────────────────────────────────────────────

def make_2d_blueprint(results: list) -> go.Figure:
    """
    Top-down orthographic 2D site map.
    Outer concrete boundary: solid grey.
    Internal process channel: dashed blue.
    Corridor gaps: filled road-tan rectangles.
    """
    traces = []

    # Draw corridor gaps first (behind everything)
    for i in range(len(results) - 1):
        c_cur  = results[i]['coordinates']
        c_next = results[i + 1]['coordinates']
        y_max  = max(c_cur['y_end'], c_next['y_end'])
        rx, ry = _closed_rect_xy(c_cur['x_end'], 0, c_next['x_start'], y_max)
        traces.append(go.Scatter(
            x=rx, y=ry, fill='toself',
            fillcolor=ROAD_COLOR, line=dict(color=ROAD_COLOR),
            showlegend=(i == 0), name='Maintenance corridor',
            hoverinfo='skip',
        ))

    for r in results:
        g     = r['geometry']
        c     = r['coordinates']
        stype = r['type']
        x0, x1 = c['x_start'], c['x_end']
        y0, y1 = c['y_start'], c['y_end']
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        h = g['total_height']

        if stype == 'frustum':
            sl = g['slopes']
            # Outer = top opening
            ox, oy = _closed_rect_xy(x0, y0, x1, y1)
            traces.append(go.Scatter(
                x=ox, y=oy, mode='lines', fill='toself',
                fillcolor='rgba(180,180,180,0.25)',
                line=dict(color=GREY_OUTER, width=2),
                showlegend=False, hoverinfo='skip',
            ))
            # Inner = bottom footprint (positioned using per-side slopes)
            ix0 = x0 + h * sl['W']
            ix1 = x1 - h * sl['E']
            iy0 = y0 + h * sl['S']
            iy1 = y1 - h * sl['N']
            ix, iy = _closed_rect_xy(ix0, iy0, ix1, iy1)
            traces.append(go.Scatter(
                x=ix, y=iy, mode='lines',
                line=dict(color=BLUE_INNER, width=1.5, dash='dash'),
                showlegend=False, hoverinfo='skip',
            ))

        elif stype == 'rectangular':
            ox, oy = _closed_rect_xy(x0, y0, x1, y1)
            traces.append(go.Scatter(
                x=ox, y=oy, mode='lines', fill='toself',
                fillcolor='rgba(180,180,180,0.25)',
                line=dict(color=GREY_OUTER, width=2),
                showlegend=False, hoverinfo='skip',
            ))
            li, wi = g['l_internal'], g['w_internal']
            ix, iy = _closed_rect_xy(cx - li/2, cy - wi/2, cx + li/2, cy + wi/2)
            traces.append(go.Scatter(
                x=ix, y=iy, mode='lines',
                line=dict(color=BLUE_INNER, width=1.5, dash='dash'),
                showlegend=False, hoverinfo='skip',
            ))

        elif stype == 'circular':
            r_out = g['d_outer'] / 2
            r_in  = g['d_internal'] / 2
            ox, oy = _circle_xy(cx, cy, r_out)
            ix, iy = _circle_xy(cx, cy, r_in)
            traces.append(go.Scatter(
                x=ox, y=oy, mode='lines', fill='toself',
                fillcolor='rgba(180,180,180,0.25)',
                line=dict(color=GREY_OUTER, width=2),
                showlegend=False, hoverinfo='skip',
            ))
            traces.append(go.Scatter(
                x=ix, y=iy, mode='lines',
                line=dict(color=BLUE_INNER, width=1.5, dash='dash'),
                showlegend=False, hoverinfo='skip',
            ))

        # Fillet annotation in plan
        if g.get('a_loss', 0) > 0:
            R = math.sqrt(g['a_loss'] / (4 - math.pi))
            traces.append(go.Scatter(
                x=[cx], y=[y1 + 0.5],
                mode='text',
                text=[f'R={R:.2f} m'],
                textfont=dict(size=9, color='#888888'),
                showlegend=False, hoverinfo='skip',
            ))

        # ID + V_water label
        traces.append(go.Scatter(
            x=[cx], y=[cy],
            mode='text',
            text=[f"<b>{r['id']}</b><br>{g['v_water']:.1f} m³"],
            textfont=dict(size=10, color='#222222'),
            showlegend=False, hoverinfo='skip',
        ))

    # Dummy legend entries
    traces += [
        go.Scatter(x=[None], y=[None], mode='lines',
                   line=dict(color=GREY_OUTER, width=2),
                   name='Outer concrete boundary'),
        go.Scatter(x=[None], y=[None], mode='lines',
                   line=dict(color=BLUE_INNER, width=1.5, dash='dash'),
                   name='Internal process channel'),
    ]

    fig = go.Figure(traces)
    fig.update_layout(
        title='Site Layout — 2D Blueprint Map',
        xaxis=dict(title='X (m)', scaleanchor='y', scaleratio=1,
                   showgrid=True, gridcolor='#e0e0e0', zeroline=False),
        yaxis=dict(title='Y (m)', showgrid=True,
                   gridcolor='#e0e0e0', zeroline=False),
        plot_bgcolor=BG_COLOR,
        paper_bgcolor='white',
        legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='#cccccc', borderwidth=1),
        margin=dict(l=60, r=40, t=60, b=60),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. Aspect-Ratio-Locked 3D Box View
# ─────────────────────────────────────────────────────────────────────────────

def _prism_mesh(v_bot, v_top, color, opacity, name):
    """
    Closed 8-vertex prism (frustum or box) as Mesh3d.
    v_bot, v_top: each a list of 4 (x,y,z) tuples [SW, SE, NE, NW].
    """
    verts = v_bot + v_top
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    # 12 triangles: bottom, top, 4 side quads (each split into 2)
    i_f = [0, 0,  4, 4,  0, 0,  1, 1,  2, 2,  3, 3]
    j_f = [1, 2,  5, 6,  1, 5,  2, 6,  3, 7,  0, 4]
    k_f = [2, 3,  6, 7,  5, 4,  6, 5,  7, 6,  4, 7]
    return go.Mesh3d(
        x=xs, y=ys, z=zs,
        i=i_f, j=j_f, k=k_f,
        color=color, opacity=opacity,
        name=name, showlegend=True, flatshading=True,
        lighting=dict(ambient=0.6, diffuse=0.8),
    )


def _cylinder_side(radius, z_bot, z_top, color, opacity, name, n=72):
    """Cylinder side wall only via go.Surface — avoids Mesh3d depth-sort artifacts."""
    theta = [2 * math.pi * i / n for i in range(n + 1)]
    xs = [[radius * math.cos(t)] * 2 for t in theta]
    ys = [[radius * math.sin(t)] * 2 for t in theta]
    zs = [[z_bot, z_top]] * (n + 1)
    return go.Surface(
        x=xs, y=ys, z=zs,
        colorscale=[[0, color], [1, color]],
        opacity=opacity, showscale=False,
        name=name, showlegend=(name is not None),
        lighting=dict(ambient=0.6, diffuse=0.8),
    )


def _disk_surface(radius, z, color, opacity, n=72):
    """Flat filled disk at height z via go.Surface (r from 0 → radius)."""
    theta = [2 * math.pi * i / n for i in range(n + 1)]
    xs = [[0.0] + [radius * math.cos(t) for t in theta],
          [0.0] + [radius * math.cos(t) for t in theta]]
    ys = [[0.0] + [radius * math.sin(t) for t in theta],
          [0.0] + [radius * math.sin(t) for t in theta]]
    zs = [[z] * (n + 2)] * 2
    return go.Surface(
        x=xs, y=ys, z=zs,
        colorscale=[[0, color], [1, color]],
        opacity=opacity, showscale=False, showlegend=False,
        lighting=dict(ambient=0.6, diffuse=0.8),
    )


def make_3d_box(result: dict) -> go.Figure:
    """
    Aspect-ratio-locked 3D view of one structure.
    Concrete shell: semi-transparent grey.  Water block: solid blue.
    Fillet radius shown as text annotation — mesh is not deformed.
    """
    g     = result['geometry']
    stype = result['type']
    h     = g['total_height']
    d     = g['water_depth']
    traces = []
    annotations = []

    if stype == 'frustum':
        lb, wb = g['l_bottom'], g['w_bottom']
        sl = g['slopes']

        def _corners(dim_l_half, dim_w_half, z, dl_w, dl_e, dw_s, dw_n):
            return [
                (-dim_l_half - dl_w, -dim_w_half - dw_s, z),  # SW
                (+dim_l_half + dl_e, -dim_w_half - dw_s, z),  # SE
                (+dim_l_half + dl_e, +dim_w_half + dw_n, z),  # NE
                (-dim_l_half - dl_w, +dim_w_half + dw_n, z),  # NW
            ]

        v_shell_bot = _corners(lb/2, wb/2, 0,   0,          0,          0,          0)
        v_shell_top = _corners(lb/2, wb/2, h,   h*sl['W'],  h*sl['E'],  h*sl['S'],  h*sl['N'])
        v_water_top = _corners(lb/2, wb/2, d,   d*sl['W'],  d*sl['E'],  d*sl['S'],  d*sl['N'])

        traces.append(_prism_mesh(v_shell_bot, v_shell_top,
                                  GREY_FILL, 0.30, 'Concrete shell'))
        traces.append(_prism_mesh(v_shell_bot, v_water_top,
                                  BLUE_WATER, 0.70, f'Water  d = {d:.2f} m'))

    elif stype == 'rectangular':
        lo, wo = g['l_outer'], g['w_outer']
        li, wi = g['l_internal'], g['w_internal']

        def _box_corners(lx, wy, z):
            return [(-lx/2,-wy/2,z),(lx/2,-wy/2,z),(lx/2,wy/2,z),(-lx/2,wy/2,z)]

        traces.append(_prism_mesh(_box_corners(lo, wo, 0), _box_corners(lo, wo, h),
                                  GREY_FILL, 0.30, 'Concrete shell'))
        traces.append(_prism_mesh(_box_corners(li, wi, 0), _box_corners(li, wi, d),
                                  BLUE_WATER, 0.70, f'Water  d = {d:.2f} m'))

    elif stype == 'circular':
        r_out = g['d_outer']    / 2
        r_in  = g['d_internal'] / 2
        # Outer concrete wall — side surface only (no overlapping solid interiors)
        traces.append(_cylinder_side(r_out, 0, h, GREY_FILL,  0.45, 'Concrete shell'))
        # Inner wall of concrete (annular top view)
        traces.append(_cylinder_side(r_in,  0, h, GREY_FILL,  0.20, None))
        # Water body side + top disk surface
        traces.append(_cylinder_side(r_in,  0, d, BLUE_WATER, 0.55, f'Water  d = {d:.2f} m'))
        traces.append(_disk_surface(r_in, d, BLUE_WATER, 0.85))

    # Fillet annotation (no mesh deformation per spec)
    if g.get('a_loss', 0) > 0:
        R = math.sqrt(g['a_loss'] / (4 - math.pi))
        annotations.append(dict(
            x=0, y=0, z=h * 1.05,
            text=f'Fillet Radius: {R:.2f} m',
            showarrow=False,
            font=dict(size=12, color='#555555'),
        ))

    fig = go.Figure(traces)
    scene = dict(
        xaxis_title='X (m)',
        yaxis_title='Y (m)',
        zaxis_title='Z (m)',
        aspectmode='data',
        bgcolor='#f0f0f0',
    )
    if annotations:
        scene['annotations'] = annotations

    fig.update_layout(
        title=f"3D View — {result['id']}: {result['name']}",
        scene=scene,
        legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='#cccccc', borderwidth=1),
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor='white',
    )
    return fig
