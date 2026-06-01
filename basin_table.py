"""basin_table.py — pure DataFrame round-trip between the structures list and the
Streamlit data-editor grid. No Streamlit imports so it can be unit-tested."""

import copy

import pandas as pd


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

        row = {
            "Del":              False,
            "ID":               s["id"],
            "Name":             s["name"],
            "Type":             df_type,
            "Length / Diam (int.)": length,
            "Width":            width,
            "Height (m)":       _f(d.get("total_height")),
            "Water Depth (m)":  _f(d.get("water_depth")),
            "Underdrain (m)":   _f(d.get("underdrain_height"), 0.0),
            "Wall Thick (m)":   wall,
            "Slope":            slope_str,
            "X (m)":            _f(s.get("x_pos"), 0.0),
            "Y (m)":            _f(s.get("y_pos"), 0.0),
        }
        rows.append(row)
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
            d["length_bottom"]    = str(row["Length / Diam (int.)"])
            d["width_bottom"]     = str(row["Width"])
            d["total_height"]     = h
            d["water_depth"]      = w
            d["underdrain_height"] = _f(row.get("Underdrain (m)"), 0.0)
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
            d["length_internal"]  = str(row["Length / Diam (int.)"])
            d["width_internal"]   = str(row["Width"])
            d["total_height"]     = h
            d["water_depth"]      = w
            d["underdrain_height"] = _f(row.get("Underdrain (m)"), 0.0)
            d["wall_thickness"]   = _f(row["Wall Thick (m)"])

        else:  # circular
            d["diameter_internal"]  = str(row["Length / Diam (int.)"])
            d["total_height"]       = h
            d["water_depth"]        = w
            d["underdrain_height"]  = _f(row.get("Underdrain (m)"), 0.0)
            d["wall_thickness"]     = _f(row["Wall Thick (m)"])

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
        "underdrain_height": 0.0, "wall_thickness": 0.0,
        "dimension_basis": "bottom",
    },
}
