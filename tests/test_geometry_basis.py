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
    assert math.isclose(g["l_top"], 30.0)
    assert math.isclose(g["w_top"], 17.5)
