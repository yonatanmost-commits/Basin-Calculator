"""
app.py — Streamlit engineering dashboard.
Wraps geometry.py, charts.py, and exports.py. Reads initial values from
state.json; all edits flow through compute_layout_coordinates() in real time.
"""

import copy
import json
import os
import tempfile

import pandas as pd
import streamlit as st

from charts import make_2d_blueprint, make_3d_box
from exports import export_cad, export_excel, read_basins_sheet, write_results_sheet
from geometry import compute_layout_coordinates

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Basin Geometry Dashboard",
    page_icon="🏗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {
    padding-top: 0.55rem !important;
    padding-bottom: 0.3rem !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
.element-container { margin-bottom: 0 !important; }
section.main > div { padding-top: 0 !important; }

h3 { font-size: 1.05rem !important; margin: 0.15rem 0 0.25rem 0 !important; color: #e0e8f4; }
div[data-testid="stDownloadButton"] button {
    background: #1a2e55; color: #c8d8f0; border: 1px solid #2a3f6e;
    font-weight: 600; font-size: 0.82rem; padding: 0.3rem 0.8rem;
}
div[data-testid="stDownloadButton"] button:hover {
    background: #243d6e; color: #ffffff; border-color: #4a6ea0;
}
label[data-testid="stWidgetLabel"] p { font-size: 0.78rem !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Base state (cached read of state.json)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def _load_base() -> dict:
    with open("state.json") as f:
        return json.load(f)

BASE = _load_base()

# ─────────────────────────────────────────────────────────────────────────────
# Session state — owns the live structures list
# ─────────────────────────────────────────────────────────────────────────────
if "structures" not in st.session_state:
    st.session_state.structures = copy.deepcopy(BASE["structures"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _f(val, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if v == v else default
    except (TypeError, ValueError):
        return default


def _to_df(structures: list) -> pd.DataFrame:
    rows = []
    for s in structures:
        d = s["dimensions"]
        t = s["type"]
        uneven = bool(d.get("uneven_slopes_enabled", False))

        if t == "frustum" and uneven:
            df_type = "uneven frustum"
            sN = _f(d.get("slope_north"))
            sS = _f(d.get("slope_south"))
            sE = _f(d.get("slope_east"))
            sW = _f(d.get("slope_west"))
            slope_str = f"{sN};{sS};{sE};{sW}"
        elif t == "frustum":
            df_type = "frustum"
            slope_str = str(_f(d.get("slope_uniform")))
        else:
            df_type = t
            slope_str = ""

        if t == "frustum":
            length = str(d.get("length_bottom", ""))
            width  = str(d.get("width_bottom",  ""))
            wall   = 0.0
        elif t == "rectangular":
            length = str(d.get("length_internal", ""))
            width  = str(d.get("width_internal",  ""))
            wall   = _f(d.get("wall_thickness"))
        else:  # circular
            length = str(d.get("diameter_internal", ""))
            width  = ""
            wall   = _f(d.get("wall_thickness"))

        rows.append({
            "Del":             False,
            "ID":              s["id"],
            "Name":            s["name"],
            "Type":            df_type,
            "Length / Diam (int.)":   length,
            "Width":           width,
            "Height (m)":      _f(d.get("total_height")),
            "Water Depth (m)": _f(d.get("water_depth")),
            "Wall Thick (m)":  wall,
            "Slope":           slope_str,
            "X (m)":           _f(s.get("x_pos"), 0.0),
            "Y (m)":           _f(s.get("y_pos"), 0.0),
        })
    return pd.DataFrame(rows)


def _parse_slope_str(s: str):
    """Parse slope field: '1.5' → uniform, '0;1.5;1.0;1.0' → (N,S,E,W)."""
    parts = [p.strip() for p in str(s).split(";")]
    if len(parts) == 4:
        return None, [_f(p) for p in parts]  # uneven: [N, S, E, W]
    return _f(parts[0]), None                  # uniform


def _from_df(df: pd.DataFrame, base_structures: list) -> list:
    by_id = {s["id"]: s for s in base_structures}
    result = []
    for _, row in df.iterrows():
        df_type = str(row["Type"])
        sid     = str(row["ID"]).strip()
        if not sid:
            continue

        # Map display type back to internal type
        internal_type = "frustum" if df_type in ("frustum", "uneven frustum") else df_type
        base = copy.deepcopy(
            by_id.get(sid, {"id": sid, "name": str(row["Name"]),
                             "type": internal_type, "dimensions": {}})
        )
        base["id"]   = sid
        base["name"] = str(row["Name"])
        base["type"] = internal_type
        d = base.setdefault("dimensions", {})
        h = _f(row["Height (m)"],      1.0)
        w = _f(row["Water Depth (m)"], 0.5)

        if df_type in ("frustum", "uneven frustum"):
            d["length_bottom"] = str(row["Length / Diam (int.)"])
            d["width_bottom"]  = str(row["Width"])
            d["total_height"]  = h
            d["water_depth"]   = w
            uniform, nsew = _parse_slope_str(row["Slope"])
            if df_type == "uneven frustum" and nsew:
                d["uneven_slopes_enabled"] = True
                d["slope_north"]   = nsew[0]
                d["slope_south"]   = nsew[1]
                d["slope_east"]    = nsew[2]
                d["slope_west"]    = nsew[3]
                d["slope_uniform"] = None
            else:
                d["uneven_slopes_enabled"] = False
                d["slope_uniform"] = uniform if uniform is not None else 0.0
                d["slope_north"] = d["slope_south"] = d["slope_east"] = d["slope_west"] = None

        elif df_type == "rectangular":
            d["length_internal"] = str(row["Length / Diam (int.)"])
            d["width_internal"]  = str(row["Width"])
            d["total_height"]    = h
            d["water_depth"]     = w
            d["wall_thickness"]  = _f(row["Wall Thick (m)"])

        else:  # circular
            d["diameter_internal"] = str(row["Length / Diam (int.)"])
            d["total_height"]      = h
            d["water_depth"]       = w
            d["wall_thickness"]    = _f(row["Wall Thick (m)"])

        base["x_pos"] = _f(row.get("X (m)"), 0.0)
        base["y_pos"] = _f(row.get("Y (m)"), 0.0)
        result.append(base)
    return result


_DEFAULT_STRUCTURE = {
    "id": "NEW", "name": "New Structure", "type": "frustum",
    "dimensions": {
        "length_bottom": 10.0, "width_bottom": 5.0,
        "total_height": 3.0, "water_depth": 2.0,
        "slope_uniform": 1.0, "uneven_slopes_enabled": False,
        "slope_north": None, "slope_south": None,
        "slope_east": None, "slope_west": None,
        "wall_thickness": 0.0,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Download helpers
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _excel_bytes(results_json: str) -> bytes:
    results  = json.loads(results_json)
    template = BASE["global_settings"]["excel_template_path"]
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "export.xlsx")
        export_excel(results, template, output_path=out)
        return open(out, "rb").read()


@st.cache_data(show_spinner=False)
def _dxf_bytes(results_json: str) -> bytes:
    results = json.loads(results_json)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "export.dxf")
        export_cad(results, out)
        return open(out, "rb").read()


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Process Excel upload / export
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Process Excel")
    uploaded = st.file_uploader("Upload process Excel", type=["xlsx"], key="proc_upload")
    if uploaded is not None:
        if st.session_state.get("_proc_upload_name") != uploaded.name:
            file_bytes = uploaded.read()
            try:
                new_structs = read_basins_sheet(file_bytes)
            except ValueError:
                new_structs = []   # no Basins sheet — start empty, export still works
            st.session_state.structures         = new_structs
            st.session_state._proc_upload_name  = uploaded.name
            st.session_state._proc_upload_bytes = file_bytes
            st.rerun()

    if st.session_state.get("_proc_upload_bytes") and st.session_state.get("_proc_upload_name"):
        st.caption(f"Loaded: {st.session_state._proc_upload_name}")

    st.markdown("---")
    st.markdown("**Template**")
    @st.cache_data(show_spinner=False)
    def _template_bytes() -> bytes:
        from exports import create_process_template
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "process_template.xlsx")
            create_process_template(path)
            return open(path, "rb").read()

    st.download_button(
        "Download process template",
        data=_template_bytes(),
        file_name="process_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

st.markdown("### Basin Geometry Engineering Dashboard")

# ── Seed X/Y from auto-layout the first time each structure appears ───────────
_seed = compute_layout_coordinates({**BASE, "structures": st.session_state.structures})
for _r, _s in zip(_seed, st.session_state.structures):
    _s.setdefault("x_pos", round(_r["coordinates"]["x_start"], 2))
    _s.setdefault("y_pos", round(_r["coordinates"]["y_start"], 2))

# ── Empty state: show only the Add button ────────────────────────────────────
if not st.session_state.structures:
    if st.button("＋ Add Structure", key="add_btn"):
        new = copy.deepcopy(_DEFAULT_STRUCTURE)
        new["id"] = "S01"
        st.session_state.structures.append(new)
        st.rerun()
    st.stop()

# ── Data editor ──────────────────────────────────────────────────────────────
edited_df = st.data_editor(
    _to_df(st.session_state.structures),
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Del": st.column_config.CheckboxColumn(
            label="Del", help="Check to permanently delete this row.", default=False,
        ),
        "Type": st.column_config.SelectboxColumn(
            options=["frustum", "uneven frustum", "rectangular", "circular"],
            required=True,
        ),
        "Height (m)":       st.column_config.NumberColumn(min_value=0.01, step=0.1,  format="%.2f"),
        "Water Depth (m)":  st.column_config.NumberColumn(min_value=0.01, step=0.1,  format="%.2f"),
        "Wall Thick (m)":   st.column_config.NumberColumn(min_value=0.0,  step=0.05, format="%.3f"),
        "Slope": st.column_config.TextColumn(
            label="Slope  (N;S;E;W for uneven)",
            help="Frustum: single number (e.g. 1.5).\n"
                 "Uneven frustum: four values as N;S;E;W (e.g. 0;1.5;1.0;1.0).",
            default="1.0",
        ),
        "X (m)": st.column_config.NumberColumn(step=0.5, format="%.1f"),
        "Y (m)": st.column_config.NumberColumn(step=0.5, format="%.1f"),
    },
    key="grid",
)

# ── Handle deletion — commit all edits, strip deleted rows, rerun ─────────────
deleted_ids = set(edited_df.loc[edited_df["Del"] == True, "ID"].astype(str))
if deleted_ids:
    kept = _from_df(edited_df[edited_df["Del"] != True].reset_index(drop=True),
                    st.session_state.structures)
    st.session_state.structures = kept
    st.rerun()

# ── Add structure button ──────────────────────────────────────────────────────
if st.button("＋ Add Structure", key="add_btn"):
    current = _from_df(edited_df, st.session_state.structures)
    new = copy.deepcopy(_DEFAULT_STRUCTURE)
    existing_ids = {s["id"] for s in current}
    n = len(current) + 1
    while f"S{n:02d}" in existing_ids:
        n += 1
    new["id"] = f"S{n:02d}"
    current.append(new)
    st.session_state.structures = current
    st.rerun()

# ── Recompute geometry ────────────────────────────────────────────────────────
try:
    structures = _from_df(edited_df, st.session_state.structures)
    if not structures:
        st.info("Add at least one structure to see results.")
        st.stop()
    results = compute_layout_coordinates({**BASE, "structures": structures})
    # Apply manual X/Y position overrides from the editor
    for r, s in zip(results, structures):
        x = s.get("x_pos")
        y = s.get("y_pos", 0.0)
        if x is not None:
            fp_x = r["geometry"]["outer_footprint_x"]
            fp_y = r["geometry"]["outer_footprint_y"]
            r["coordinates"].update({
                "x_start": x, "x_end": x + fp_x,
                "y_start": y, "y_end": y + fp_y,
            })
    ok = True
except Exception as exc:
    st.error(f"Geometry error — {exc}")
    ok = False

if ok:
    results_json = json.dumps(results)

    # ── Metrics ───────────────────────────────────────────────────────────
    total_fp = sum(r["geometry"]["outer_footprint_x"] * r["geometry"]["outer_footprint_y"] for r in results)
    total_vw = sum(r["geometry"]["v_water"]            for r in results)
    total_ve = sum(r["geometry"]["v_total_excavation"] for r in results)
    total_vc = sum(r["geometry"].get("v_concrete") or 0.0 for r in results)

    def _metric_card(label: str, value: str) -> str:
        return (
            f'<div style="background:linear-gradient(140deg,#0d1a35,#1a2e55);'
            f'border:1px solid #2a3f6e;border-radius:10px;padding:10px 20px;">'
            f'<div style="font-size:0.68rem;color:#a8c8e8;text-transform:uppercase;'
            f'letter-spacing:0.10em;font-weight:700;">{label}</div>'
            f'<div style="font-size:2.1rem;font-weight:900;color:#deeeff;'
            f'letter-spacing:-0.02em;line-height:1.2;">{value}</div>'
            f'</div>'
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_metric_card("Total Footprint Area",    f"{total_fp:,.1f} m²"), unsafe_allow_html=True)
    c2.markdown(_metric_card("Total Process Capacity",  f"{total_vw:,.1f} m³"), unsafe_allow_html=True)
    c3.markdown(_metric_card("Total Excavation Volume", f"{total_ve:,.1f} m³"), unsafe_allow_html=True)
    c4.markdown(_metric_card("Total Concrete Volume",   f"{total_vc:,.1f} m³"), unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.markdown("<div style='margin-top:3rem;'></div>", unsafe_allow_html=True)
        fig2d = make_2d_blueprint(results)
        fig2d.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=450)
        st.plotly_chart(fig2d, width="stretch")

    with right:
        st.markdown("<div style='margin-top:3rem;'></div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:1rem;font-weight:700;margin:0 0 0.5rem 0;'>3D view — select structure</p>", unsafe_allow_html=True)
        sel_id = st.selectbox("", options=[r["id"] for r in results], key="sel_3d",
                              label_visibility="collapsed")
        sel = next(r for r in results if r["id"] == sel_id)
        fig3d = make_3d_box(sel)
        fig3d.update_layout(
            title=dict(
                text=f"<b>3D View — {sel['id']}: {sel['name']}</b>",
                font=dict(size=16),
            ),
            margin=dict(l=10, r=10, t=30, b=10),
            height=420,
        )
        st.plotly_chart(fig3d, width="stretch")

    # ── Downloads ─────────────────────────────────────────────────────────
    proc_bytes = st.session_state.get("_proc_upload_bytes")
    d1, d2, d3, _ = st.columns([1, 1, 1, 3])
    with d1:
        st.download_button("⬇ Export Excel", data=_excel_bytes(results_json),
                           file_name="basin_summary.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           width="stretch")
    with d2:
        st.download_button("⬇ Export DXF", data=_dxf_bytes(results_json),
                           file_name="site_plan.dxf", mime="application/octet-stream",
                           width="stretch")
    if proc_bytes:
        with d3:
            fname = st.session_state.get("_proc_upload_name", "process_results.xlsx")
            st.download_button(
                "⬇ Export to Process Excel",
                data=write_results_sheet(proc_bytes, results),
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
