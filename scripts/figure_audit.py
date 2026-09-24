#!/usr/bin/env python3
"""Mechanical figure checks: the part of an audit that does not need judgement.

Every check prints one line: PASS, FAIL, SKIP or INFO.

  PASS  the check ran and the figure met it
  FAIL  the check ran and the figure did not
  SKIP  the check applies but could NOT be established -- a tool is missing, the file does not
        carry the information, or the input is outside what this script can resolve
  INFO  an observation that is not a pass/fail criterion

Exit status is the honest summary, not the optimistic one:

  0  every applicable check ran and passed
  1  at least one check FAILED
  3  nothing failed, but at least one check was SKIPPED, or nothing was checked at all --
     the mechanical screen is INCOMPLETE. Pass --allow-skip to accept stated, known gaps.
  2  usage error

This is a screening tool. A PASS applies only to the named check; exit 0 says nothing about
whether the figure is scientifically correct.

    figure_audit.py geometry  <file.svg|file.pdf> [--max-width-mm 180] [--max-height-mm 247]
    figure_audit.py text      <file.svg> [--min-pt 5.5]
    figure_audit.py fonts     <file.pdf>
    figure_audit.py export    <file.tiff|file.png> [--min-dpi 300] [--tiff-modes RGB,L,CMYK,1]
    figure_audit.py video     <file.mp4> [--thorough] [--codec h264]
    figure_audit.py stale     <output-dir> <generator> [<generator> ...]
    figure_audit.py inventory <dir> [--formats svg,pdf,png,tiff] [--expect STEM]...
    figure_audit.py svgdiff   <a.svg> <b.svg>
    figure_audit.py all       <dir> [--generator PATH]... [--expect STEM]... [--formats ...]
                              [--max-width-mm] [--max-height-mm] [--min-pt] [--min-dpi]
                              [--tiff-modes ...] [--codec ...] [--thorough]

Every subcommand also takes --allow-skip. Limits, formats, TIFF modes and codec defaults are
screening conventions, not journal rules: pass the values from the figure contract.

Only the Python standard library is required. PDF checks need poppler's pdfinfo/pdffonts, raster
checks need Pillow, video checks need ffprobe/ffmpeg. Without them the checks SKIP; they never
fall back to a weaker method and report its answer as if it were the real one.
"""
from __future__ import annotations

import argparse
import difflib
import math
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PT_PER_MM = 72.0 / 25.4
PX_PER_PT = 96.0 / 72.0          # CSS: 96 px per inch, 72 pt per inch
DEFAULT_FONT_PX = 16.0           # CSS initial value, "medium"
FIG_EXT = {".svg", ".pdf", ".png", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
TOOL_TIMEOUT = 180               # seconds; a hung decoder is a SKIP, not a hang
XLINK = "{http://www.w3.org/1999/xlink}href"
TIFF_MODES = "RGB,L,CMYK,1"   # alpha-free; many journals reject an alpha channel

RESULTS: list[tuple[str, str, str]] = []


def record(status: str, check: str, detail: str) -> None:
    RESULTS.append((status, check, detail))
    print(f"  {status:<4}  {check:<36} {detail}")


def run(cmd: list[str], timeout: int = TOOL_TIMEOUT) -> subprocess.CompletedProcess | None:
    """Run a tool; None means it did not finish, which callers report as SKIP."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# ================================================================================ SVG units
_LEN = re.compile(r"^\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*$")
_ABS_TO_PX = {"": 1.0, "px": 1.0, "pt": PX_PER_PT, "pc": 16.0, "in": 96.0,
              "cm": 96.0 / 2.54, "mm": 96.0 / 25.4, "q": 96.0 / 101.6}


def length_px(value: str | None) -> float | None:
    """An absolute SVG/CSS length in px, or None if it is relative or unparseable."""
    if not value:
        return None
    m = _LEN.match(value)
    if not m or m.group(2).lower() not in _ABS_TO_PX:
        return None
    return float(m.group(1)) * _ABS_TO_PX[m.group(2).lower()]


def pt_per_user_unit(root: ET.Element) -> float | None:
    """How many physical points one SVG user unit is, or None if the SVG has no physical size.

    A viewBox alone declares a coordinate system, not a size on paper: such an SVG scales to
    whatever box it is placed in, so no physical font size or page size can be read from it.
    """
    w = length_px(root.get("width"))
    if w is None:
        return None
    vb = root.get("viewBox")
    if vb:
        parts = [float(v) for v in re.split(r"[\s,]+", vb.strip()) if v]
        if len(parts) == 4 and parts[2] > 0:
            return (w / PX_PER_PT) / parts[2]
    return 1.0 / PX_PER_PT                 # no viewBox: one user unit is one CSS px


# ================================================================================ geometry
def pdf_pages_pt(path: Path) -> list[tuple[float, float]] | str:
    """Every page's size as viewed (rotation applied), or an error string.

    Read by poppler's parser, not by scanning bytes: MediaBox can be inherited from a parent
    /Pages node, sit in a compressed object stream, or differ between pages, and a byte regex
    silently reports whichever box it happens to find first.
    """
    if not shutil.which("pdfinfo"):
        return "SKIP: pdfinfo not installed"
    q = run(["pdfinfo", "-f", "1", "-l", "100000", str(path)])
    if q is None:
        return "SKIP: pdfinfo timed out"
    if q.returncode != 0:
        return f"FAIL: pdfinfo could not read it: {(q.stderr or '').strip()[:100]}"
    sizes = {int(m.group(1)): (float(m.group(2)), float(m.group(3)))
             for m in re.finditer(r"Page\s+(\d+)\s+size:\s*([0-9.]+)\s*x\s*([0-9.]+)", q.stdout)}
    rots = {int(m.group(1)): int(m.group(2))
            for m in re.finditer(r"Page\s+(\d+)\s+rot:\s*(-?\d+)", q.stdout)}
    if not sizes:
        return "FAIL: pdfinfo reported no page sizes"
    pages = []
    for n in sorted(sizes):
        w, h = sizes[n]
        if rots.get(n, 0) % 180 == 90:
            w, h = h, w
        pages.append((w, h))
    return pages


def cmd_geometry(path: Path, max_w: float, max_h: float) -> None:
    name = f"geometry {path.name}"
    ext = path.suffix.lower()
    if ext == ".svg":
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            record("FAIL", name, f"unparseable SVG: {exc}")
            return
        w, h = length_px(root.get("width")), length_px(root.get("height"))
        if w is None or h is None:
            record("SKIP", name, "no absolute width/height - a viewBox alone has no size on paper")
            return
        if not math.isfinite(w) or not math.isfinite(h) or w <= 0 or h <= 0:
            record("FAIL", name, "width and height must be finite and positive")
            return
        pages = [(w / PX_PER_PT, h / PX_PER_PT)]
    elif ext == ".pdf":
        pages = pdf_pages_pt(path)
        if isinstance(pages, str):
            status, _, why = pages.partition(": ")
            record(status, name, why)
            return
    else:
        record("SKIP", name, "not an SVG or PDF")
        return
    over = [f"p{i} {w / PT_PER_MM:.1f} x {h / PT_PER_MM:.1f} mm"
            for i, (w, h) in enumerate(pages, 1)
            if w / PT_PER_MM > max_w + 0.05 or h / PT_PER_MM > max_h + 0.05]
    multi = f", {len(pages)} pages" if len(pages) > 1 else ""
    if over:
        record("FAIL", name, f"over {max_w:g} x {max_h:g} mm: {'; '.join(over)}{multi}")
    else:
        w0, h0 = pages[0][0] / PT_PER_MM, pages[0][1] / PT_PER_MM
        record("PASS", name, f"{w0:.1f} x {h0:.1f} mm (limit {max_w:g} x {max_h:g}){multi}")


# ================================================================================ SVG text
_TF = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def _mul(m1, m2):
    """Compose 2x2 linear maps stored as (a, b, c, d) = [[a, c], [b, d]]."""
    a1, b1, c1, d1 = m1
    a2, b2, c2, d2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2)


def linear_part(transform: str | None):
    """The linear part of an SVG transform list. Translation does not change size."""
    m = (1.0, 0.0, 0.0, 1.0)
    for name, args in _TF.findall(transform or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "matrix" and len(v) >= 4:
            t = (v[0], v[1], v[2], v[3])
        elif name == "scale" and v:
            t = (v[0], 0.0, 0.0, v[1] if len(v) > 1 else v[0])
        elif name == "rotate" and v:
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r))
        elif name == "skewX" and v:
            t = (1.0, 0.0, math.tan(math.radians(v[0])), 1.0)
        elif name == "skewY" and v:
            t = (1.0, math.tan(math.radians(v[0])), 0.0, 1.0)
        else:
            continue
        m = _mul(m, t)
    return m


def _declarations(el: ET.Element) -> dict[str, str]:
    decl = {}
    if el.get("font-size"):
        decl["font-size"] = el.get("font-size")
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            decl[k.strip().lower()] = v.strip()
    return decl


_KEYWORD_PX = {"xx-small": 9, "x-small": 10, "small": 13, "medium": 16, "large": 18,
               "x-large": 24, "xx-large": 32, "xxx-large": 48}
_SIZE_TOKEN = re.compile(r"[0-9]*\.?[0-9]+(px|pt|pc|in|cm|mm|q|em|rem|ex|%)", re.I)


def _font_size_token(decl: dict[str, str]) -> str | None:
    """This element's own font-size, from font-size or from the font shorthand.

    In the shorthand the size is the first token that carries a LENGTH UNIT (or is a size
    keyword). Weights such as 700 are unitless, which is how "font: 700 4px" is read as a
    4 px font rather than a 700 px one.
    """
    if "font-size" in decl:
        return decl["font-size"]
    if "font" in decl:
        for tok in decl["font"].split():
            tok = tok.split("/", 1)[0]            # "10px/1.2" -> "10px"
            if _SIZE_TOKEN.fullmatch(tok) or tok.lower() in _KEYWORD_PX:
                return tok
    return None


def _resolve_px(token: str, parent_px: float) -> float | None:
    t = token.strip().lower()
    if t in _KEYWORD_PX:
        return float(_KEYWORD_PX[t])
    m = _LEN.match(t)
    if not m:
        return None
    num, unit = float(m.group(1)), m.group(2).lower()
    if unit == "em":
        return num * parent_px
    if unit == "rem":
        return num * DEFAULT_FONT_PX
    if unit == "ex":
        return num * parent_px * 0.5
    if unit == "%":
        return num / 100.0 * parent_px
    return length_px(t)


def text_nodes(root: ET.Element):
    """(text, rendered size in pt or None) for every text node, plus what could not be resolved.

    The rendered size is the element's font-size -- inherited down the tree, with em and %
    relative to the parent -- times the scale of every ancestor transform, converted through
    the root's physical units. Reading the font-size string alone misses all three.
    """
    ptu = pt_per_user_unit(root)
    gaps: list[str] = []
    if ptu is None:
        gaps.append("SVG has no physical size, so no size on paper can be computed")
    for el in root.iter():
        if local(el.tag) == "style" and "font" in (el.text or ""):
            gaps.append("a <style> sheet sets fonts; class-based rules are not resolved here")
            break
    nodes: list[tuple[str, float | None]] = []

    def walk(el, parent_px, parent_lin):
        lin = _mul(parent_lin, linear_part(el.get("transform")))
        px = parent_px
        tok = _font_size_token(_declarations(el))
        if tok is not None:
            resolved = _resolve_px(tok, parent_px)
            if resolved is None:
                gaps.append(f"unresolved font-size {tok!r}")
            else:
                px = resolved
        if local(el.tag) in ("text", "tspan", "textPath") and (el.text or "").strip():
            scale = math.sqrt(abs(lin[0] * lin[3] - lin[1] * lin[2]))
            nodes.append(((el.text or "").strip()[:30], None if ptu is None else px * scale * ptu))
        for child in el:
            walk(child, px, lin)

    walk(root, DEFAULT_FONT_PX, (1.0, 0.0, 0.0, 1.0))
    return nodes, list(dict.fromkeys(gaps))


def glyph_uses(root: ET.Element) -> int:
    """<use> elements that reference a glyph outline: text drawn as paths.

    matplotlib's svg.fonttype='path' defines each glyph as a <path> whose id ends in
    -<hex codepoint> (DejaVuSans-41) and draws text by <use>-ing it.
    """
    kind = {el.get("id"): local(el.tag) for el in root.iter() if el.get("id")}
    n = 0
    for el in root.iter():
        if local(el.tag) == "use":
            target = (el.get(XLINK) or el.get("href") or "").lstrip("#")
            # A glyph-named target counts when it is a <path> -- or when it is not defined at
            # all, since a dangling glyph reference is still text that is not live. Only a
            # target defined as something else (a <g>, a <symbol>) is not a glyph.
            if re.search(r"^[A-Za-z][\w.]*-[0-9a-fA-F]{1,6}$", target) \
                    and kind.get(target, "path") == "path":
                n += 1
    return n


def cmd_text(path: Path, min_pt: float) -> None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        record("FAIL", f"live text {path.name}", f"unparseable SVG: {exc}")
        return
    nodes, gaps = text_nodes(root)
    glyphs = glyph_uses(root)
    if glyphs:
        # Any outlined glyph fails, even beside live text: one live label does not make an
        # outlined axis editable.
        record("FAIL", f"live text {path.name}",
               f"{glyphs} glyph(s) drawn as outlines beside {len(nodes)} live text node(s) - "
               f"set svg.fonttype='none'")
    elif nodes:
        record("PASS", f"live text {path.name}", f"{len(nodes)} live text node(s), no outlined glyphs")
    else:
        record("INFO", f"live text {path.name}", "no text in this SVG")
        return

    sized = [(t, pt) for t, pt in nodes if pt is not None]
    note = f"; not resolved: {'; '.join(gaps)}" if gaps else ""
    if not sized:
        record("SKIP", f"min font {path.name}", "no rendered size could be computed" + note)
        return
    lo_text, lo = min(sized, key=lambda x: x[1])
    if lo < min_pt - 1e-6:
        record("FAIL", f"min font {path.name}",
               f"rendered {lo:.2f} pt < {min_pt:g} pt, e.g. {lo_text!r}{note}")
    elif gaps:
        # Everything resolved is above the floor, but something was not resolved: that is an
        # unestablished result, not a pass.
        record("SKIP", f"min font {path.name}", f"smallest resolved {lo:.2f} pt{note}")
    else:
        dist = sorted({round(pt, 2) for _, pt in sized})
        record("PASS", f"min font {path.name}",
               f"smallest rendered {lo:.2f} pt (floor {min_pt:g}); sizes {dist[:8]}")


# ================================================================================ PDF fonts
def pdffonts_rows(out: str) -> list[dict[str, str]]:
    """Parse pdffonts by the column spans of its dashed rule.

    Splitting on whitespace breaks on multi-word types ('CID TrueType') and names with spaces;
    matching ' no ' anywhere reads the uni=no column as emb=no. Column spans avoid both.
    """
    lines = out.splitlines()
    rule = next((i for i, ln in enumerate(lines)
                 if ln.strip() and set(ln.replace(" ", "")) == {"-"}), None)
    if not rule:
        return []
    body = [ln for ln in lines[rule + 1:] if ln.strip()]
    spans = [(m.start(), m.end()) for m in re.finditer(r"-+", lines[rule])]
    header = [lines[rule - 1][a:b].strip().lower() for a, b in spans]
    if {"type", "emb"} <= set(header):
        return [dict(zip(header, [ln[a:(b if i < len(spans) - 1 else None)].strip()
                                  for i, (a, b) in enumerate(spans)])) for ln in body]
    # The rule did not give usable columns (other poppler builds, trimmed output). The last
    # six fields are fixed -- encoding emb sub uni object-number generation -- so read those
    # from the right; everything between the name and the encoding is the type.
    rows = []
    for ln in body:
        t = ln.split()
        if len(t) >= 8:
            rows.append({"name": t[0], "type": " ".join(t[1:-6]), "encoding": t[-6],
                         "emb": t[-5], "sub": t[-4], "uni": t[-3]})
    return rows


def cmd_fonts(path: Path) -> None:
    name = path.name
    if not shutil.which("pdffonts"):
        record("SKIP", f"fonts {name}",
               "pdffonts not installed - a byte scan cannot see compressed font objects")
        return
    q = run(["pdffonts", str(path)])
    if q is None:
        record("SKIP", f"fonts {name}", "pdffonts timed out")
        return
    if q.returncode != 0:
        record("FAIL", f"fonts {name}", "pdffonts could not read it: "
               + ((q.stderr or "").strip() or f"exit {q.returncode}")[:100])
        return
    if (q.stderr or "").strip():
        # Poppler prints "Syntax Error" for damage it recovers from; the listing still stands.
        record("INFO", f"pdffonts warnings {name}", q.stderr.strip().splitlines()[0][:100])
    rows = pdffonts_rows(q.stdout)
    if not rows:
        record("INFO", f"fonts {name}",
               "no fonts - no live text (raster-only, or outlined); confirm that is intended")
        return
    if not all("emb" in r and "type" in r for r in rows):
        record("SKIP", f"fonts {name}", "unrecognised pdffonts output")
        return
    not_emb = [r.get("name", "?") for r in rows if r["emb"].lower() != "yes"]
    type3 = [r.get("name", "?") for r in rows if r["type"].lower().startswith("type 3")]
    record("FAIL" if not_emb else "PASS", f"fonts embedded {name}",
           f"not embedded: {not_emb}" if not_emb else f"{len(rows)} font(s), all embedded")
    record("FAIL" if type3 else "PASS", f"font type {name}",
           f"Type 3: {type3} - set pdf.fonttype=42" if type3
           else f"no Type 3 ({', '.join(sorted({r['type'] for r in rows}))})")


# ================================================================================ raster
def cmd_export(path: Path, min_dpi: float, tiff_modes: list[str]) -> None:
    try:
        from PIL import Image
    except ImportError:
        record("SKIP", f"raster {path.name}", "Pillow not installed")
        return
    try:
        with Image.open(path) as im:
            mode, size, raw = im.mode, im.size, im.info.get("dpi")
            im.load()
    except Exception as exc:  # a file that does not open IS the finding
        record("FAIL", f"opens {path.name}", f"{type(exc).__name__}: {exc}")
        return
    record("PASS", f"opens {path.name}", f"{size[0]}x{size[1]} {mode}")
    if path.suffix.lower() in (".tif", ".tiff"):
        ok = mode in tiff_modes
        record("PASS" if ok else "FAIL", f"tiff mode {path.name}",
               mode + ("" if ok else f" - not in {tiff_modes}; flatten alpha, or pass the "
                                     f"contract's modes with --tiff-modes"))
    # TIFF reports dpi as PIL's IFDRational, which rejects a format spec; PNG as floats.
    dpi = tuple(float(v) for v in raw) if raw else None
    if not dpi:
        record("SKIP", f"dpi {path.name}", "no resolution recorded - print size unknown")
    else:
        record("PASS" if min(dpi) >= min_dpi - 0.5 else "FAIL", f"dpi {path.name}",
               f"{dpi[0]:.0f} x {dpi[-1]:.0f} (need >= {min_dpi:g} on both axes)")


# ================================================================================ video
def cmd_video(path: Path, thorough: bool, codec_want: str = "h264") -> None:
    name = path.name
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        record("SKIP", f"video {name}", "ffprobe/ffmpeg not installed")
        return
    q = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name,width,height,nb_frames,r_frame_rate:format=duration",
             "-of", "default=nw=1", str(path)])
    if q is None:
        record("SKIP", f"video opens {name}", "ffprobe timed out")
        return
    info = dict(ln.split("=", 1) for ln in q.stdout.splitlines() if "=" in ln)
    if q.returncode != 0 or "codec_name" not in info:
        record("FAIL", f"video opens {name}", (q.stderr or "no video stream").strip()[:120])
        return
    w = int(info["width"]) if info.get("width", "").isdigit() else 0
    h = int(info["height"]) if info.get("height", "").isdigit() else 0
    codec = info["codec_name"]
    nb = info.get("nb_frames", "N/A")
    record("PASS", f"video opens {name}",
           f"{w}x{h} {codec}, {nb if nb.isdigit() else 'unknown'} frames per container, "
           f"{info.get('duration', '?')} s")

    # Decode the first frame and the final second instead of every frame: cheap on a
    # several-hundred-MB file, and it proves both ends survive. --thorough decodes it all.
    probes = ([("full decode", [], [])] if thorough else
              [("first frame", [], ["-frames:v", "1"]), ("last second", ["-sseof", "-1"], [])])
    for label, in_opts, out_opts in probes:
        d = run(["ffmpeg", "-v", "error", *in_opts, "-i", str(path), *out_opts, "-f", "null", "-"],
                timeout=TOOL_TIMEOUT * (5 if thorough else 1))
        if d is None:
            record("SKIP", f"video {label} {name}", "decode timed out")
        elif d.returncode != 0 or (d.stderr or "").strip():
            record("FAIL", f"video {label} {name}", (d.stderr or "decode failed").strip()[:120])
        else:
            record("PASS", f"video {label} {name}", "decodes without error")

    # This sees the FILE. mp4v silently drops the last row/column of an odd frame while
    # writing, so a writer asked for 321x181 leaves an even 320x180 file that passes here.
    # A loss that has already happened is only visible by comparing requested and written
    # size at write time -- see failure-modes.md.
    if w <= 0 or h <= 0:
        record("SKIP", f"video parity {name}", "ffprobe reported no frame size")
    else:
        even = w % 2 == 0 and h % 2 == 0
        record("PASS" if even else "FAIL", f"video parity {name}",
               f"{w}x{h}" + ("" if even else " - odd size: yuv420p refuses it"))
    ok = codec == codec_want
    record("PASS" if ok else "FAIL", f"video codec {name}",
           codec + ("" if ok else f" - contract expects {codec_want}; pass --codec if it differs"))


# ================================================================================ stale
def _outputs(root: Path) -> list[Path]:
    return [p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in FIG_EXT | VIDEO_EXT | {".log"}
            and "__pycache__" not in p.parts and not p.name.startswith(".")]


def cmd_stale(out_dir: Path, generators: list[Path]) -> None:
    missing = [str(g) for g in generators if not g.exists()]
    if missing:
        record("FAIL", "generators exist", f"missing: {missing}")
    gens = [g for g in generators if g.exists()]
    if not gens:
        return
    newest = max(gens, key=lambda p: p.stat().st_mtime)
    t_gen = newest.stat().st_mtime
    outs = _outputs(out_dir)
    if not outs:
        record("SKIP", "stale (timestamp heuristic)", "no outputs found to compare")
        return
    old = sorted((p for p in outs if p.stat().st_mtime < t_gen), key=lambda p: p.stat().st_mtime)
    # Timestamps are a heuristic, not provenance: a comment-only edit to the generator trips
    # this, and a stale output that was copied or touched passes it. The label says so.
    if old:
        record("FAIL", "stale (timestamp heuristic)",
               f"{len(old)} of {len(outs)} output(s) older than {newest.name}, e.g. "
               f"{old[0].relative_to(out_dir)} - regenerate, or confirm the edit was cosmetic")
    else:
        record("PASS", "stale (timestamp heuristic)",
               f"all {len(outs)} output(s) newer than {newest.name}")
    logs = [p for p in outs if p.suffix.lower() == ".log"]
    figs = [p for p in outs if p.suffix.lower() in FIG_EXT | VIDEO_EXT]
    if not logs:
        record("INFO", "run log", "no .log alongside the figures - nothing records how they were made")
    elif figs:
        # A log opened before a long render legitimately predates its figures; 60 s is slack
        # for that, not a proof. Half-applied work shows as a log much older than its outputs.
        newest_fig = max(p.stat().st_mtime for p in figs)
        old_logs = [p.name for p in logs if p.stat().st_mtime < newest_fig - 60]
        record("FAIL" if old_logs else "PASS", "run log regenerated with figures",
               f"older than the figures they describe: {old_logs}" if old_logs
               else f"{len(logs)} log(s) current")


# ================================================================================ inventory
def cmd_inventory(root: Path, formats: list[str], expect: list[str]) -> None:
    want = {"tiff" if f.lower().lstrip(".") == "tif" else f.lower().lstrip(".") for f in formats}
    stems: dict[str, set[str]] = {}
    for p in root.rglob("*"):
        if (p.is_file() and p.suffix.lower() in FIG_EXT and "__pycache__" not in p.parts
                and not p.name.startswith(".")):
            ext = p.suffix.lower().lstrip(".")
            stem = p.relative_to(root).with_suffix("").as_posix()
            stems.setdefault(stem, set()).add("tiff" if ext == "tif" else ext)
            if p.stat().st_size == 0:
                record("FAIL", f"non-empty {p.name}", "0 bytes")
    for stem in expect:
        miss = want - stems.get(stem, set())
        record("FAIL" if miss else "PASS", f"expected {stem}",
               f"missing {sorted(miss)}" if miss else f"{sorted(stems[stem])}")
    intermediates = []
    for stem, have in sorted(stems.items()):
        if stem in expect:
            continue
        if len(have & want) >= 2:
            # Two or more export formats means this stem is a figure being exported, so a
            # partial set is a missing export rather than an intermediate.
            miss = want - have
            record("FAIL" if miss else "PASS", f"formats {stem}",
                   f"have {sorted(have)}, missing {sorted(miss)}" if miss else f"{sorted(have)}")
        else:
            intermediates.append(stem)
    if intermediates:
        record("INFO", "single-format files",
               f"{len(intermediates)} not checked for a format set (e.g. {intermediates[0]}); "
               f"name the real figures with --expect")
    if not stems:
        record("INFO", "inventory", f"no figure files under {root}")
    readmes = list(root.rglob("README.md"))
    record("INFO", "README", f"{len(readmes)} found" if readmes
           else "none - a figure should say how it was made")


# ================================================================================ svgdiff
_URL = re.compile(r"""url\(\s*(['"]?)#([^)'"]+)\1\s*\)""")


def normalise_svg(text: str) -> list[str]:
    """Re-serialise an SVG with every id renamed to its order of definition.

    One name per definition, not one shared placeholder: two renders of the same figure get
    identical names, while a reference that moves from one shape to another still points at a
    different name, so the change stays visible. Only id-valued attributes and their
    references are touched -- visible text can never be normalised away -- and only metadata
    dates are blanked.
    """
    root = ET.fromstring(text)
    ids = [el.attrib["id"] for el in root.iter() if "id" in el.attrib]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate SVG ids - references are ambiguous")
    names = {old: f"audit-id-{i}" for i, old in enumerate(ids)}
    for el in root.iter():
        if el.tag == "{http://purl.org/dc/elements/1.1/}date":
            el.text = ""
        for key, value in list(el.attrib.items()):
            if key == "id":
                value = names[value]
            elif key in ("href", XLINK) and value.startswith("#"):
                value = "#" + names.get(value[1:], value[1:])
            value = _URL.sub(lambda m: f"url(#{names.get(m.group(2), m.group(2))})", value)
            el.attrib[key] = value
    return ET.tostring(root, encoding="unicode").splitlines()


def cmd_svgdiff(a: Path, b: Path) -> None:
    try:
        la, lb = normalise_svg(a.read_text()), normalise_svg(b.read_text())
    except (ET.ParseError, ValueError, UnicodeError) as exc:
        record("FAIL", "svg parse", str(exc))
        return
    diff = [ln for ln in difflib.unified_diff(la, lb, lineterm="", n=0)
            if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    if not diff:
        record("PASS", "svg identical modulo ids/dates", "no differences")
        return
    telling = next((ln for ln in diff if re.search(r">[^<]*[A-Za-z0-9][^<]*<", ln)), None)
    if telling:
        inner = re.search(r">([^<]*[A-Za-z0-9][^<]*)<", telling).group(1).strip()
        example = f"{telling.lstrip()[0]}text {inner[:80]!r}"
    else:
        example = diff[0].strip()[:110]
    record("FAIL", "svg identical modulo ids/dates", f"{len(diff)} differing line(s), e.g. {example}")


# ================================================================================ all
def cmd_all(root: Path, a: argparse.Namespace) -> None:
    print(f"== inventory: {root}")
    cmd_inventory(root, a.formats.split(","), a.expect)
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        if ext in FIG_EXT or ext in VIDEO_EXT:
            print(f"== {p.relative_to(root)}")
        if ext == ".svg":
            cmd_geometry(p, a.max_width_mm, a.max_height_mm)
            cmd_text(p, a.min_pt)
        elif ext == ".pdf":
            cmd_geometry(p, a.max_width_mm, a.max_height_mm)
            cmd_fonts(p)
        elif ext in (".tif", ".tiff", ".png"):
            cmd_export(p, a.min_dpi, a.tiff_modes.split(","))
        elif ext in VIDEO_EXT:
            cmd_video(p, a.thorough, a.codec)
    print("== staleness")
    if a.generator:
        cmd_stale(root, a.generator)
    else:
        record("SKIP", "stale (timestamp heuristic)",
               "no --generator given - outputs were not checked against their code")


def summarise(allow_skip: bool) -> int:
    n = {s: sum(1 for r in RESULTS if r[0] == s) for s in ("PASS", "FAIL", "SKIP", "INFO")}
    print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped, {n['INFO']} info")
    if n["FAIL"]:
        return 1
    if n["PASS"] == 0:
        print("INCOMPLETE: nothing was checked.")
        return 3
    if n["SKIP"]:
        print("INCOMPLETE: skipped checks were NOT run. Report them as gaps, not passes.")
        return 0 if allow_skip else 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--allow-skip", action="store_true",
                        help="exit 0 despite SKIPs; state the gaps in the report")
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name):
        return sub.add_parser(name, parents=[common])

    def lim(sp):
        sp.add_argument("--max-width-mm", type=float, default=180.0)
        sp.add_argument("--max-height-mm", type=float, default=247.0)

    g = cmd("geometry"); g.add_argument("file", type=Path); lim(g)
    t = cmd("text"); t.add_argument("file", type=Path)
    t.add_argument("--min-pt", type=float, default=5.5)
    f = cmd("fonts"); f.add_argument("file", type=Path)
    e = cmd("export"); e.add_argument("file", type=Path)
    e.add_argument("--min-dpi", type=float, default=300.0)
    e.add_argument("--tiff-modes", default=TIFF_MODES)
    v = cmd("video"); v.add_argument("file", type=Path)
    v.add_argument("--thorough", action="store_true", help="decode every frame")
    v.add_argument("--codec", default="h264")
    s = cmd("stale"); s.add_argument("dir", type=Path)
    s.add_argument("generators", type=Path, nargs="+")
    i = cmd("inventory"); i.add_argument("dir", type=Path)
    i.add_argument("--formats", default="svg,pdf,png,tiff")
    i.add_argument("--expect", action="append", default=[], metavar="STEM")
    d = cmd("svgdiff"); d.add_argument("a", type=Path); d.add_argument("b", type=Path)
    a = cmd("all"); a.add_argument("dir", type=Path)
    a.add_argument("--generator", type=Path, action="append", default=[])
    a.add_argument("--expect", action="append", default=[], metavar="STEM")
    a.add_argument("--min-pt", type=float, default=5.5)
    a.add_argument("--min-dpi", type=float, default=300.0)
    a.add_argument("--formats", default="svg,pdf,png,tiff")
    a.add_argument("--tiff-modes", default=TIFF_MODES)
    a.add_argument("--codec", default="h264")
    a.add_argument("--thorough", action="store_true", help="decode every video frame"); lim(a)
    return p


def main(argv: list[str] | None = None) -> int:
    RESULTS.clear()
    args = build_parser().parse_args(argv)
    for attr in ("file", "dir", "a", "b"):
        path = getattr(args, attr, None)
        if isinstance(path, Path) and not path.exists():
            print(f"no such path: {path}", file=sys.stderr)
            return 2
        if isinstance(path, Path) and ((attr == "dir" and not path.is_dir())
                                      or (attr != "dir" and not path.is_file())):
            print(f"expected {'directory' if attr == 'dir' else 'file'}: {path}", file=sys.stderr)
            return 2
    {
        "geometry": lambda: cmd_geometry(args.file, args.max_width_mm, args.max_height_mm),
        "text": lambda: cmd_text(args.file, args.min_pt),
        "fonts": lambda: cmd_fonts(args.file),
        "export": lambda: cmd_export(args.file, args.min_dpi, args.tiff_modes.split(",")),
        "video": lambda: cmd_video(args.file, args.thorough, args.codec),
        "stale": lambda: cmd_stale(args.dir, args.generators),
        "inventory": lambda: cmd_inventory(args.dir, args.formats.split(","), args.expect),
        "svgdiff": lambda: cmd_svgdiff(args.a, args.b),
        "all": lambda: cmd_all(args.dir, args),
    }[args.cmd]()
    return summarise(args.allow_skip)


if __name__ == "__main__":
    sys.exit(main())
