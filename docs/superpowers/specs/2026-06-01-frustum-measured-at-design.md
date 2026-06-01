# Frustum "Measured at" (Bottom/Top) input — design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan

## Problem

For a frustum, the grid's Length/Width inputs are always the **bottom** (small floor)
dimensions; the **top** (large opening) is derived from slope and height. Users want to
enter *either* the bottom or the top dimension and have the other auto-fill from the
slope, since field/process data sometimes specifies the top opening instead.

## Goal

Let each frustum independently declare whether its entered Length/Width refers to the
**bottom** or the **top**. The complementary dimension is computed from slope + height and
shown read-only.

Non-goals (YAGNI): mixing per-side top overrides, entering top *and* bottom at the same
time, applying this to rectangular/circular types.

## Geometry recap (`geometry.py`, unchanged math)

Current frustum top projection (`geometry.py:62-63`):

```
l_top = l_bot + h*(s_west + s_east)
w_top = w_bot + h*(s_south + s_north)
```

`_compute_frustum` already supports an explicit top override (`geometry.py:58-64`): when
`length_top` and `width_top` are both present it uses them directly, while `a_bot` still
comes from `length_bottom`/`width_bottom`. We exploit this — no formula changes are needed.
We only populate `length_bottom`/`width_bottom` and `length_top`/`width_top` consistently
in the app's round-trip.

## Data model

Add to frustum `dimensions`:

- `dimension_basis`: `"bottom"` (default) | `"top"`.

Behavior:

- `basis == "bottom"` (default; backward-compatible): entered L/W → `length_bottom` /
  `width_bottom`; `length_top` / `width_top` cleared to `None` (slope-projected as today).
- `basis == "top"`: entered L/W → `length_top` / `width_top`; derive and store:
  - `length_bottom = length_top − h*(s_west + s_east)`
  - `width_bottom  = width_top  − h*(s_south + s_north)`

Slopes come from the same row (uniform or uneven, already parsed by `_parse_slope_str`).
Existing `state.json` / process-Excel loads have no `dimension_basis` key → treated as
`"bottom"` → identical to current behavior.

## UI (`app.py` data editor)

- New `SelectboxColumn` **"Measured at"**, options `["Bottom", "Top"]`, default `"Bottom"`.
- Meaningful only for `frustum` / `uneven frustum` rows. For `rectangular` / `circular`
  rows the value is blank/`None` and ignored on round-trip.
- The existing "Length / Diam (int.)" and "Width" columns display whichever basis the row
  is set to.
- "Measured at" stores a **user-set** value (not recomputed each run), so it does **not**
  reintroduce the `data_editor`-identity bug documented in
  `memory/streamlit-data-editor-identity.md`. The editor input stays byte-stable across
  plain edits.

## Derived-dimension display

The auto-filled complementary dimension is shown **read-only** in the results table below
the metrics (the same table that shows `V_process`), **never** inside the editor (a
recomputed column in the keyed editor would discard in-progress edits — see the memory
note above). Add `Bottom L×W` and `Top L×W` columns to that read-only `st.dataframe`.

## Round-trip (`_to_df` / `_from_df`)

- `_to_df` (frustum rows): emit L/W from the stored basis
  (`length_top`/`width_top` when `dimension_basis == "top"`, else
  `length_bottom`/`width_bottom`) and set "Measured at" to `"Top"`/`"Bottom"`.
- `_from_df`: read "Measured at".
  - `"top"`: store `length_top`/`width_top` from entered values; compute and store derived
    `length_bottom`/`width_bottom`; set `dimension_basis = "top"`.
  - `"bottom"` (or blank): store `length_bottom`/`width_bottom`; set `length_top` /
    `width_top` to `None`; set `dimension_basis = "bottom"`.

## Validation (per-row error)

After `_from_df`, before `compute_layout_coordinates`, run a validation pass over
structures. For each `top`-basis frustum, if derived `length_bottom <= 0` or
`width_bottom <= 0`, collect the row's `id` and `name`. If any fail, render a single
`st.error` listing the offending structures, e.g.:

> S02 "Clarifier": top dimensions too small for slope × height — derived bottom ≤ 0.

and stop before rendering results (consistent with the existing geometry-error handling
that wraps the compute in try/except and shows `st.error`).

## Testing

- `geometry.py` math is unchanged; existing tests stay green.
- Round-trip unit check: a `top`-basis frustum with known L/W/slope/height derives the
  expected bottom; a `bottom`-basis frustum is unchanged from current output.
- Validation: top-basis frustum with `top − h*(s_left+s_right) <= 0` is flagged.
- Backward-compat: dimensions lacking `dimension_basis` behave as `"bottom"`.
- Manual: editing in the grid still sticks (no data_editor reset regression).
