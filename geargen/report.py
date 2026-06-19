"""Engineering reports and 2-D exports (data sheet, DXF, SVG).

These are handy companions to the 3-D STEP output: a human-readable gear data
sheet, a DXF of the tooth profile (for laser/water-jet/wire-EDM or 2-D CAD) and
an SVG preview.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from .geometry import GearParams, gear_profile

XY = Tuple[float, float]


# --------------------------------------------------------------------------- #
# Text data sheet
# --------------------------------------------------------------------------- #
def datasheet(p: GearParams, title: str = "GEAR DATA SHEET") -> str:
    s = p.summary()
    rows = [
        ("Module m", f"{p.module:.4g} mm"),
        ("Number of teeth z", f"{p.teeth}"),
        ("Pressure angle alpha", f"{p.pressure_angle:.4g} deg"),
        ("Helix angle beta", f"{p.helix_angle:.4g} deg"),
        ("Profile shift x", f"{p.profile_shift:.4g}"),
        ("Face width b", f"{p.face_width:.4g} mm"),
        ("", ""),
        ("Reference (pitch) dia. d", f"{s['pitch_diameter']:.4f} mm"),
        ("Base circle dia. db", f"{s['base_diameter']:.4f} mm"),
        ("Tip circle dia. da", f"{s['tip_diameter']:.4f} mm"),
        ("Root circle dia. df", f"{s['root_diameter']:.4f} mm"),
        ("Addendum ha", f"{s['addendum']:.4f} mm"),
        ("Dedendum hf", f"{s['dedendum']:.4f} mm"),
        ("Circular pitch p", f"{s['circular_pitch']:.4f} mm"),
        ("Tooth thickness (pitch)", f"{s['tooth_thickness_pitch']:.4f} mm"),
        ("Type", "internal" if p.internal else "external"),
    ]
    if math.isfinite(p.lead):
        rows.append(("Helix lead", f"{p.lead:.3f} mm/turn"))
    width = max(len(k) for k, _ in rows if k) + 2
    lines = [f"  {title}", "  " + "-" * (width + 22)]
    for k, v in rows:
        if not k:
            lines.append("")
        else:
            lines.append(f"  {k:<{width}}{v}")
    warns = p.validate()
    if warns:
        lines.append("")
        lines.append("  WARNINGS:")
        for w in warns:
            lines.append(f"    - {w}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# DXF (R12-compatible, LINE entities - universally readable)
# --------------------------------------------------------------------------- #
def _dxf_entities(loops: Sequence[Sequence[XY]], layer: str = "GEAR") -> List[str]:
    out: List[str] = []
    for loop in loops:
        n = len(loop)
        for i in range(n):
            x0, y0 = loop[i]
            x1, y1 = loop[(i + 1) % n]
            out += ["0", "LINE", "8", layer,
                    "10", f"{x0:.6f}", "20", f"{y0:.6f}", "30", "0.0",
                    "11", f"{x1:.6f}", "21", f"{y1:.6f}", "31", "0.0"]
    return out


def write_dxf(loops: Sequence[Sequence[XY]], path: str,
              layer: str = "GEAR") -> str:
    """Write 2-D closed loops to a minimal, widely-readable DXF file."""
    codes = ["0", "SECTION", "2", "ENTITIES"]
    codes += _dxf_entities(loops, layer)
    codes += ["0", "ENDSEC", "0", "EOF"]
    with open(path, "w") as fh:
        fh.write("\n".join(codes) + "\n")
    return path


def gear_dxf(p: GearParams, path: str, flank_pts: int = 24,
             arc_pts: int = 8, with_bore: float = 0.0) -> str:
    loops: List[List[XY]] = [gear_profile(p, flank_pts, arc_pts)]
    if with_bore > 0:
        seg = 96
        loops.append([(with_bore / 2 * math.cos(2 * math.pi * i / seg),
                       with_bore / 2 * math.sin(2 * math.pi * i / seg))
                      for i in range(seg)])
    return write_dxf(loops, path)


# --------------------------------------------------------------------------- #
# SVG preview
# --------------------------------------------------------------------------- #
def write_svg(loops: Sequence[Sequence[XY]], path: str,
              margin: float = 5.0, stroke: float = 0.3) -> str:
    xs = [x for loop in loops for x, _ in loop]
    ys = [y for loop in loops for _, y in loop]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = (maxx - minx) + 2 * margin
    h = (maxy - miny) + 2 * margin

    def tx(x: float) -> float:
        return x - minx + margin

    def ty(y: float) -> float:                 # flip Y for screen coords
        return (maxy - y) + margin

    paths = []
    for loop in loops:
        d = "M " + " L ".join(f"{tx(x):.3f},{ty(y):.3f}" for x, y in loop) + " Z"
        paths.append(
            f'<path d="{d}" fill="none" stroke="#1565c0" '
            f'stroke-width="{stroke}"/>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w:.2f}mm" height="{h:.2f}mm" '
        f'viewBox="0 0 {w:.3f} {h:.3f}">\n'
        f'  <rect width="{w:.3f}" height="{h:.3f}" fill="white"/>\n  '
        + "\n  ".join(paths)
        + "\n</svg>\n")
    with open(path, "w") as fh:
        fh.write(svg)
    return path


def gear_svg(p: GearParams, path: str, flank_pts: int = 24,
             arc_pts: int = 8, with_bore: float = 0.0) -> str:
    loops: List[List[XY]] = [gear_profile(p, flank_pts, arc_pts)]
    if with_bore > 0:
        seg = 96
        loops.append([(with_bore / 2 * math.cos(2 * math.pi * i / seg),
                       with_bore / 2 * math.sin(2 * math.pi * i / seg))
                      for i in range(seg)])
    return write_svg(loops, path)
