"""Command-line interface for geargen.

Examples
--------
    python -m geargen gear  --module 2 --teeth 20 --width 10 --bore 10 \\
                            --fillet 0.6 --out gear.step --dxf gear.dxf
    python -m geargen pair  --module 2 --pinion 18 --wheel 36 --width 10 \\
                            --out pair.step --rpm 1500 --torque 12
    python -m geargen train --module 1.5 --stages 16:48,18:54 --out train.step
    python -m geargen planetary --module 2 --sun 24 --planet 18 --planets 3 \\
                            --out planetary.step
    python -m geargen bevel --module 3 --pinion 18 --wheel 27 --out bevel.step
    python -m geargen worm  --module 3 --starts 2 --worm-d 30 --wheel 40 \\
                            --out worm.step
    python -m geargen rack  --module 2 --teeth 14 --pinion 16 --out rack.step
    python -m geargen info  --module 2 --teeth 17
    python -m geargen ratio --target 4.5 --min 14 --max 90
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .geometry import GearParams
from .gear import (Gear, GearBuild, Keyway, Spline, LighteningHoles, Spokes, Hub)
from .transmission import GearPair, GearTrain, Stage
from .planetary import PlanetaryGearSet, PlanetaryParams
from .bevel import BevelPair, BevelGear, BevelParams
from .worm import WormDrive, WormParams
from .rack import Rack, RackParams, RackAndPinion
from .step import write_step
from .report import datasheet, gear_dxf, gear_svg


# --------------------------------------------------------------------------- #
# Option parsers
# --------------------------------------------------------------------------- #
def _csv(text: str):
    return [p for p in text.replace(":", ",").replace("x", ",").split(",") if p]


def _keyway(text):
    if not text:
        return None
    p = _csv(text)
    return Keyway(float(p[0]), float(p[1]))


def _holes(text):
    if not text:
        return None
    p = _csv(text)
    if len(p) < 3:
        raise argparse.ArgumentTypeError("holes = COUNT,DIA,PITCHCIRCLE")
    return LighteningHoles(int(p[0]), float(p[1]), float(p[2]))


def _spline(text):
    if not text:
        return None
    p = _csv(text)
    if len(p) < 3:
        raise argparse.ArgumentTypeError("spline = COUNT,MINOR_DIA,MAJOR_DIA")
    return Spline(int(p[0]), float(p[1]), float(p[2]))


def _spokes(text):
    if not text:
        return None
    p = _csv(text)
    if len(p) < 4:
        raise argparse.ArgumentTypeError(
            "spokes = COUNT,HUB_DIA,RIM_INNER_DIA,WIDTH")
    return Spokes(int(p[0]), float(p[1]), float(p[2]), float(p[3]))


def _hub(text):
    if not text:
        return None
    p = _csv(text)
    if len(p) < 2:
        raise argparse.ArgumentTypeError("hub = DIA,HEIGHT[,both]")
    both = len(p) > 2 and p[2].lower().startswith("b")
    return Hub(float(p[0]), float(p[1]), both)


def _gear_build(args) -> GearBuild:
    return GearBuild(
        bore=getattr(args, "bore", 0.0),
        keyway=_keyway(getattr(args, "keyway", None)),
        spline=_spline(getattr(args, "spline", None)),
        lightening=_holes(getattr(args, "holes", None)),
        spokes=_spokes(getattr(args, "spokes", None)),
        hub=_hub(getattr(args, "hub", None)),
        herringbone=getattr(args, "herringbone", False),
        flank_pts=args.flank_pts,
        arc_pts=args.arc_pts,
    )


def _gear_params(args) -> GearParams:
    return GearParams(module=args.module, teeth=args.teeth,
                      pressure_angle=args.pressure_angle, helix_angle=args.helix,
                      face_width=args.width, profile_shift=args.shift,
                      root_fillet=getattr(args, "fillet", 0.0))


def _print(title, d):
    print(f"  {title}")
    print("  " + "-" * 46)
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"      {kk:<28}{vv}")
        else:
            print(f"  {k:<30}{v}")


def _common_gear_opts(sp):
    sp.add_argument("--module", "-m", type=float, required=True, help="module m (mm)")
    sp.add_argument("--pressure-angle", "-a", type=float, default=20.0)
    sp.add_argument("--helix", type=float, default=0.0, help="helix angle (deg)")
    sp.add_argument("--width", "-w", type=float, default=10.0, help="face width (mm)")
    sp.add_argument("--shift", type=float, default=0.0, help="profile shift x")
    sp.add_argument("--flank-pts", type=int, default=18)
    sp.add_argument("--arc-pts", type=int, default=6)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_gear(args):
    p = _gear_params(args)
    print(datasheet(p, f"GEAR  z={args.teeth}  m={args.module:g}"))
    out = args.out or f"gear_z{p.z}_m{args.module:g}.step"
    write_step(Gear(p, _gear_build(args)).to_solid(), out, f"gear_z{p.z}")
    print(f"\n  [STEP] {out}")
    if args.dxf:
        gear_dxf(p, args.dxf, args.flank_pts * 2, args.arc_pts * 2, args.bore)
        print(f"  [DXF ] {args.dxf}")
    if args.svg:
        gear_svg(p, args.svg, args.flank_pts * 2, args.arc_pts * 2, args.bore)
        print(f"  [SVG ] {args.svg}")
    return 0


def cmd_pair(args):
    P = GearParams(args.module, args.pinion, args.pressure_angle, args.shift_p,
                   args.helix, args.width)
    W = GearParams(args.module, args.wheel, args.pressure_angle, args.shift_w,
                   -args.helix, args.width)
    pair = GearPair(P, W,
                    GearBuild(bore=args.bore_p, flank_pts=args.flank_pts),
                    GearBuild(bore=args.bore_w, flank_pts=args.flank_pts))
    _print("GEAR PAIR", pair.report(args.rpm, args.torque))
    out = args.out or f"pair_{args.pinion}_{args.wheel}.step"
    write_step(pair.solids(), out, f"pair_{args.pinion}_{args.wheel}")
    print(f"\n  [STEP] {out}  (2 solids, meshed)")
    return 0


def cmd_train(args):
    stages = []
    for chunk in args.stages.split(","):
        a, b = chunk.split(":")
        stages.append(Stage(
            GearParams(args.module, int(a), args.pressure_angle, face_width=args.width),
            GearParams(args.module, int(b), args.pressure_angle, face_width=args.width)))
    train = GearTrain(stages)
    rep = train.report(args.rpm)
    print(f"  GEAR TRAIN  ({rep['stages']} stages, overall ratio "
          f"{rep['overall_ratio']}, output {rep['output_rpm']} rpm)")
    for i, st in enumerate(rep["stage_details"], 1):
        print(f"    stage {i}: z{st['z_pinion']}/{st['z_wheel']} "
              f"i={st['ratio']}  a={st['working_center_distance']} mm")
    out = args.out or "train.step"
    write_step(train.solids(), out, "gear_train")
    print(f"\n  [STEP] {out}  ({2*len(stages)} solids)")
    return 0


def cmd_planetary(args):
    pp = PlanetaryParams(args.module, args.sun, args.planet, args.planets,
                         args.pressure_angle, args.width)
    pgs = PlanetaryGearSet(pp, bore_sun=args.bore_sun, bore_planet=args.bore_planet)
    _print("PLANETARY GEAR SET", pgs.report(args.rpm))
    out = args.out or "planetary.step"
    write_step(pgs.solids(with_ring=not args.no_ring), out, "planetary")
    n = 1 + pp.n_planets + (0 if args.no_ring else 1)
    print(f"\n  [STEP] {out}  ({n} solids: sun + {pp.n_planets} planets"
          f"{'' if args.no_ring else ' + ring'})")
    return 0


def cmd_bevel(args):
    pair = BevelPair.right_angle(args.module, args.pinion, args.wheel, args.width,
                                 args.pressure_angle, args.bore_p, args.bore_w)
    _print("BEVEL DRIVE (90 deg)", pair.report(args.rpm, args.torque))
    out = args.out or f"bevel_{args.pinion}_{args.wheel}.step"
    write_step(pair.solids(), out, "bevel_pair")
    print(f"\n  [STEP] {out}  (2 solids)")
    return 0


def cmd_worm(args):
    wd = WormDrive(WormParams(args.module, args.starts, args.worm_d, args.worm_len,
                              args.pressure_angle, args.bore_worm),
                   wheel_teeth=args.wheel, wheel_face_width=args.width,
                   wheel_bore=args.bore_wheel)
    _print("WORM DRIVE", wd.report(args.rpm, args.torque))
    out = args.out or f"worm_{args.starts}_{args.wheel}.step"
    write_step(wd.solids(), out, "worm_drive")
    print(f"\n  [STEP] {out}  (worm + wheel)")
    return 0


def cmd_rack(args):
    rack = RackParams(args.module, args.teeth, args.pressure_angle, args.width)
    if args.pinion:
        rp = RackAndPinion(GearParams(args.module, args.pinion, args.pressure_angle,
                                      face_width=args.width), rack,
                           GearBuild(bore=args.bore))
        _print("RACK & PINION", rp.report(args.rpm))
        out = args.out or "rack_pinion.step"
        write_step(rp.solids(), out, "rack_pinion")
        print(f"\n  [STEP] {out}  (rack + pinion)")
    else:
        out = args.out or "rack.step"
        write_step(Rack(rack).to_solid(), out, "rack")
        print(f"  RACK z={args.teeth}  length={rack.length:.2f} mm")
        print(f"\n  [STEP] {out}")
    return 0


def cmd_info(args):
    p = _gear_params(args)
    if args.json:
        print(json.dumps(p.summary(), indent=2))
    else:
        print(datasheet(p, f"GEAR  z={args.teeth}  m={args.module:g}"))
    return 0


def cmd_ratio(args):
    target = args.target
    best = []
    for z1 in range(args.min, args.max + 1):
        z2 = round(z1 * target)
        if z2 < args.min or z2 > args.max:
            continue
        err = abs((z2 / z1) - target) / target
        best.append((err, z1, z2))
    best.sort()
    print(f"  Target ratio {target}  (teeth {args.min}..{args.max})")
    print(f"  {'pinion':>7} {'wheel':>7} {'ratio':>9} {'error %':>9}")
    for err, z1, z2 in best[:args.count]:
        print(f"  {z1:>7} {z2:>7} {z2/z1:>9.4f} {err*100:>8.3f}%")
    return 0


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser():
    pr = argparse.ArgumentParser(
        prog="geargen",
        description="Involute gear & transmission generator with STEP/DXF/SVG export.")
    sub = pr.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gear", help="single gear (spur/helical/herringbone/internal)")
    _common_gear_opts(g)
    g.add_argument("--teeth", "-z", type=int, required=True,
                   help="teeth (negative = internal/ring gear)")
    g.add_argument("--fillet", type=float, default=0.0, help="root fillet radius (mm)")
    g.add_argument("--herringbone", action="store_true", help="double-helical")
    g.add_argument("--bore", type=float, default=0.0)
    g.add_argument("--keyway", help="WIDTHxDEPTH")
    g.add_argument("--spline", help="COUNT,MINOR_DIA,MAJOR_DIA")
    g.add_argument("--holes", help="lightening COUNT,DIA,PITCHCIRCLE")
    g.add_argument("--spokes", help="COUNT,HUB_DIA,RIM_INNER_DIA,WIDTH")
    g.add_argument("--hub", help="DIA,HEIGHT[,both]")
    g.add_argument("--out", "-o")
    g.add_argument("--dxf")
    g.add_argument("--svg")
    g.set_defaults(func=cmd_gear)

    pa = sub.add_parser("pair", help="meshing gear pair")
    _common_gear_opts(pa)
    pa.add_argument("--pinion", type=int, required=True)
    pa.add_argument("--wheel", type=int, required=True, help="negative = internal")
    pa.add_argument("--bore-p", type=float, default=0.0)
    pa.add_argument("--bore-w", type=float, default=0.0)
    pa.add_argument("--shift-p", type=float, default=0.0)
    pa.add_argument("--shift-w", type=float, default=0.0)
    pa.add_argument("--rpm", type=float, default=1500.0)
    pa.add_argument("--torque", type=float, default=10.0)
    pa.add_argument("--out", "-o")
    pa.set_defaults(func=cmd_pair)

    tr = sub.add_parser("train", help="multi-stage gear train")
    _common_gear_opts(tr)
    tr.add_argument("--stages", required=True, help="z1:z2,z3:z4,... e.g. 18:54,16:48")
    tr.add_argument("--rpm", type=float, default=1500.0)
    tr.add_argument("--out", "-o")
    tr.set_defaults(func=cmd_train)

    pl = sub.add_parser("planetary", help="planetary (epicyclic) gear set")
    pl.add_argument("--module", "-m", type=float, required=True)
    pl.add_argument("--sun", type=int, required=True, help="sun teeth")
    pl.add_argument("--planet", type=int, required=True, help="planet teeth")
    pl.add_argument("--planets", type=int, default=3, help="number of planets")
    pl.add_argument("--pressure-angle", "-a", type=float, default=20.0)
    pl.add_argument("--width", "-w", type=float, default=10.0)
    pl.add_argument("--bore-sun", type=float, default=0.0)
    pl.add_argument("--bore-planet", type=float, default=0.0)
    pl.add_argument("--no-ring", action="store_true")
    pl.add_argument("--rpm", type=float, default=1500.0)
    pl.add_argument("--out", "-o")
    pl.set_defaults(func=cmd_planetary)

    bv = sub.add_parser("bevel", help="right-angle bevel drive")
    bv.add_argument("--module", "-m", type=float, required=True)
    bv.add_argument("--pinion", type=int, required=True)
    bv.add_argument("--wheel", type=int, required=True)
    bv.add_argument("--pressure-angle", "-a", type=float, default=20.0)
    bv.add_argument("--width", "-w", type=float, default=10.0)
    bv.add_argument("--bore-p", type=float, default=0.0)
    bv.add_argument("--bore-w", type=float, default=0.0)
    bv.add_argument("--rpm", type=float, default=1000.0)
    bv.add_argument("--torque", type=float, default=10.0)
    bv.add_argument("--out", "-o")
    bv.set_defaults(func=cmd_bevel)

    wm = sub.add_parser("worm", help="worm drive")
    wm.add_argument("--module", "-m", type=float, required=True)
    wm.add_argument("--starts", type=int, default=1, help="worm starts z_w")
    wm.add_argument("--worm-d", type=float, required=True, help="worm pitch diameter")
    wm.add_argument("--worm-len", type=float, default=50.0, help="worm length")
    wm.add_argument("--wheel", type=int, required=True, help="wheel teeth")
    wm.add_argument("--pressure-angle", "-a", type=float, default=20.0)
    wm.add_argument("--width", "-w", type=float, default=14.0, help="wheel face width")
    wm.add_argument("--bore-worm", type=float, default=0.0)
    wm.add_argument("--bore-wheel", type=float, default=0.0)
    wm.add_argument("--rpm", type=float, default=1500.0)
    wm.add_argument("--torque", type=float, default=5.0)
    wm.add_argument("--out", "-o")
    wm.set_defaults(func=cmd_worm)

    rk = sub.add_parser("rack", help="rack (and optional pinion)")
    rk.add_argument("--module", "-m", type=float, required=True)
    rk.add_argument("--teeth", "-z", type=int, required=True, help="rack teeth")
    rk.add_argument("--pinion", type=int, default=0, help="add a meshing pinion")
    rk.add_argument("--pressure-angle", "-a", type=float, default=20.0)
    rk.add_argument("--width", "-w", type=float, default=10.0)
    rk.add_argument("--bore", type=float, default=0.0)
    rk.add_argument("--rpm", type=float, default=100.0)
    rk.add_argument("--out", "-o")
    rk.set_defaults(func=cmd_rack)

    inf = sub.add_parser("info", help="print a gear data sheet")
    _common_gear_opts(inf)
    inf.add_argument("--teeth", "-z", type=int, required=True)
    inf.add_argument("--fillet", type=float, default=0.0)
    inf.add_argument("--json", action="store_true")
    inf.set_defaults(func=cmd_info)

    rt = sub.add_parser("ratio", help="find tooth pairs for a target ratio")
    rt.add_argument("--target", "-t", type=float, required=True)
    rt.add_argument("--min", type=int, default=12)
    rt.add_argument("--max", type=int, default=100)
    rt.add_argument("--count", type=int, default=10)
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
