#!/usr/bin/env python3
"""Build the cover image the lablab submission form requires.

  "Cover Image: Use PNG or JPG format with 16:9 aspect ratio."
      -- lablab.ai Hackathon Rule Book, "Cover Image and Presentation"
      (rules_canonical_20260909T2300Z/rulebook.body.txt)

  The Submission Guidelines say "recommended 16:9 ratio".  The two surfaces
  disagree on whether 16:9 is mandatory or advisory; this builds 16:9, which
  is the reading AGAINST us.

The cover is GENERATED, not authored.  Every figure on it is read out of
../slides/evidence/*.json at build time -- the auditor's own report files and
one measured readback of the public repository -- and check_cover.py re-derives
the same figures independently, then looks for them in the SHIPPED PNG PIXELS.

That is not decoration.  This project's whole argument is that a claim nothing
can falsify is not evidence, so a cover whose numbers no control reads would be
the exact failure the tool exists to find.

TEXT IN A PNG HAS NO TEXT STREAM.  A PDF can be checked by extracting its text;
a raster image cannot.  So every string is placed at an INTEGER PIXEL position,
which makes its rasterisation position-independent (measured: the same string
rendered at two different integer origins crops to bit-identical ink).  The
checker re-renders each string it derived and finds it in the shipped pixels by
exact-ink template match.

  python3 make_cover.py     # -> evidence/cover_image.png
                            #    evidence/cover_image.json

Deterministic: SOURCE_DATE_EPOCH is pinned below, so two builds from the same
evidence produce byte-identical PNGs -- which is how check_cover.py ties the
shipped bytes to this builder.  Needs matplotlib.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

os.environ.setdefault("SOURCE_DATE_EPOCH", "1757000000")

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "DejaVu Sans"
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.patches import Rectangle                         # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SRC_EV = HERE.parent / "slides" / "evidence"     # single source of truth
EV = HERE / "evidence"
PNG = EV / "cover_image.png"
SIDECAR = EV / "cover_image.json"

W, H, DPI = 1920, 1080, 100                      # 1920/1080 == 16/9 exactly
BG = "#0A0D12"
PANEL = "#141C28"
RULE = "#22303F"
ACCENT = "#6FC3C6"
TEXT = "#E9EEF3"
MUTED = "#93A2B1"
WARN = "#E2A24A"

EVENT = "IBM Bob 2.0 Hackathon | lablab.ai | 2026-09-25 to 2026-09-27"
REPO = "github.com/jianwang-ntu/ibm-bob-2-hackathon"

placed: list[dict] = []          # every string, for the sidecar and the checker


# --------------------------------------------------------------- evidence
def load_evidence(ev: pathlib.Path) -> dict:
    j = lambda n: json.loads((ev / n).read_text(encoding="utf-8"))
    return {
        "self": j("self_audit.json"),
        "demo12": j("demo_audit_12.json"),
        "demo4": j("demo_audit_4.json"),
        "repo": j("repo_state.json"),
    }


def pick(report: dict, claim_id: str) -> dict:
    hits = [c for c in report["claims"] if c["claim_id"] == claim_id]
    if len(hits) != 1:
        raise KeyError(f"{claim_id}: {len(hits)} matches")
    return hits[0]


def evidential(c: dict) -> int:
    """Denominator the kill count was measured against.

    `mutants_applied` counts runs in which the check never executed.  Printing
    a kill count over THAT denominator is the exact defect this project
    documents having made once, so it is re-derived rather than read.
    """
    return c["mutants_applied"] - c["mutants_did_not_run"]


def figures(e: dict) -> dict:
    """Every number the cover is allowed to print, derived from evidence."""
    s, d12, repo = e["self"], e["demo12"], e["repo"]
    real12 = pick(d12, "real_suite_verifies_pricing")
    vac12 = pick(d12, "vacuous_suite_verifies_pricing")
    worst = min(s["claims"], key=lambda c: c["mutants_killed"] / evidential(c))
    return {
        "demo_split": (f"{real12['mutants_killed']} / {evidential(real12)}"
                       f"   vs   {vac12['mutants_killed']} / {evidential(vac12)}"),
        "demo_label": "mutants killed: a real suite vs a vacuous one",
        "demo_caption": "pytest calls both suites green.",
        "self_headline": (f"{s['summary']['weak']} of {s['summary']['total']}"
                          f"  WEAK"),
        "self_label": (f"this repository's own claims, "
                       f"{s['summary']['discriminating']} DISCRIMINATING"),
        "self_caption": (f"worst: {worst['claim_id']} "
                         f"{worst['mutants_killed']} / {evidential(worst)}."),
        "repo_headline": f"{repo['tests_passed_in_clone']} tests pass",
        "repo_label": (f"{repo['tracked_files']} tracked files, "
                       f"{repo['module_count']} modules, anonymous clone"),
        "repo_caption": (f"at {repo['head'][:8]}, {repo['licence']} licensed, "
                         f"{len(repo['distinct_commit_authors'])} commit author."),
    }


def absences(e: dict) -> dict:
    """The absences the cover is required to carry, so it cannot oversell."""
    s = e["self"]
    return {
        "no_bob": ("Not built yet: IBM Bob 2.0 has not been used on this "
                   "project. Access opens at kickoff and nothing here claims "
                   "otherwise."),
        "no_discriminating": (f"Nothing in this repository's own audit is "
                              f"DISCRIMINATING: {s['summary']['weak']} of "
                              f"{s['summary']['total']} claims are WEAK."),
        "no_demo_url": ("No hosted demo URL: deploying one needs an account "
                        "this entry does not hold."),
    }


# ------------------------------------------------------------------ layout
# Measured, not eyeballed.  The first draft of this file put three panel
# captions on top of each other and ran a fourth off the right edge of the
# page; all of it was geometrically legal to a builder that never measured.
tracked: list[dict] = []          # every artist, in pixels, for the check
boxes: list[dict] = []            # every background block, likewise
violations: list[dict] = []
MARGIN = 96


def _renderer(fig):
    return fig.canvas.get_renderer()


def _extent(fig, artist):
    """Pixel bbox of a text artist, top-left origin, in cover coordinates."""
    bb = artist.get_window_extent(renderer=_renderer(fig))
    return {"x0": bb.x0, "x1": bb.x1, "y0": H - bb.y1, "y1": H - bb.y0}


def measure(fig, s, size, weight):
    """Width in pixels of a string, with the real font metrics."""
    t = fig.text(0, 0, s, fontsize=size, fontweight=weight)
    bb = t.get_window_extent(renderer=_renderer(fig))
    t.remove()
    return bb.width


def wrap(fig, s, size, weight, max_px):
    """Greedy wrap on the measured width, never on a guessed character count."""
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and measure(fig, trial, size, weight) > max_px:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _overlap(a, b):
    return not (a["x1"] <= b["x0"] or b["x1"] <= a["x0"]
                or a["y1"] <= b["y0"] or b["y1"] <= a["y0"])


def check_layout():
    for t in tracked:
        e = t["extent"]
        if e["x0"] < MARGIN - 2 or e["x1"] > W - MARGIN + 2 \
                or e["y0"] < 0 or e["y1"] > H:
            violations.append({"kind": "off_page", "label": t["label"],
                               "extent": e})
        owner = t.get("owner")
        for b in boxes:
            inside_x = e["x0"] >= b["x0"] - 1 and e["x1"] <= b["x1"] + 1
            inside_y = e["y0"] >= b["y0"] - 1 and e["y1"] <= b["y1"] + 1
            if b["name"] == owner and not (inside_x and inside_y):
                violations.append({"kind": "escapes_its_panel",
                                   "label": t["label"], "panel": b["name"],
                                   "extent": e})
            if b["name"] != owner and _overlap(e, b) \
                    and not (inside_x and inside_y):
                violations.append({"kind": "straddles_a_panel_edge",
                                   "label": t["label"], "panel": b["name"],
                                   "extent": e})
    for i in range(len(tracked)):
        for j in range(i + 1, len(tracked)):
            if _overlap(tracked[i]["extent"], tracked[j]["extent"]):
                violations.append({"kind": "text_on_text",
                                   "labels": [tracked[i]["label"],
                                              tracked[j]["label"]]})


# ----------------------------------------------------------------- drawing
def text(fig, label, s, xpx, ypx, size, color, weight="normal", ha="left",
         va="baseline", owner=None):
    """Place a string at an INTEGER pixel position and record it.

    The integer origin is what makes the rasterisation reproducible outside
    this file: check_cover.py renders the same string at its own origin and
    the ink comes out bit-identical.
    """
    xpx, ypx = int(xpx), int(ypx)
    art = fig.text(xpx / W, 1.0 - ypx / H, s, color=color, fontsize=size,
                   fontweight=weight, ha=ha, va=va)
    placed.append({"label": label, "text": s, "x_px": xpx, "y_px": ypx,
                   "size": size, "color": color, "weight": weight,
                   "ha": ha, "va": va})
    tracked.append({"label": label, "extent": _extent(fig, art),
                    "owner": owner})


def panel(fig, name, xpx, ypx, wpx, hpx, face=PANEL):
    fig.patches.append(Rectangle((xpx / W, 1.0 - (ypx + hpx) / H),
                                 wpx / W, hpx / H, transform=fig.transFigure,
                                 facecolor=face, edgecolor=RULE, linewidth=1.2,
                                 zorder=0))
    boxes.append({"name": name, "x0": xpx, "x1": xpx + wpx,
                  "y0": ypx, "y1": ypx + hpx})


def build(e: dict) -> None:
    f, a = figures(e), absences(e)

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.patch.set_facecolor(BG)

    # accent rule across the top
    fig.patches.append(Rectangle((0, 1.0 - 10 / H), 1.0, 10 / H,
                                 transform=fig.transFigure, facecolor=ACCENT,
                                 edgecolor="none", zorder=1))

    text(fig, "title", "Vacuity Auditor", 96, 186, 92, TEXT, weight="bold")
    text(fig, "subtitle", "Can this check ever go red?", 96, 272, 42, ACCENT)
    text(fig, "framing",
         "It audits the check, not the code the check is pointed at.",
         96, 328, 25, MUTED)

    # three measured panels
    px, pw, gap = MARGIN, 554, 33
    ptop, ph, pad = 372, 286, 28
    inner = pw - 2 * pad
    for i, (head, lab, cap) in enumerate([
        (f["demo_split"], f["demo_label"], f["demo_caption"]),
        (f["self_headline"], f["self_label"], f["self_caption"]),
        (f["repo_headline"], f["repo_label"], f["repo_caption"]),
    ]):
        x = px + i * (pw + gap)
        name = f"panel{i}"
        panel(fig, name, x, ptop, pw, ph)
        size = 40
        while measure(fig, head, size, "bold") > inner and size > 20:
            size -= 1
        text(fig, f"{name}_head", head, x + pad, ptop + 84, size, TEXT,
             weight="bold", owner=name)
        y = ptop + 134
        for k, line in enumerate(wrap(fig, lab, 20, "normal", inner)):
            text(fig, f"{name}_label_{k}", line, x + pad, y, 20, ACCENT,
                 owner=name)
            y += 28
        y += 12
        for k, line in enumerate(wrap(fig, cap, 18, "normal", inner)):
            text(fig, f"{name}_caption_{k}", line, x + pad, y, 18, MUTED,
                 owner=name)
            y += 26

    # the absence strip: checked, so it cannot be quietly cut
    strip_w = W - 2 * MARGIN
    panel(fig, "absences", MARGIN, 710, strip_w, 196, face="#16110C")
    text(fig, "absence_head", "What this entry does not have",
         MARGIN + 34, 754, 22, WARN, weight="bold", owner="absences")
    y = 792
    for key in ("no_bob", "no_discriminating", "no_demo_url"):
        lines = wrap(fig, a[key], 19, "normal", strip_w - 68)
        for k, line in enumerate(lines):
            text(fig, f"{key}_{k}", line, MARGIN + 34, y, 19, TEXT,
                 owner="absences")
            y += 26
        y += 8

    text(fig, "event", EVENT, MARGIN, 968, 20, MUTED)
    text(fig, "repo", REPO, MARGIN, 1000, 20, MUTED)
    text(fig, "entrant",
         "Solo entry - Wang Jian - every line of code written by an "
         "autonomous AI coding agent", MARGIN, 1038, 18, MUTED)

    check_layout()
    if violations:
        for v in violations:
            print(f"LAYOUT {v['kind']}: {v.get('label') or v.get('labels')}",
                  file=sys.stderr)
        raise SystemExit(f"{len(violations)} layout violations -- refusing to "
                         f"write a cover with text off the page or on top of "
                         f"other text")

    EV.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, format="png", dpi=DPI, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    e = load_evidence(SRC_EV)
    build(e)

    raw = PNG.read_bytes()
    sidecar = {
        "schema": "cover_image/v1",
        "png": "submission/cover/evidence/cover_image.png",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "width_px": W,
        "height_px": H,
        "aspect_ratio": "16:9",
        "aspect_ratio_exact": W * 9 == H * 16,
        "dpi": DPI,
        "requirement": ("lablab Hackathon Rule Book, \"Cover Image and "
                        "Presentation\": \"Cover Image: Use PNG or JPG format "
                        "with 16:9 aspect ratio.\""),
        "cross_surface_note": ("The Submission Guidelines say \"recommended "
                               "16:9 ratio\" where the Rule Book says use it. "
                               "Built 16:9, the reading against us."),
        "title": "Vacuity Auditor: can this check ever go red?",
        "event": EVENT,
        "repo": REPO,
        "built_by": "submission/cover/make_cover.py",
        "built_from_head": e["repo"]["head"],
        "source_date_epoch": os.environ["SOURCE_DATE_EPOCH"],
        "deterministic": ("SOURCE_DATE_EPOCH is pinned, so two builds from the "
                          "same evidence produce byte-identical PNGs."),
        "figures_derived_from": ["../slides/evidence/self_audit.json",
                                 "../slides/evidence/demo_audit_12.json",
                                 "../slides/evidence/demo_audit_4.json",
                                 "../slides/evidence/repo_state.json"],
        "integer_pixel_origins": ("Every string sits at an integer pixel "
                                  "origin, which is what makes the ink "
                                  "reproducible by an independent renderer."),
        "boxes": boxes,
        "layout_violations": violations,
        "layout_check": ("every string is measured with the real font metrics; "
                         "off-page, text-on-text, escaping its own panel and "
                         "straddling another panel's edge all fail the build"),
        "placed": placed,
    }
    SIDECAR.write_text(json.dumps(sidecar, indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"wrote {PNG}  {len(raw):,} bytes  {W}x{H}  "
          f"sha256 {sidecar['sha256']}")
    print(f"wrote {SIDECAR}  {len(placed)} strings recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
