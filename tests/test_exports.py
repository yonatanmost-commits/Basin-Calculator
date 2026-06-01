import exports


def test_raw_dim_string_bottom_basis_frustum_no_none():
    dims = {"length_bottom": "20.0", "width_bottom": "10.0", "total_height": 5.0,
            "slope_uniform": 1.0, "uneven_slopes_enabled": False,
            "dimension_basis": "bottom", "length_top": None, "width_top": None}
    s = exports._raw_dim_string(dims, "frustum")
    assert "None" not in s
    assert "20.0" in s and "10.0" in s


def test_raw_dim_string_top_basis_frustum_shows_top_not_none():
    dims = {"length_bottom": None, "width_bottom": None, "total_height": 5.0,
            "slope_uniform": 1.0, "uneven_slopes_enabled": False,
            "dimension_basis": "top", "length_top": "30.0", "width_top": "20.0"}
    s = exports._raw_dim_string(dims, "frustum")
    assert "None" not in s
    assert "30.0" in s and "20.0" in s
