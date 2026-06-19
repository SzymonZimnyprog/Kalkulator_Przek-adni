"""Command-line interface for geargen.

Examples
--------
    python -m geargen gear  --module 2 --teeth 20 --width 10 --bore 10 \\
                            --out gear.step --dxf gear.dxf --svg gear.svg
    python -m geargen pair  --module 2 --pinion 18 --wheel 36 --width 10 \\
                            --out pair.step --rpm 1500 --torque 12
    python -m geargen train --module 1.5 --stages 16:48,18:54 --width 8 \\
                            --out train.step
    python -m geargen info  --module 2 --teeth 17
    python -m geargen ratio --target 4.5 --min 14 --max 90
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Tuple

from .geometry import GearParams
from .gear import Gear, GearBuild, Keyway, LighteningHoles
from .transmission import GearPair, GearTrain, Stage
from .step import write_step
from .report import datasheet, gear_dxf, gear_svg


# --------------------------------------------------------------------------- #
# Argument helpers
# --------------------------------------------------------------------------- #
def _parse_keyway(text: Optional[str]) -> Optional[Keyway]:
    if not text:
        return None
    parts = text.lower().replace("x", " ").split()
    if len(parts) < 2:
        raise argparse.ArgumentTypeError("keyway must be WIDTHxDEPTH, e.g. 4x1.8")
    return Keyway(width=float(parts[0]), depth=float(parts[1]))


def _parse_holes(text: Optional[str]) -> Optional[LighteningHoles]:
    if not text:
        return None
    parts = text.replace(":", ",").split(",")
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(
            "holes must be COUNT,DIAMETER,PITCHCIRCLE, e.g. 6,14,75")
    return LighteningHoles(count=int(parts[0]), diameter=float(parts[1]),
                           pitch_circle=float(parts[2]))


def _build_from_args(args, bore: float) -> GearBuild:
    return GearBuild(
        bore=bore,
        keyway=_parse_keyway(getattr(args, "keyway", None)),
        lightening=_parse_holes(getattr(args, "holes", None)),
        flank_pts=args.flank_pts,
        arc_pts=args.arc_pts,
    )


def _common_gear_opts(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--module", "-m", type=float, required=True, help="module m (mm)")
    sp.add_argument("--pressure-angle", "-a", type=float, default=20.0,
                    help="pressure angle (deg, default 20)")
    sp.add_argument("--helix", type=float, default=0.0, help="helix angle (deg)")
    sp.add_argument("--width", "-w", type=float, default=10.0, help="face width b (mm)")
    sp.add_argument("--shift", type=float, default=0.0, help="profile shift x")
    sp.add_argument("--flank-pts", type=int, default=18,
                    help="involute samples per flank (smoothness)")
    sp.add_argument("--arc-pts", type=int, default=6, help="samples per tip/root arc")


# --------------------------------------------------------------------------- #
# Sub-commands
# --------------------------------------------------------------------------- #
def cmd_gear(args) -> int:
    p = GearParams(module=args.module, teeth=args.teeth,
                   pressure_angle=args.pressure_angle, helix_angle=args.helix,
                   face_width=args.width, profile_shift=args.shift)
    print(datasheet(p, f"GEAR  z={args.teeth}  m={args.module:g}"))
    build = _build_from_args(args, args.bore)
    out = args.out or f"gear_z{p.z}_m{args.module:g}.step"
    write_step(Gear(p, build).to_solid(), out, product=f"gear_z{p.z}")
    print(f"\n  [STEP] {out}")
    if args.dxf:
        gear_dxf(p, args.dxf, args.flank_pts * 2, args.arc_pts * 2, args.bore)
        print(f"  [DXF ] {args.dxf}")
    if args.svg:
        gear_svg(p, args.svg, args.flank_pts * 2, args.arc_pts * 2, args.bore)
        print(f"  [SVG ] {args.svg}")
    return 0


def cmd_pair(args) -> int:
    P = GearParams(module=args.module, teeth=args.pinion,
                   pressure_angle=args.pressure_angle, helix_angle=args.helix,
                   face_width=args.width, profile_shift=args.shift_p)
    # The wheel takes the opposite helix hand so a helical pair meshes.
    W = GearParams(module=args.module, teeth=args.wheel,
                   pressure_angle=args.pressure_angle, helix_angle=-args.helix,
                   face_width=args.width, profile_shift=args.shift_w)
    pair = GearPair(P, W,
                    GearBuild(bore=args.bore_p, flank_pts=args.flank_pts,
                              arc_pts=args.arc_pts),
                    GearBuild(bore=args.bore_w, flank_pts=args.flank_pts,
                              arc_pts=args.arc_pts))
    rep = pair.report(args.rpm, args.torque)
    print("  GEAR PAIR")
    print("  " + "-" * 40)
    for k, v in rep.items():
        print(f"  {k:<28}{v}")
    out = args.out or f"pair_{args.pinion}_{args.wheel}.step"
    write_step(pair.solids(), out, product=f"pair_{args.pinion}_{args.wheel}")
    print(f"\n  [STEP] {out}  (2 solids, meshed)")
    return 0


def cmd_train(args) -> int:
    stages: List[Stage] = []
    for chunk in args.stages.split(","):
        a, b = chunk.split(":")
        stages.append(Stage(
            GearParams(module=args.module, teeth=int(a),
                       pressure_angle=args.pressure_angle, face_width=args.width),
            GearParams(module=args.module, teeth=int(b),
                       pressure_angle=args.pressure_angle, face_width=args.width)))
    train = GearTrain(stages)
    rep = train.report(args.rpm)
    print("  GEAR TRAIN")
    print("  " + "-" * 40)
    print(f"  stages          {rep['stages']}")
    print(f"  overall ratio   {rep['overall_ratio']}")
    print(f"  input rpm       {rep['input_rpm']}")
    print(f"  output rpm      {rep['output_rpm']}")
    for i, st in enumerate(rep["stage_details"], 1):
        print(f"    stage {i}: z{st['z_pinion']}/{st['z_wheel']} "
              f"i={st['ratio']}  a={st['working_center_distance']} mm")
    out = args.out or "train.step"
    write_step(train.solids(), out, product="gear_train")
    print(f"\n  [STEP] {out}  ({2*len(stages)} solids)")
    return 0


def cmd_info(args) -> int:
    p = GearParams(module=args.module, teeth=args.teeth,
                   pressure_angle=args.pressure_angle, helix_angle=args.helix,
                   face_width=args.width, profile_shift=args.shift)
    if args.json:
        print(json.dumps(p.summary(), indent=2))
    else:
        print(datasheet(p, f"GEAR  z={args.teeth}  m={args.module:g}"))
    return 0


def cmd_ratio(args) -> int:
    """Suggest tooth-count pairs approximating a target ratio."""
    target = args.target
    best: List[Tuple[float, int, int]] = []
    for z1 in range(args.min, args.max + 1):
        z2 = round(z1 * target)
        if z2 < args.min or z2 > args.max:
            continue
        err = abs((z2 / z1) - target) / target
        best.append((err, z1, z2))
    best.sort()
    print(f"  Target ratio {target}  (teeth {args.min}..{args.max})")
    print("  " + "-" * 40)
    print(f"  {'pinion':>7} {'wheel':>7} {'ratio':>9} {'error %':>9}")
    for err, z1, z2 in best[:args.count]:
        print(f"  {z1:>7} {z2:>7} {z2/z1:>9.4f} {err*100:>8.3f}%")
    return 0


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    pr = argparse.ArgumentParser(
        prog="geargen",
        description="Involute gear & transmission generator with STEP/DXF/SVG export.")
    sub = pr.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gear", help="generate a single gear")
    _common_gear_opts(g)
    g.add_argument("--teeth", "-z", type=int, required=True,
                   help="number of teeth (negative = internal/ring gear)")
    g.add_argument("--bore", type=float, default=0.0, help="bore diameter (mm)")
    g.add_argument("--keyway", help="keyway WIDTHxDEPTH, e.g. 4x1.8")
    g.add_argument("--holes", help="lightening holes COUNT,DIA,PITCHCIRCLE")
    g.add_argument("--out", "-o", help="output STEP path")
    g.add_argument("--dxf", help="also write a 2-D DXF profile")
    g.add_argument("--svg", help="also write a 2-D SVG preview")
    g.set_defaults(func=cmd_gear)

    pa = sub.add_parser("pair", help="generate a meshing gear pair")
    _common_gear_opts(pa)
    pa.add_argument("--pinion", type=int, required=True, help="pinion teeth z1")
    pa.add_argument("--wheel", type=int, required=True,
                    help="wheel teeth z2 (negative = internal mesh)")
    pa.add_argument("--bore-p", type=float, default=0.0, help="pinion bore (mm)")
    pa.add_argument("--bore-w", type=float, default=0.0, help="wheel bore (mm)")
    pa.add_argument("--shift-p", type=float, default=0.0, help="pinion profile shift")
    pa.add_argument("--shift-w", type=float, default=0.0, help="wheel profile shift")
    pa.add_argument("--rpm", type=float, default=1500.0, help="input speed (rpm)")
    pa.add_argument("--torque", type=float, default=10.0, help="input torque (Nm)")
    pa.add_argument("--out", "-o", help="output STEP path")
    # 'shift' from common opts is unused for pairs; keep for parser symmetry.
    pa.set_defaults(func=cmd_pair, teeth=None, shift=0.0)

    tr = sub.add_parser("train", help="generate a multi-stage gear train")
    _common_gear_opts(tr)
    tr.add_argument("--stages", required=True,
                    help="stages as z1:z2,z3:z4,...  e.g. 18:54,16:48")
    tr.add_argument("--rpm", type=float, default=1500.0, help="input speed (rpm)")
    tr.add_argument("--out", "-o", help="output STEP path")
    tr.set_defaults(func=cmd_train, teeth=None, shift=0.0)

    inf = sub.add_parser("info", help="print a gear data sheet")
    _common_gear_opts(inf)
    inf.add_argument("--teeth", "-z", type=int, required=True)
    inf.add_argument("--json", action="store_true", help="print JSON instead")
    inf.set_defaults(func=cmd_info)

    rt = sub.add_parser("ratio", help="find tooth pairs for a target ratio")
    rt.add_argument("--target", "-t", type=float, required=True, help="target ratio")
    rt.add_argument("--min", type=int, default=12, help="min teeth (default 12)")
    rt.add_argument("--max", type=int, default=100, help="max teeth (default 100)")
    rt.add_argument("--count", type=int, default=10, help="results to show")
    rt.set_defaults(func=cmd_ratio)

    return pr


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, argparse.ArgumentTypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
