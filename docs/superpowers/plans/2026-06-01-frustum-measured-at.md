# Frustum "Measured at" (Bottom/Top) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each frustum declare whether its entered Length/Width is the bottom (small floor) or the top (large opening), deriving the other dimension from slope and height.

**Architecture:** All derivation/validation math lives in the pure `geometry.py` module (a new `_resolve_frustum_dims` resolver plus a `frustum_basis_error` validator). The grid round-trip helpers move out of `app.py` (which can't be imported under test because it runs Streamlit at module load) into a new pure `basin_table.py` module that adds a "Measured at" column. `app.py` gains the new column config, a per-row validation pass, and read-only derived-dimension columns.

**Tech Stack:** Python 3.14, Streamlit 1.57, pandas, pytest 9. Tests run from the repo root with `python -m pytest` (cwd on `sys.path`, so `import geometry` / `import basin_table` resolve).

**Spec:** `docs/superpowers/specs/2026-06-01-frustum-measured-at-design.md`

**Note on a spec refinement:** the spec described deriving the bottom inside `_from_df`. This plan instead derives at compute time inside `geometry.py` (it already has a top-override path and is the tested module), and `_from_df` only stores the entered values + `dimension_basis`. Behavior and UX are identical; the math is centralized and unit-tested.

---

## File Structure

- **`geometry.py`** (modify) — add `_resolve_frustum_dims(dims)` and `frustum_basis_error(dims)`; refactor `_compute_frustum` to use the resolver. Pure math, no UI.
- **`basin_table.py`** (create) — pure DataFrame round-trip moved out of `app.py`: `_f`, `_parse_slope_str`, `_to_df`, `_from_df`, `_DEFAULT_STRUCTURE`, with the new "Measured at" column and `dimension_basis` handling. No Streamlit import.
- **`app.py`** (modify) — import the round-trip from `basin_table`; add the "Measured at" SelectboxColumn; add a per-row validation pass; add read-only Bottom/Top L×W columns to the results table.
- **`tests/test_geometry_basis.py`** (create) — resolver + validator + compute tests.
- **`tests/test_basin_table.py`** (create) — round-trip mapping tests.

---

## Task 1: Geometry resolver + refactor `_compute_frustum`

**Files:**
- Modify: `geometry.py` (add resolver after `_resolve_slopes` at line 36; rewrite `_compute_frustum` at lines 48-96)
- Test: `tests/test_geometry_basis.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_geometry_basis.py`:

```python
import math
import geometry


def _base_frustum(**over):
    dims = {
        "length_bottom": 20.0, "width_bottom": 10.0,
        "total_height": 5.0, "water_depth": 4.2,
        "slope_uniform": 1.0, "uneven_slopes_enabled": False,
        "underdrain_height": 0.0,
    }
    dims.update(over)
    return dims


def test_bottom_basis_projects_top():
    # default (no dimension_basis) behaves as bottom basis
    g = geometry._compute_frustum(_base_frustum())
    assert math.isclose(g["l_bottom"], 20.0)
    assert math.isclose(g["w_bottom"], 10.0)
    # l_top = 20 + 5*(1+1) = 30 ; w_top = 10 + 5*(1+1) = 20
    assert math.isclose(g["l_top"], 30.0)
    assert math.isclose(g["w_top"], 20.0)


def test_top_basis_derives_bottom_uniform():
    dims = _base_frustum(dimension_basis="top", length_top=30.0, width_top=20.0)
    # remove bottom keys to prove they are not required when basis=top
    dims.pop("length_bottom"); dims.pop("width_bottom")
    g = geometry._compute_frustum(dims)
    # l_bot = 30 - 5*(1+1) = 20 ; w_bot = 20 - 5*(1+1) = 10
    assert math.isclose(g["l_bottom"], 20.0)
    assert math.isclose(g["w_bottom"], 10.0)
    assert math.isclose(g["l_top"], 30.0)
    assert math.isclose(g["w_top"], 20.0)


def test_top_basis_matches_equivalent_bottom_volume():
    bottom = geometry._compute_frustum(_base_frustum())
    top = _base_frustum(dimension_basis="top", length_top=30.0, width_top=20.0)
    top.pop("length_bottom"); top.pop("width_bottom")
    assert math.isclose(geometry._compute_frustum(top)["v_water"],
                        bottom["v_water"], rel_tol=1e-9)


def test_top_basis_uneven_slopes():
    dims = _base_frustum(
        dimension_basis="top", length_top=30.0, width_top=17.5,
        uneven_slopes_enabled=True,
        slope_north=0.0, slope_south=1.5, slope_east=1.0, slope_west=1.0,
        slope_uniform=None,
    )
    dims.pop("length_bottom"); dims.pop("width_bottom")
    g = geometry._compute_frustum(dims)
    # l_bot = 30 - 5*(s_w+s_e)=30-5*2=20 ; w_bot = 17.5 - 5*(s_s+s_n)=17.5-7.5=10
    assert math.isclose(g["l_bottom"], 20.0)
    assert math.isclose(g["w_bottom"], 10.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_geometry_basis.py -v`
Expected: FAIL — `test_top_basis_*` raise `KeyError: 'length_bottom'` (current `_compute_frustum` reads `dims['length_bottom']` directly).

- [ ] **Step 3: Add the resolver in `geometry.py`**

Insert after `_resolve_slopes` (after line 36, before the `# Volume Formulae` section):

```python
def _resolve_frustum_dims(dims: dict) -> tuple:
    """Return (l_bot, w_bot, l_top, w_top) honoring dimension_basis.

    basis 'bottom' (default): entered length_bottom/width_bottom; top projected
    by slope (or an explicit length_top/width_top override if both present).
    basis 'top': entered length_top/width_top; bottom derived by subtracting the
    slope projection.
    """
    h = parse_dim(dims['total_height'])
    s_n, s_s, s_e, s_w = _resolve_slopes(dims)
    basis = dims.get('dimension_basis', 'bottom')

    if basis == 'top':
        l_top = parse_dim(dims['length_top'])
        w_top = parse_dim(dims['width_top'])
        l_bot = l_top - h * (s_w + s_e)
        w_bot = w_top - h * (s_s + s_n)
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
```

- [ ] **Step 4: Refactor `_compute_frustum` to use the resolver**

Replace the body of `_compute_frustum` (lines 48-96) with:

```python
def _compute_frustum(dims: dict) -> dict:
    h     = parse_dim(dims['total_height'])
    d     = parse_dim(dims['water_depth'])
    ud    = min(parse_dim(dims.get('underdrain_height') or 0.0), d)

    s_n, s_s, s_e, s_w = _resolve_slopes(dims)
    l_bot, w_bot, l_top, w_top = _resolve_frustum_dims(dims)

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
```

- [ ] **Step 5: Run the new tests + the existing regression**

Run: `python -m pytest tests/test_geometry_basis.py -v`
Expected: PASS (4 tests).

Run: `python run_tests.py`
Expected: prints the verification report ending in `Result: ALL PASS` (bottom-basis behavior unchanged).

- [ ] **Step 6: Commit**

```bash
git add geometry.py tests/test_geometry_basis.py
git commit -m "Add frustum dimension_basis resolver in geometry"
```

---

## Task 2: Per-row validation function `frustum_basis_error`

**Files:**
- Modify: `geometry.py` (add `frustum_basis_error` after `_resolve_frustum_dims`)
- Test: `tests/test_geometry_basis.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_geometry_basis.py`:

```python
def test_basis_error_none_for_bottom_basis():
    assert geometry.frustum_basis_error(_base_frustum()) is None


def test_basis_error_none_for_valid_top():
    dims = _base_frustum(dimension_basis="top", length_top=30.0, width_top=20.0)
    assert geometry.frustum_basis_error(dims) is None


def test_basis_error_flags_nonpositive_derived_bottom():
    # top too small: l_bot = 8 - 5*(1+1) = -2  -> error
    dims = _base_frustum(dimension_basis="top", length_top=8.0, width_top=20.0)
    msg = geometry.frustum_basis_error(dims)
    assert msg is not None
    assert "derived bottom" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_geometry_basis.py -k basis_error -v`
Expected: FAIL — `AttributeError: module 'geometry' has no attribute 'frustum_basis_error'`.

- [ ] **Step 3: Implement `frustum_basis_error`**

Add directly after `_resolve_frustum_dims` in `geometry.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_geometry_basis.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add geometry.py tests/test_geometry_basis.py
git commit -m "Add frustum top-basis validation helper"
```

---

## Task 3: Extract round-trip into `basin_table.py` (no behavior change)

This moves the pure helpers out of `app.py` verbatim so they become importable/testable. The "Measured at" column is added in Task 4.

**Files:**
- Create: `basin_table.py`
- Modify: `app.py` (remove the moved helpers; import them)

- [ ] **Step 1: Create `basin_table.py`**

Create `basin_table.py` with the helpers exactly as they currently exist in `app.py` (the `_f` at lines 73-78, `_to_df` at 81-133, `_parse_slope_str` at 136-141, `_from_df` at 144-203, `_DEFAULT_STRUCTURE` at 206-216), with `dimension_basis` added to the default:

```python
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
    """Parse slope field: '1.5' -> uniform, '0;1.5;1.0;1.0' -> (N,S,E,W)."""
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
```

- [ ] **Step 2: Update `app.py` imports and remove the moved code**

In `app.py`, delete the now-moved definitions: `_f` (lines 73-78), `_to_df` (81-133), `_parse_slope_str` (136-141), `_from_df` (144-203), and `_DEFAULT_STRUCTURE` (206-216). Keep `import copy`, `import json`, etc. Add this import near the other local imports (after `from geometry import ...`):

```python
from basin_table import _DEFAULT_STRUCTURE, _from_df, _to_df
```

(`_f` and `_parse_slope_str` are only used by the moved functions, so they do not need importing into `app.py`.)

- [ ] **Step 3: Verify the app still imports and the script still runs**

Run: `python -c "import ast; ast.parse(open('app.py').read()); ast.parse(open('basin_table.py').read()); print('PARSE_OK')"`
Expected: `PARSE_OK`

Run: `python -c "import basin_table, geometry; df = basin_table._to_df([{'id':'S01','name':'A','type':'frustum','dimensions':{'length_bottom':10,'width_bottom':5,'total_height':3,'water_depth':2,'slope_uniform':1.0,'uneven_slopes_enabled':False,'underdrain_height':0.0}}]); print(list(df.columns)); print('OK')"`
Expected: prints the column list and `OK`.

Run: `python run_tests.py`
Expected: `Result: ALL PASS`.

- [ ] **Step 4: Commit**

```bash
git add basin_table.py app.py
git commit -m "Extract pure grid round-trip into basin_table module"
```

---

## Task 4: Add "Measured at" column to the round-trip

**Files:**
- Modify: `basin_table.py` (`_to_df`, `_from_df`)
- Test: `tests/test_basin_table.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_basin_table.py`:

```python
import basin_table


def _struct(dims, sid="S01", name="A"):
    return {"id": sid, "name": name, "type": "frustum", "dimensions": dims}


def test_to_df_bottom_basis_shows_bottom_and_measured():
    s = _struct({"length_bottom": 20.0, "width_bottom": 10.0,
                 "total_height": 5.0, "water_depth": 4.0,
                 "slope_uniform": 1.0, "uneven_slopes_enabled": False,
                 "dimension_basis": "bottom"})
    row = basin_table._to_df([s]).iloc[0]
    assert row["Measured at"] == "Bottom"
    assert row["Length / Diam (int.)"] == "20.0"
    assert row["Width"] == "10.0"


def test_to_df_top_basis_shows_top():
    s = _struct({"length_top": 30.0, "width_top": 20.0,
                 "total_height": 5.0, "water_depth": 4.0,
                 "slope_uniform": 1.0, "uneven_slopes_enabled": False,
                 "dimension_basis": "top"})
    row = basin_table._to_df([s]).iloc[0]
    assert row["Measured at"] == "Top"
    assert row["Length / Diam (int.)"] == "30.0"
    assert row["Width"] == "20.0"


def test_to_df_measured_blank_for_non_frustum():
    s = {"id": "S02", "name": "R", "type": "rectangular",
         "dimensions": {"length_internal": 10.0, "width_internal": 5.0,
                        "total_height": 3.0, "water_depth": 2.0,
                        "wall_thickness": 0.3}}
    row = basin_table._to_df([s]).iloc[0]
    assert row["Measured at"] is None


def test_from_df_top_basis_maps_keys_and_clears_bottom():
    s = _struct({"length_top": 30.0, "width_top": 20.0,
                 "total_height": 5.0, "water_depth": 4.0,
                 "slope_uniform": 1.0, "uneven_slopes_enabled": False,
                 "dimension_basis": "top"})
    df = basin_table._to_df([s])
    out = basin_table._from_df(df, [s])[0]["dimensions"]
    assert out["dimension_basis"] == "top"
    assert out["length_top"] == "30.0"
    assert out["width_top"] == "20.0"
    assert out["length_bottom"] is None
    assert out["width_bottom"] is None


def test_from_df_bottom_basis_clears_top():
    s = _struct({"length_bottom": 20.0, "width_bottom": 10.0,
                 "total_height": 5.0, "water_depth": 4.0,
                 "slope_uniform": 1.0, "uneven_slopes_enabled": False,
                 "dimension_basis": "bottom"})
    df = basin_table._to_df([s])
    out = basin_table._from_df(df, [s])[0]["dimensions"]
    assert out["dimension_basis"] == "bottom"
    assert out["length_bottom"] == "20.0"
    assert out["length_top"] is None
    assert out["width_top"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_basin_table.py -v`
Expected: FAIL — `KeyError: 'Measured at'` (column not emitted yet).

- [ ] **Step 3: Update `_to_df` to emit basis-aware dims + "Measured at"**

In `basin_table.py`, replace the frustum branch of the dimension block (the `if t == "frustum":` arm that sets `length`/`width`/`wall`) and add a `measured` variable. Replace this block:

```python
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
```

with:

```python
        measured = None
        if t == "frustum":
            if d.get("dimension_basis", "bottom") == "top":
                length = str(d.get("length_top", ""))
                width  = str(d.get("width_top",  ""))
                measured = "Top"
            else:
                length = str(d.get("length_bottom", ""))
                width  = str(d.get("width_bottom",  ""))
                measured = "Bottom"
            wall   = 0.0
        elif t == "rectangular":
            length = str(d.get("length_internal", ""))
            width  = str(d.get("width_internal",  ""))
            wall   = _f(d.get("wall_thickness"))
        else:  # circular
            length = str(d.get("diameter_internal", ""))
            width  = ""
            wall   = _f(d.get("wall_thickness"))
```

Then add `"Measured at"` to the `row` dict (immediately after the `"Width"` entry):

```python
            "Width":            width,
            "Measured at":      measured,
```

- [ ] **Step 4: Update `_from_df` to read "Measured at"**

In `basin_table.py`, replace the first two lines of the frustum arm:

```python
        if df_type in ("frustum", "uneven frustum"):
            d["length_bottom"]    = str(row["Length / Diam (int.)"])
            d["width_bottom"]     = str(row["Width"])
            d["total_height"]     = h
```

with:

```python
        if df_type in ("frustum", "uneven frustum"):
            measured = str(row.get("Measured at") or "Bottom").strip().lower()
            if measured == "top":
                d["dimension_basis"] = "top"
                d["length_top"]    = str(row["Length / Diam (int.)"])
                d["width_top"]     = str(row["Width"])
                d["length_bottom"] = None
                d["width_bottom"]  = None
            else:
                d["dimension_basis"] = "bottom"
                d["length_bottom"] = str(row["Length / Diam (int.)"])
                d["width_bottom"]  = str(row["Width"])
                d["length_top"]    = None
                d["width_top"]     = None
            d["total_height"]     = h
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_basin_table.py -v`
Expected: PASS (5 tests).

Run: `python -m pytest -q`
Expected: all tests pass (geometry + basin_table).

- [ ] **Step 6: Commit**

```bash
git add basin_table.py tests/test_basin_table.py
git commit -m "Add Measured at column to grid round-trip"
```

---

## Task 5: Wire UI — column config, validation pass, derived columns

**Files:**
- Modify: `app.py` (data_editor `column_config`; import `frustum_basis_error`; validation pass; results table)

- [ ] **Step 1: Import the validator**

In `app.py`, change the geometry import line:

```python
from geometry import compute_layout_coordinates
```

to:

```python
from geometry import compute_layout_coordinates, frustum_basis_error
```

- [ ] **Step 2: Add the "Measured at" SelectboxColumn**

In the `st.data_editor(...)` `column_config={...}` dict, add this entry immediately after the `"Type": st.column_config.SelectboxColumn(...)` entry:

```python
        "Measured at": st.column_config.SelectboxColumn(
            options=["Bottom", "Top"],
            required=False,
            help="Frustum only. Bottom = entered L/W is the small floor (top "
                 "derived from slope). Top = entered L/W is the large opening "
                 "(bottom derived). Ignored for rectangular/circular.",
        ),
```

- [ ] **Step 3: Add the per-row validation pass**

In the `try:` block of the "Recompute geometry" section, replace:

```python
    structures = _from_df(edited_df, st.session_state.structures)
    if not structures:
        st.info("Add at least one structure to see results.")
        st.stop()
    results = compute_layout_coordinates({**BASE, "structures": structures})
```

with:

```python
    structures = _from_df(edited_df, st.session_state.structures)
    if not structures:
        st.info("Add at least one structure to see results.")
        st.stop()
    basis_errors = [
        f"{s['id']} “{s['name']}”: {msg}"
        for s in structures
        if s["type"] == "frustum"
        and (msg := frustum_basis_error(s["dimensions"]))
    ]
    if basis_errors:
        st.error("Cannot compute geometry:\n\n" + "\n\n".join(basis_errors))
        st.stop()
    results = compute_layout_coordinates({**BASE, "structures": structures})
```

- [ ] **Step 4: Add derived Bottom/Top L×W columns to the read-only results table**

In `app.py`, replace the read-only volume table block:

```python
    vol_df = pd.DataFrame(
        [{"ID": r["id"], "Name": r["name"],
          "V_process (m³)": round(r["geometry"]["v_process"], 2)} for r in results]
    )
    st.dataframe(
        vol_df, hide_index=True, width="stretch",
        column_config={"V_process (m³)": st.column_config.NumberColumn(format="%.1f")},
    )
```

with:

```python
    def _frustum_dims_label(r: dict) -> tuple:
        g = r["geometry"]
        if r["type"] == "frustum":
            return (f"{g['l_bottom']:.2f} × {g['w_bottom']:.2f}",
                    f"{g['l_top']:.2f} × {g['w_top']:.2f}")
        return "", ""

    vol_rows = []
    for r in results:
        bot_lbl, top_lbl = _frustum_dims_label(r)
        vol_rows.append({
            "ID": r["id"], "Name": r["name"],
            "Bottom L×W (m)": bot_lbl,
            "Top L×W (m)": top_lbl,
            "V_process (m³)": round(r["geometry"]["v_process"], 2),
        })
    vol_df = pd.DataFrame(vol_rows)
    st.dataframe(
        vol_df, hide_index=True, width="stretch",
        column_config={"V_process (m³)": st.column_config.NumberColumn(format="%.1f")},
    )
```

- [ ] **Step 5: Verify app parses and round-trip integrates**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('PARSE_OK')"`
Expected: `PARSE_OK`

Run: `python -c "import basin_table, geometry; s={'id':'S01','name':'A','type':'frustum','dimensions':{'length_top':30.0,'width_top':20.0,'total_height':5.0,'water_depth':4.0,'slope_uniform':1.0,'uneven_slopes_enabled':False,'underdrain_height':0.0,'dimension_basis':'top'}}; df=basin_table._to_df([s]); st=basin_table._from_df(df,[s]); print(geometry.frustum_basis_error(st[0]['dimensions'])); print(geometry._compute_frustum(st[0]['dimensions'])['l_bottom'])"`
Expected: prints `None` then `20.0`.

- [ ] **Step 6: Manual smoke test in the app**

Run: `streamlit run app.py --server.port 8502` (or `run.bat`). Verify:
1. Editing a cell sticks (no reset regression).
2. A frustum row's "Measured at" can be switched to Top; the read-only table below shows the derived Bottom L×W shrinking as expected.
3. Setting a Top with a too-small value (e.g. Length 8, slope 1, height 5) shows the per-row error and no results until fixed.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "Wire Measured at column, validation, and derived dims into UI"
```

---

## Self-Review

**Spec coverage:**
- Data model `dimension_basis` (default bottom, derive bottom when top) → Task 1 (resolver), Task 4 (round-trip stores it). ✓
- Geometry unchanged math / reuse top-override path → Task 1 refactor keeps formulas, `run_tests.py` regression. ✓
- UI "Measured at" SelectboxColumn, frustum-only, blank for others → Task 4 (`_to_df` blank for non-frustum), Task 5 (column config). ✓
- Editor stays byte-stable (no data_editor reset) → "Measured at" is user data, not recomputed; Task 5 Step 6 manual check. ✓
- Derived dim shown read-only below, not in editor → Task 5 Step 4. ✓
- Round-trip `_to_df`/`_from_df` basis mapping → Task 4. ✓
- Per-row validation error when derived bottom ≤ 0 → Task 2 (helper), Task 5 Step 3 (UI pass). ✓
- Backward compat (missing `dimension_basis` ⇒ bottom) → Task 1 `test_bottom_basis_projects_top` uses no basis key; `run_tests.py` on existing `state.json`. ✓

**Placeholder scan:** none — every code step shows complete code; every run step shows the command and expected output.

**Type/name consistency:** `dimension_basis` ("bottom"/"top"), `_resolve_frustum_dims` returns `(l_bot, w_bot, l_top, w_top)`, geometry keys `l_bottom`/`w_bottom`/`l_top`/`w_top`, `frustum_basis_error(dims) -> str | None`, column label `"Measured at"`, and round-trip key clearing (`length_top`/`width_top`/`length_bottom`/`width_bottom`) are used identically across Tasks 1–5. ✓
