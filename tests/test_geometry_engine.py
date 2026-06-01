"""End-to-end geometry-engine checks against the hand-calculated values in
state.json. Ported from the former run_tests.py script so the rectangular /
circular volume formulas, the uneven-frustum case, the layout coordinator
(x/y placement with corridor spacing) and comma-separated measurement averaging
stay covered by the pytest suite.

Hand calculations (see also the comments in git history of run_tests.py):

  B01  frustum, uniform slope s=1.0
    l_bot = avg(20.0, 19.8, 20.2) = 20.0 ; w_bot = 10
    l_top = 20 + 5*1 + 5*1 = 30 ; w_top = 10 + 5*1 + 5*1 = 20
    V_total = (5/3)*(200 + 600 + sqrt(120000)) = 1910.684
    l_water = 28.4, w_water = 18.4 -> V_water = 1.4 * 1045.841 = 1464.178

  B01-Alt  frustum, uneven s_N=0, s_S=1.5, s_E=1.0, s_W=1.0
    l_top = 30, w_top = 10 + 5*1.5 + 5*0 = 17.5
    V_total = (5/3)*(200 + 525 + sqrt(105000)) = 1748.395
    V_water = 1.4 * 967.195 = 1354.073

  B02  rectangular  l=25, w=avg(12.0,12.2)=12.1, tw=0.4, h=5, d=3.8
    V_water = 25*12.1*3.8 ; l_outer=25.8, w_outer=12.9, V_total=1664.1

  B03  circular  d_int=15, tw=0.4, h=6, d=5
    V_water = pi*7.5^2*5 ; d_outer=15.8, V_total = pi*7.9^2*6

  Layout: corridor 6.0 m between outer footprints, placed along X from 0.
"""

import math

import pytest

from geometry import load_and_run

TOL = 1e-2


@pytest.fixture(scope="module")
def by_id():
    return {r["id"]: r for r in load_and_run("state.json")}


def test_b01_frustum_uniform(by_id):
    g = by_id["B01"]["geometry"]
    c = by_id["B01"]["coordinates"]
    assert g["l_bottom"] == pytest.approx(20.0, abs=TOL)   # comma-avg of 20.0,19.8,20.2
    assert g["l_top"] == pytest.approx(30.0, abs=TOL)
    assert g["w_top"] == pytest.approx(20.0, abs=TOL)
    assert g["v_water"] == pytest.approx(1464.178, abs=TOL)
    assert g["v_total_excavation"] == pytest.approx(1910.684, abs=TOL)
    assert c["x_start"] == pytest.approx(0.0, abs=TOL)
    assert c["x_end"] == pytest.approx(30.0, abs=TOL)
    assert c["y_end"] == pytest.approx(20.0, abs=TOL)


def test_b01_alt_frustum_uneven(by_id):
    g = by_id["B01-Alt"]["geometry"]
    c = by_id["B01-Alt"]["coordinates"]
    assert g["l_top"] == pytest.approx(30.0, abs=TOL)
    assert g["w_top"] == pytest.approx(17.5, abs=TOL)       # uneven: N=0, S=1.5
    assert g["v_water"] == pytest.approx(1354.073, abs=TOL)
    assert g["v_total_excavation"] == pytest.approx(1748.395, abs=TOL)
    assert c["x_start"] == pytest.approx(36.0, abs=TOL)      # 30 + 6 corridor
    assert c["x_end"] == pytest.approx(66.0, abs=TOL)
    assert c["y_end"] == pytest.approx(17.5, abs=TOL)


def test_b02_rectangular(by_id):
    g = by_id["B02"]["geometry"]
    c = by_id["B02"]["coordinates"]
    assert g["w_internal"] == pytest.approx(12.1, abs=TOL)   # comma-avg of 12.0,12.2
    assert g["l_outer"] == pytest.approx(25.8, abs=TOL)
    assert g["w_outer"] == pytest.approx(12.9, abs=TOL)
    assert g["v_water"] == pytest.approx(25.0 * 12.1 * 3.8, abs=TOL)
    assert g["v_total_excavation"] == pytest.approx(1664.1, abs=TOL)
    assert g["v_concrete"] == pytest.approx((25.8 * 12.9 - 25.0 * 12.1) * 5.0, abs=TOL)
    assert c["x_start"] == pytest.approx(72.0, abs=TOL)      # 66 + 6 corridor
    assert c["x_end"] == pytest.approx(97.8, abs=TOL)
    assert c["y_end"] == pytest.approx(12.9, abs=TOL)


def test_b03_circular(by_id):
    g = by_id["B03"]["geometry"]
    c = by_id["B03"]["coordinates"]
    assert g["d_outer"] == pytest.approx(15.8, abs=TOL)
    assert g["v_water"] == pytest.approx(math.pi * 7.5 ** 2 * 5.0, abs=TOL)
    assert g["v_total_excavation"] == pytest.approx(math.pi * 7.9 ** 2 * 6.0, abs=TOL)
    assert g["v_concrete"] == pytest.approx(math.pi * (7.9 ** 2 - 7.5 ** 2) * 6.0, abs=TOL)
    assert c["x_start"] == pytest.approx(103.8, abs=TOL)     # 97.8 + 6 corridor
    assert c["x_end"] == pytest.approx(119.6, abs=TOL)
    assert c["y_end"] == pytest.approx(15.8, abs=TOL)
