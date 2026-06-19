"""Numerical-control (CNC) output: G-code and coordinate tables.

Turns a gear's 2-D section (outer profile + bore/holes) into machine programs:

* **WEDM** - wire-EDM contour cutting (the most accurate way to make a gear).
* **2.5-D milling** - multi-pass contour milling with optional cutter-radius
  compensation (G41/G42).
* **Laser / plasma / engraving** - single-pass 2-D contour cutting.

plus numerical exports (CSV / JSON) of the tooth coordinates for CMM, FEM, etc.

The G-code is generic ISO (G20/G21, G90, G00/G01, F, M03/M05).  Wire/tool
offset is left to the machine (G41/G42) so the true part contour is emitted -
set the kerf/wire/tool radius in the control.
"""

from __future__ import annotations

import json
import math
from typing import List, Optional, Sequence, Tuple

XY = Tuple[float, float]
Loops = Sequence[Sequence[XY]]


def _fmt(v: float) -> str:
    v = round(v, 4)
    if v == 0:
        v = 0.0                         # avoid "-0"
    s = f"{v:.4f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _lead_point(loop: Sequence[XY], outward: bool, dist: float) -> XY:
    """A pierce/approach point offset radially from the first contour point."""
    x0, y0 = loop[0]
    r = math.hypot(x0, y0) or 1.0
    k = (r + dist) / r if outward else max(0.05, (r - dist) / r)
    return (x0 * k, y0 * k)


# --------------------------------------------------------------------------- #
# Coordinate exports
# --------------------------------------------------------------------------- #
def to_csv(loops: Loops, path: str) -> str:
    lines = ["contour,point,x_mm,y_mm"]
    for ci, loop in enumerate(loops):
        for pi, (x, y) in enumerate(loop):
            x = 0.0 if round(x, 6) == 0 else x
            y = 0.0 if round(y, 6) == 0 else y
            lines.append(f"{ci},{pi},{x:.6f},{y:.6f}")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def to_json(meta: dict, loops: Loops, path: str) -> str:
    data = {
        "metadata": meta,
        "units": "mm",
        "contours": [[[round(x, 6), round(y, 6)] for (x, y) in loop]
                     for loop in loops],
    }
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
    return path


# --------------------------------------------------------------------------- #
# G-code
# --------------------------------------------------------------------------- #
def _header(title: str, metric: bool) -> List[str]:
    return [f"({title})", "G21" if metric else "G20",
            "G90", "G17", "G40", "G94"]


def gcode_wedm(loops: Loops, title: str = "GEAR WEDM",
               feed: float = 2.0, lead_in: float = 2.0,
               comp: str = "none", offset_reg: int = 1) -> str:
    """Wire-EDM program.  ``comp`` in {'none','left','right'} enables G41/G42."""
    out = ["%"] + _header(title, True)
    out.append(f"F{_fmt(feed)}")
    for ci, loop in enumerate(loops):
        outward = (ci == 0)              # outer contour pierces from outside
        px, py = _lead_point(loop, outward, lead_in)
        out += [f"(contour {ci})",
                f"G00 X{_fmt(px)} Y{_fmt(py)}",
                "M50 (wire on / flush on)"]
        if comp != "none":
            g = "G41" if comp == "left" else "G42"
            out.append(f"{g} D{offset_reg}")
        out.append(f"G01 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])}")
        for (x, y) in loop[1:]:
            out.append(f"G01 X{_fmt(x)} Y{_fmt(y)}")
        out.append(f"G01 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])}")
        if comp != "none":
            out.append("G40")
        out += [f"G01 X{_fmt(px)} Y{_fmt(py)}", "M51 (wire off)"]
    out += ["M02", "%"]
    return "\n".join(out) + "\n"


def gcode_mill(loops: Loops, title: str = "GEAR MILL",
               depth: float = 5.0, doc: float = 1.0, tool_d: float = 2.0,
               feed: float = 300.0, plunge: float = 100.0, safe_z: float = 5.0,
               comp: str = "none") -> str:
    """2.5-D contour milling with multiple Z passes.

    ``comp`` in {'none','left','right'} emits G41/G42 (tool radius set in the
    control).  Outer contour is cut climb-style; holes are cut from inside.
    """
    out = _header(title, True)
    out += [f"(tool diameter {tool_d} mm, depth {depth} mm, {doc} mm/pass)",
            f"G00 Z{_fmt(safe_z)}", "M03 (spindle on)"]
    n_pass = max(1, math.ceil(depth / doc))
    for ci, loop in enumerate(loops):
        out.append(f"(contour {ci})")
        out.append(f"G00 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])}")
        for k in range(1, n_pass + 1):
            z = -min(depth, k * doc)
            out.append(f"G01 Z{_fmt(z)} F{_fmt(plunge)}")
            if comp != "none":
                g = "G41" if comp == "left" else "G42"
                out.append(f"{g}")
            out.append(f"G01 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])} F{_fmt(feed)}")
            for (x, y) in loop[1:]:
                out.append(f"G01 X{_fmt(x)} Y{_fmt(y)}")
            out.append(f"G01 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])}")
            if comp != "none":
                out.append("G40")
        out.append(f"G00 Z{_fmt(safe_z)}")
    out += ["M05 (spindle off)", "M30"]
    return "\n".join(out) + "\n"


def gcode_laser(loops: Loops, title: str = "GEAR LASER",
                feed: float = 600.0, power: int = 800, passes: int = 1) -> str:
    """Single- or multi-pass 2-D laser/plasma/engrave contour program."""
    out = _header(title, True)
    out.append(f"(power S{power}, {passes} pass(es))")
    for _ in range(passes):
        for ci, loop in enumerate(loops):
            out += [f"(contour {ci})",
                    f"G00 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])}",
                    f"M03 S{power} (beam on)",
                    f"G01 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])} F{_fmt(feed)}"]
            for (x, y) in loop[1:]:
                out.append(f"G01 X{_fmt(x)} Y{_fmt(y)}")
            out += [f"G01 X{_fmt(loop[0][0])} Y{_fmt(loop[0][1])}",
                    "M05 (beam off)"]
    out.append("M30")
    return "\n".join(out) + "\n"


def write_gcode(text: str, path: str) -> str:
    with open(path, "w") as fh:
        fh.write(text)
    return path


PROCESSES = {
    "wedm": gcode_wedm,
    "mill": gcode_mill,
    "laser": gcode_laser,
}
