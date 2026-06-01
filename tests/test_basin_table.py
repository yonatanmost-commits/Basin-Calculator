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
