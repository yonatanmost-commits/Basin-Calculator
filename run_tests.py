"""
run_tests.py — Temporary math verification script.
Checks computed volumes and layout coordinates against hand-calculated values.
"""

import math
import sys
from geometry import load_and_run

TOL = 1e-2   # 0.01 m³ / 0.01 m tolerance

# ---------------------------------------------------------------------------
# Hand-calculated expected values
# ---------------------------------------------------------------------------
#
# B01  Frustum / uniform slope s=1.0
#   l_bot = avg(20.0, 19.8, 20.2) = 20.0
#   l_top = 20 + 5*1 + 5*1 = 30.0   w_top = 10 + 5*1 + 5*1 = 20.0
#   A_bot=200, A_top=600
#   V_total = (5/3)*(200+600+sqrt(120000)) = (5/3)*1146.410 = 1910.684
#   l_water=28.4, w_water=18.4, A_water=522.56
#   V_water = (4.2/3)*(200+522.56+sqrt(104512)) = 1.4*1045.841 = 1464.178
#
# B01-Alt Frustum / uneven s_N=0, s_S=1.5, s_E=1.0, s_W=1.0
#   l_top = 20+5*1+5*1=30  w_top = 10+5*1.5+5*0=17.5
#   A_bot=200, A_top=525
#   V_total = (5/3)*(200+525+sqrt(105000)) = (5/3)*1049.037 = 1748.395
#   l_water=28.4, w_water=16.3, A_water=462.92
#   V_water = (4.2/3)*(200+462.92+sqrt(92584)) = 1.4*967.195 = 1354.073
#
# B02  Rectangular  l=25, w=avg(12.0,12.2)=12.1, tw=0.4, R=0.5
#   A_loss = (4-pi)*0.25 = 0.2146
#   V_water = (302.5-0.2146)*3.8 = 1148.685
#   l_outer=25.8, w_outer=12.9, V_total=25.8*12.9*5=1664.1
#
# B03  Circular  d_int=15, tw=0.4
#   V_water = pi*(7.5)^2*5   = 883.574
#   d_outer=15.8, V_total = pi*(7.9)^2*6 = 1176.400
# ---------------------------------------------------------------------------

EXPECTED = {
    'B01': {
        'l_top': 30.0, 'w_top': 20.0,
        'v_water': 1464.178,
        'v_total_excavation': 1910.684,
        'x_start': 0.0,  'x_end': 30.0,
        'y_start': 0.0,  'y_end': 20.0,
    },
    'B01-Alt': {
        'l_top': 30.0, 'w_top': 17.5,
        'v_water': 1354.073,
        'v_total_excavation': 1748.395,
        'x_start': 36.0, 'x_end': 66.0,
        'y_start': 0.0,  'y_end': 17.5,
    },
    'B02': {
        'l_outer': 25.8, 'w_outer': 12.9,
        'a_loss': (4 - math.pi) * 0.25,
        'v_water': 1148.685,
        'v_total_excavation': 1664.1,
        'x_start': 72.0, 'x_end': 97.8,
        'y_start': 0.0,  'y_end': 12.9,
    },
    'B03': {
        'd_outer': 15.8,
        'v_water': math.pi * 7.5**2 * 5.0,
        'v_total_excavation': math.pi * 7.9**2 * 6.0,
        'x_start': 103.8, 'x_end': 119.6,
        'y_start': 0.0,   'y_end': 15.8,
    },
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def chk(label, actual, expected, tol=TOL):
    ok  = abs(actual - expected) <= tol
    sym = "PASS" if ok else "FAIL"
    return sym, actual, expected, ok


results = load_and_run('state.json')
by_id   = {r['id']: r for r in results}

all_pass = True
rows = []

def add(struct_id, field, actual, expected):
    global all_pass
    sym, a, e, ok = chk(field, actual, expected)
    if not ok:
        all_pass = False
    rows.append((struct_id, field, a, e, sym))

# B01 checks
g = by_id['B01']['geometry']
c = by_id['B01']['coordinates']
add('B01', 'l_bot (avg)              ', g['l_bottom'],            20.0)
add('B01', 'l_top                    ', g['l_top'],               EXPECTED['B01']['l_top'])
add('B01', 'w_top                    ', g['w_top'],               EXPECTED['B01']['w_top'])
add('B01', 'V_water (m³)             ', g['v_water'],             EXPECTED['B01']['v_water'])
add('B01', 'V_total_excav (m³)       ', g['v_total_excavation'],  EXPECTED['B01']['v_total_excavation'])
add('B01', 'X_start (m)              ', c['x_start'],             EXPECTED['B01']['x_start'])
add('B01', 'X_end (m)                ', c['x_end'],               EXPECTED['B01']['x_end'])
add('B01', 'Y_end (m)                ', c['y_end'],               EXPECTED['B01']['y_end'])

# B01-Alt checks
g = by_id['B01-Alt']['geometry']
c = by_id['B01-Alt']['coordinates']
add('B01-Alt', 'l_top                    ', g['l_top'],               EXPECTED['B01-Alt']['l_top'])
add('B01-Alt', 'w_top (uneven N=0,S=1.5) ', g['w_top'],               EXPECTED['B01-Alt']['w_top'])
add('B01-Alt', 'V_water (m³)             ', g['v_water'],             EXPECTED['B01-Alt']['v_water'])
add('B01-Alt', 'V_total_excav (m³)       ', g['v_total_excavation'],  EXPECTED['B01-Alt']['v_total_excavation'])
add('B01-Alt', 'X_start (m)              ', c['x_start'],             EXPECTED['B01-Alt']['x_start'])
add('B01-Alt', 'X_end (m)                ', c['x_end'],               EXPECTED['B01-Alt']['x_end'])
add('B01-Alt', 'Y_end (m)                ', c['y_end'],               EXPECTED['B01-Alt']['y_end'])

# B02 checks
g = by_id['B02']['geometry']
c = by_id['B02']['coordinates']
add('B02', 'w_int (avg 12.0,12.2)    ', g['w_internal'],          12.1)
add('B02', 'A_loss fillet (m²)       ', g['a_loss'],              EXPECTED['B02']['a_loss'])
add('B02', 'l_outer (m)              ', g['l_outer'],             EXPECTED['B02']['l_outer'])
add('B02', 'w_outer (m)              ', g['w_outer'],             EXPECTED['B02']['w_outer'])
add('B02', 'V_water (m³)             ', g['v_water'],             EXPECTED['B02']['v_water'])
add('B02', 'V_total_excav (m³)       ', g['v_total_excavation'],  EXPECTED['B02']['v_total_excavation'])
add('B02', 'X_start (m)              ', c['x_start'],             EXPECTED['B02']['x_start'])
add('B02', 'X_end (m)                ', c['x_end'],               EXPECTED['B02']['x_end'])
add('B02', 'Y_end (m)                ', c['y_end'],               EXPECTED['B02']['y_end'])

# B03 checks
g = by_id['B03']['geometry']
c = by_id['B03']['coordinates']
add('B03', 'd_outer (m)              ', g['d_outer'],             EXPECTED['B03']['d_outer'])
add('B03', 'V_water (m³)             ', g['v_water'],             EXPECTED['B03']['v_water'])
add('B03', 'V_total_excav (m³)       ', g['v_total_excavation'],  EXPECTED['B03']['v_total_excavation'])
add('B03', 'X_start (m)              ', c['x_start'],             EXPECTED['B03']['x_start'])
add('B03', 'X_end (m)                ', c['x_end'],               EXPECTED['B03']['x_end'])
add('B03', 'Y_end (m)                ', c['y_end'],               EXPECTED['B03']['y_end'])

# ---------------------------------------------------------------------------
# Print tabular summary
# ---------------------------------------------------------------------------

W_ID  = 10
W_FLD = 30
W_NUM = 12

divider = '-' * (W_ID + W_FLD + W_NUM * 2 + 10)
header  = (f"{'ID':<{W_ID}} {'Field':<{W_FLD}} {'Computed':>{W_NUM}} "
           f"{'Expected':>{W_NUM}}  Status")

print()
print('=' * len(header))
print(' GEOMETRY ENGINE — VERIFICATION REPORT')
print('=' * len(header))
print(header)
print(divider)

prev_id = None
for (sid, field, actual, expected, sym) in rows:
    if sid != prev_id and prev_id is not None:
        print(divider)
    print(f"{sid:<{W_ID}} {field:<{W_FLD}} {actual:>{W_NUM}.4f} "
          f"{expected:>{W_NUM}.4f}  {sym}")
    prev_id = sid

print('=' * len(header))
overall = "ALL PASS" if all_pass else "FAILURES DETECTED"
print(f" Result: {overall}")
print('=' * len(header))
print()

sys.exit(0 if all_pass else 1)
