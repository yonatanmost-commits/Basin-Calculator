"""
main.py — CLI harness for the basin calculation engine.

Commands:
  python main.py --process <state.json>
  python main.py --export-excel <state.json>
  python main.py --export-cad <state.json>
  python main.py --generate-charts <state.json>
"""

import argparse
import json
import sys
from geometry import load_and_run


def _load_state(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# --process: compute and print summary table
# ─────────────────────────────────────────────────────────────────────────────

def cmd_process(json_path: str):
    results = load_and_run(json_path)

    W_ID   = 8
    W_NAME = 30
    W_TYPE = 12
    W_FP   = 20
    W_VOL  = 14

    divider = '-' * (W_ID + W_NAME + W_TYPE + W_FP + W_VOL * 3 + 10)
    header  = (f"{'ID':<{W_ID}} {'Name':<{W_NAME}} {'Type':<{W_TYPE}} "
               f"{'Footprint':<{W_FP}} {'V_water (m3)':>{W_VOL}} "
               f"{'V_excav (m3)':>{W_VOL}} {'V_concrete (m3)':>{W_VOL}}")

    print()
    print('=' * len(header))
    print(' BASIN CALCULATION SUMMARY')
    print('=' * len(header))
    print(header)
    print(divider)

    total_vw = 0.0
    total_ve = 0.0
    total_vc = 0.0

    for r in results:
        g     = r['geometry']
        stype = r['type']

        if stype == 'circular':
            fp = f"D={g['d_outer']:.2f} m"
        else:
            fp = f"{g['outer_footprint_x']:.2f} x {g['outer_footprint_y']:.2f} m"

        vw = g['v_water']
        ve = g['v_total_excavation']
        vc = g.get('v_concrete')
        total_vw += vw
        total_ve += ve

        if vc is not None:
            total_vc += vc
            vc_str = f"{vc:>{W_VOL}.3f}"
        else:
            vc_str = f"{'n/a':>{W_VOL}}"

        print(f"{r['id']:<{W_ID}} {r['name']:<{W_NAME}} {stype:<{W_TYPE}} "
              f"{fp:<{W_FP}} {vw:>{W_VOL}.3f} {ve:>{W_VOL}.3f} {vc_str}")

    print(divider)
    print(f"{'TOTAL':<{W_ID}} {'':<{W_NAME}} {'':<{W_TYPE}} {'':<{W_FP}} "
          f"{total_vw:>{W_VOL}.3f} {total_ve:>{W_VOL}.3f} {total_vc:>{W_VOL}.3f}")
    print('=' * len(header))

    # Coordinate layout
    print()
    print('  LAYOUT COORDINATES')
    print(f"  {'ID':<8} {'X_start':>10} {'X_end':>10} {'Y_end':>10}")
    print(f"  {'-'*42}")
    for r in results:
        c = r['coordinates']
        print(f"  {r['id']:<8} {c['x_start']:>9.2f} m {c['x_end']:>9.2f} m "
              f"{c['y_end']:>9.2f} m")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# --export-excel
# ─────────────────────────────────────────────────────────────────────────────

def cmd_export_excel(json_path: str):
    import gc, io, sys
    from exports import export_excel
    state   = _load_state(json_path)
    results = load_and_run(json_path)
    template = state['global_settings']['excel_template_path']
    dest = export_excel(results, template)
    # Force GC now so openpyxl's ZipFile finalizer runs before we return.
    # Stderr is swapped briefly to suppress the known Python 3.14 ZipFile.__del__
    # false-positive (file is already saved and closed successfully).
    _old_err = sys.stderr
    sys.stderr = io.StringIO()
    try:
        gc.collect()
    finally:
        _captured = sys.stderr.getvalue()
        sys.stderr = _old_err
        # Re-raise anything that isn't the known ZipFile finalizer noise
        real_errors = [l for l in _captured.splitlines()
                       if l and 'ZipFile.__del__' not in l
                       and 'I/O operation on closed file' not in l
                       and 'Exception ignored' not in l
                       and 'zipfile' not in l
                       and 'self.fp.seek' not in l]
        if real_errors:
            print('\n'.join(real_errors), file=sys.stderr)
    print(f"Excel updated: {dest}")


# ─────────────────────────────────────────────────────────────────────────────
# --export-cad
# ─────────────────────────────────────────────────────────────────────────────

def cmd_export_cad(json_path: str):
    from exports import export_cad
    results = load_and_run(json_path)
    dest = export_cad(results, 'site_plan.dxf')
    print(f"DXF written: {dest}")


# ─────────────────────────────────────────────────────────────────────────────
# --generate-charts
# ─────────────────────────────────────────────────────────────────────────────

def cmd_generate_charts(json_path: str):
    from exports import export_png
    results = load_and_run(json_path)
    paths = export_png(results, output_dir='charts_output')
    print(f"PNG files written ({len(paths)}):")
    for p in paths:
        print(f"  {p}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Basin geometry calculation engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--process',         metavar='JSON', help='Compute and print summary table')
    parser.add_argument('--export-excel',    metavar='JSON', help='Inject results into Excel template')
    parser.add_argument('--export-cad',      metavar='JSON', help='Write 2D DXF site plan')
    parser.add_argument('--generate-charts', metavar='JSON', help='Save 2D blueprint + 3D PNGs')

    args = parser.parse_args()

    if args.process:
        cmd_process(args.process)
    elif args.export_excel:
        cmd_export_excel(args.export_excel)
    elif args.export_cad:
        cmd_export_cad(args.export_cad)
    elif args.generate_charts:
        cmd_generate_charts(args.generate_charts)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
