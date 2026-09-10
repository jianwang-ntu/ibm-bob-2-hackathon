#!/usr/bin/env python3
"""Controls for evidence/cover_image.png -- the required cover image.

A cover image is the first thing a judge sees and the least checkable artifact
in a submission: a PDF has a text stream, a PNG has none, so a number printed on
one is normally read by a human and by nothing else.  This suite treats the
SHIPPED PNG PIXELS as the thing under test.

  figures    ACCEPT every figure on the cover is re-derived HERE from
             ../slides/evidence/*.json, matches what the sidecar says is drawn,
             and is FOUND IN THE PIXELS; REJECT a corrupted figure at both
             steps, and REJECT the cover going stale when the EVIDENCE moves
  honesty    ACCEPT the cover carries the absences the entry must state -- no
             IBM Bob 2.0, nothing DISCRIMINATING, no demo URL or video;
             REJECT the ledger being cut or softened
  absent     ACCEPT the pixel matcher can say NOT FOUND, measured on decoys
  bytes      ACCEPT the shipped PNG is exactly what make_cover.py produces from
             today's evidence, is a PNG, and is 1920x1080 = 16:9 exactly;
             REJECT a sidecar sha256 that does not match the file
  layout     ACCEPT the build's own layout check found nothing; REJECT a
             deliberately overlapping layout going unreported

HOW A STRING IS FOUND IN A RASTER.  Every string on the cover sits at an integer
pixel origin, which makes its rasterisation position-independent.  So this file
renders the string itself, crops it to its ink, and slides it over the shipped
image under zero-mean normalised cross-correlation.  NCC is invariant to the
affine intensity map between "white on black" here and "muted grey on a panel"
there, so the template does not need to know what colour the cover drew it in.

The figure strings are RE-DERIVED in this file rather than imported from the
builder: two implementations that have to agree.  The corruptions are derived
from the artifact rather than pinned to literals, so they keep corrupting after
the measurements move -- and a corruption that changes nothing is reported BAD
rather than credited.

  python3 check_cover.py

Needs matplotlib, numpy and Pillow.  A missing one is a FAILURE, not a skip: a
control that quietly does not run is worse than no control.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SRC_EV = HERE.parent / "slides" / "evidence"
EV = HERE / "evidence"
PNG = EV / "cover_image.png"
SIDECAR = EV / "cover_image.json"

# Bars.  PRESENT is an EXACT-MATCH bar and that is the point: the template is
# produced by the same renderer at an integer pixel origin, so a string that is
# really on the cover matches its own rasterisation exactly and scores 1.0.
#
# The first version of this file set PRESENT to 0.98 and the suite FAILED --
# correctly.  Changing one character of a 100-character line moves NCC only to
# 0.9952 / 0.9939 / 0.9823, so a loose bar cannot tell a true absence line from
# a doctored one.  A near-miss is not evidence that the string is there; it is
# evidence that something LIKE it is.  The bar is the separation.
PRESENT = 0.9995      # at or above -> the exact rasterisation is in the pixels
ABSENT = 0.90         # below -> not on the cover at all
MARGIN = 0.0          # kept at zero: the discriminator is exactness, not a gap

results: list[dict] = []


def check(name: str, ok: bool, detail) -> bool:
    results.append({"control": name, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return bool(ok)


# ------------------------------------------------------------------ evidence
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

    Re-derived here on purpose: `mutants_applied` counts runs where the check
    never executed, and printing a kill count over THAT denominator is the exact
    defect the audited project documents having made once.
    """
    return c["mutants_applied"] - c["mutants_did_not_run"]


def figures_from_evidence(e: dict) -> list[tuple[str, str]]:
    """(label prefix, string) for every figure the cover may print."""
    s, d12, repo = e["self"], e["demo12"], e["repo"]
    real12 = pick(d12, "real_suite_verifies_pricing")
    vac12 = pick(d12, "vacuous_suite_verifies_pricing")
    worst = min(s["claims"], key=lambda c: c["mutants_killed"] / evidential(c))
    return [
        ("panel0_head", f"{real12['mutants_killed']} / {evidential(real12)}"
                        f"   vs   {vac12['mutants_killed']} / "
                        f"{evidential(vac12)}"),
        ("panel0_label", "mutants killed: a real suite vs a vacuous one"),
        ("panel0_caption", "pytest calls both suites green."),
        ("panel1_head", f"{s['summary']['weak']} of {s['summary']['total']}"
                        f"  WEAK"),
        ("panel1_label", f"this repository's own claims, "
                         f"{s['summary']['discriminating']} DISCRIMINATING"),
        ("panel1_caption", f"worst: {worst['claim_id']} "
                           f"{worst['mutants_killed']} / {evidential(worst)}."),
        ("panel2_head", f"{repo['tests_passed_in_clone']} tests pass"),
        ("panel2_label", f"{repo['tracked_files']} tracked files, "
                         f"{repo['module_count']} modules, anonymous clone"),
        ("panel2_caption", f"at {repo['head'][:8]}, {repo['licence']} licensed, "
                           f"{len(repo['distinct_commit_authors'])} commit "
                           f"author."),
    ]


def absences_from_evidence(e: dict) -> list[tuple[str, str]]:
    s = e["self"]
    return [
        ("no_bob", "Not built yet: IBM Bob 2.0 has not been used on this "
                   "project. Access opens at kickoff and nothing here claims "
                   "otherwise."),
        ("no_discriminating", f"Nothing in this repository's own audit is "
                              f"DISCRIMINATING: {s['summary']['weak']} of "
                              f"{s['summary']['total']} claims are WEAK."),
        ("no_demo_url", "No hosted demo URL and no video yet: both need "
                        "accounts this entry does not hold."),
    ]


def corrupt(claim: str) -> str:
    """Break a claim the way a stale cover breaks: bump its first number.

    Derived from the claim, not pinned to a literal, so it keeps corrupting
    after the measurements move.  A claim with no number has two adjacent
    differing characters transposed -- dropping the last word is useless,
    because a prefix of a true sentence is still on the image.
    """
    m = re.search(r"\d+", claim)
    if m:
        return claim[:m.start()] + str(int(m.group()) + 1) + claim[m.end():]
    body = claim.rstrip()
    for i in range(len(body) - 1, 0, -1):
        if body[i] != body[i - 1] and not body[i].isspace() \
                and not body[i - 1].isspace():
            return body[:i - 1] + body[i] + body[i - 1] + body[i + 1:]
    return body + "X"


# -------------------------------------------------------------- the pixels
def load_gray(path: pathlib.Path):
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        fmt, size = im.format, im.size
        return np.asarray(im.convert("L"), dtype=np.float64), fmt, size


def render_template(s: str, size: float, weight: str):
    """Rasterise one string, white on black, cropped to its ink."""
    import io
    import os
    import numpy as np
    os.environ.setdefault("SOURCE_DATE_EPOCH", "1757000000")
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.family"] = "DejaVu Sans"
    import matplotlib.pyplot as plt
    from PIL import Image

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor("#000000")
    fig.text(200 / 1920, 1.0 - 500 / 1080, s, color="#FFFFFF", fontsize=size,
             fontweight=weight, ha="left", va="baseline")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    with Image.open(io.BytesIO(buf.getvalue())) as im:
        a = np.asarray(im.convert("L"), dtype=np.float64)
    ys, xs = np.nonzero(a > 8)
    if len(ys) == 0:
        return None
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


class Matcher:
    """Zero-mean normalised cross-correlation of a template over one image.

    NCC is invariant to the affine intensity map between the template's
    white-on-black and the cover's own colours, so a template never has to be
    told what colour it was drawn in.
    """

    def __init__(self, img):
        import numpy as np
        self.np = np
        self.img = img
        self.H, self.W = img.shape
        self.F = np.fft.rfft2(img)
        self.F2 = np.fft.rfft2(img * img)

    def _boxsum(self, F, h, w):
        np = self.np
        ones = np.zeros((self.H, self.W))
        ones[:h, :w] = 1.0
        return np.fft.irfft2(F * np.conj(np.fft.rfft2(ones)),
                             s=(self.H, self.W))

    def best(self, tpl) -> float:
        np = self.np
        h, w = tpl.shape
        if h > self.H or w > self.W:
            return -1.0
        t0 = tpl - tpl.mean()
        tnorm = float(np.sqrt((t0 * t0).sum()))
        if tnorm == 0:
            return -1.0
        pad = np.zeros((self.H, self.W))
        pad[:h, :w] = t0
        num = np.fft.irfft2(self.F * np.conj(np.fft.rfft2(pad)),
                            s=(self.H, self.W))
        s1 = self._boxsum(self.F, h, w)
        s2 = self._boxsum(self.F2, h, w)
        n = h * w
        var = s2 - (s1 * s1) / n
        var[var < 1e-9] = 1e-9
        ncc = num / (tnorm * np.sqrt(var))
        valid = ncc[:self.H - h + 1, :self.W - w + 1]
        return float(valid.max())


def lines_for(sidecar: dict, prefix: str) -> list[dict]:
    pat = re.compile(rf"^{re.escape(prefix)}(_\d+)?$")
    return [p for p in sidecar["placed"] if pat.match(p["label"])]


# ------------------------------------------------------------------- main
def main() -> int:
    for mod in ("matplotlib", "numpy", "PIL"):
        try:
            __import__(mod)
        except ImportError as exc:
            check(f"dependency_{mod}", False, f"{exc} -- controls cannot run")
            return 1
    check("dependencies", True, "matplotlib, numpy and Pillow all import")

    e = load_evidence(SRC_EV)
    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    raw = PNG.read_bytes()

    # ------------------------------------------------------------ bytes
    digest = hashlib.sha256(raw).hexdigest()
    check("sidecar_sha256_matches_file",
          digest == sidecar["sha256"] and len(raw) == sidecar["bytes"],
          f"{digest[:16]}... {len(raw):,} bytes")

    img, fmt, (w_px, h_px) = load_gray(PNG)
    check("format_is_png", fmt == "PNG", f"PIL reports {fmt}")
    check("aspect_ratio_is_16_9_exactly",
          w_px * 9 == h_px * 16 and (w_px, h_px) == (1920, 1080),
          f"{w_px}x{h_px}, {w_px}*9 == {h_px}*16 -> {w_px * 9 == h_px * 16}")

    # ------------------------------------------------- figures in the pixels
    figs = figures_from_evidence(e)
    absents = absences_from_evidence(e)
    matcher = Matcher(img)

    def declared(prefix):
        items = lines_for(sidecar, prefix)
        return items, " ".join(i["text"] for i in items)

    bad_join, missing_decl = [], []
    for prefix, truth in figs + absents:
        items, joined = declared(prefix)
        if not items:
            missing_decl.append(prefix)
        elif joined != truth:
            bad_join.append((prefix, joined, truth))
    check("sidecar_declares_every_figure", not missing_decl,
          f"{len(figs) + len(absents)} figures, all present in placed[]"
          if not missing_decl else f"absent: {missing_decl}")
    check("declared_text_equals_evidence", not bad_join,
          f"{len(figs) + len(absents)} of {len(figs) + len(absents)} strings "
          f"re-derived here match what the sidecar says was drawn"
          if not bad_join else f"{bad_join[:2]}")

    scores, not_found = {}, []
    for prefix, _ in figs + absents:
        for item in lines_for(sidecar, prefix):
            tpl = render_template(item["text"], item["size"], item["weight"])
            s = matcher.best(tpl) if tpl is not None else -1.0
            scores[item["label"]] = s
            if s < PRESENT:
                not_found.append((item["label"], round(s, 4)))
    check("every_figure_is_in_the_shipped_pixels", not not_found,
          f"{len(scores)} rendered lines located, min NCC "
          f"{min(scores.values()):.4f} against a bar of {PRESENT}"
          if not not_found else f"below bar: {not_found}")

    # ------------------------------------------------- negative: corruptions
    survived_join, survived_pixels, noop = [], [], []
    corrupt_scores = {}
    for prefix, truth in figs + absents:
        bad = corrupt(truth)
        if bad == truth:
            noop.append(prefix)
            continue
        _, joined = declared(prefix)
        if joined == bad:
            survived_join.append(prefix)
        items = lines_for(sidecar, prefix)
        target = max(items, key=lambda i: len(i["text"]))
        bad_line = corrupt(target["text"])
        if bad_line == target["text"]:
            noop.append(f"{prefix}:line")
            continue
        tpl = render_template(bad_line, target["size"], target["weight"])
        s = matcher.best(tpl) if tpl is not None else -1.0
        true_s = scores[target["label"]]
        corrupt_scores[prefix] = round(s, 6)
        if not (s < PRESENT and s < true_s - MARGIN):
            survived_pixels.append((prefix, round(s, 4), round(true_s, 4)))
    check("no_corruption_was_a_no_op", not noop,
          f"{len(figs) + len(absents)} corruptions all changed their string"
          if not noop else f"no-op: {noop}")
    check("corrupted_figure_rejected_by_the_text_control", not survived_join,
          "every bumped figure disagrees with the sidecar"
          if not survived_join else f"survived: {survived_join}")
    check("corrupted_figure_rejected_by_the_pixel_control",
          not survived_pixels,
          f"{len(corrupt_scores)} corrupted lines all score below {PRESENT}; "
          f"worst {max(corrupt_scores.values()):.4f} against a true line at "
          f"{min(scores.values()):.4f}"
          if not survived_pixels else f"survived: {survived_pixels}")

    # ------------------------------------------- negative: the matcher can say no
    decoys = [
        ("plausible_but_absent", "Benchmarked against 12 competing tools."),
        ("bob_was_used", "Built with IBM Bob 2.0 during the hackathon."),
        ("inflated_verdict", "5 of 5 DISCRIMINATING"),
    ]
    loud = []
    for label, s in decoys:
        tpl = render_template(s, 20, "normal")
        v = matcher.best(tpl) if tpl is not None else -1.0
        if v >= ABSENT:
            loud.append((label, round(v, 4)))
    check("matcher_reports_absent_strings_as_absent", not loud,
          f"{len(decoys)} decoys all below {ABSENT}"
          if not loud else f"matched anyway: {loud}")

    # --------------------------------------------------------- the absences
    # This control used to be "every absence label appears in placed[]", which
    # is a SUBSET of what sidecar_declares_every_figure already checks -- so it
    # could never be the control that failed, and the mutation campaign proved
    # it: cutting an absence line killed the mutant on the other control every
    # time.  A control that cannot fail on its own is the exact defect this
    # project exists to find, so it is given an independent job here: an
    # absence has to be DRAWN LEGIBLY, inside the ledger block, at a size a
    # judge can read.  Shrinking the ledger to 4pt keeps every other control
    # green and is caught only here.
    strip = next((b for b in sidecar.get("boxes", [])
                  if b["name"] == "absences"), None)
    illegible = []
    for lab, _ in absents:
        for it in lines_for(sidecar, lab):
            if it["size"] < 16:
                illegible.append((it["label"], "size", it["size"]))
            elif strip is None:
                illegible.append((it["label"], "no absences box declared", None))
            elif not (strip["x0"] <= it["x_px"] <= strip["x1"]
                      and strip["y0"] <= it["y_px"] <= strip["y1"]):
                illegible.append((it["label"], "outside the ledger block",
                                  (it["x_px"], it["y_px"])))
    check("absence_ledger_is_drawn_legibly", not illegible,
          f"{sum(len(lines_for(sidecar, l)) for l, _ in absents)} ledger lines, "
          f"all >= 16pt and inside the declared ledger block"
          if not illegible else f"{illegible}")

    # ------------------------------------------------------------- layout
    check("build_layout_check_found_nothing",
          sidecar.get("layout_violations") == [],
          f"layout_violations = {sidecar.get('layout_violations')}")

    sys.path.insert(0, str(HERE))
    import make_cover                                             # noqa: E402
    make_cover.tracked = [
        {"label": "a", "extent": {"x0": 200, "x1": 400, "y0": 200, "y1": 240},
         "owner": None},
        {"label": "b", "extent": {"x0": 300, "x1": 500, "y0": 210, "y1": 250},
         "owner": None},
        {"label": "c", "extent": {"x0": -50, "x1": 40, "y0": 900, "y1": 940},
         "owner": None},
    ]
    make_cover.boxes = []
    make_cover.violations = []
    make_cover.check_layout()
    kinds = {v["kind"] for v in make_cover.violations}
    check("layout_check_fires_on_a_broken_layout",
          {"text_on_text", "off_page"} <= kinds,
          f"synthetic overlap and off-page both reported: {sorted(kinds)}")

    # ------------------------------------------------ bytes tie to the builder
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = pathlib.Path(tmp) / "cover"
        if sandbox.exists():
            check("rebuild_sandbox_is_empty", False, "sandbox already exists")
            return 1
        sandbox.mkdir(parents=True)
        (sandbox / "make_cover.py").write_bytes(
            (HERE / "make_cover.py").read_bytes())
        slides_ev = sandbox.parent / "slides" / "evidence"
        slides_ev.mkdir(parents=True)
        for n in ("self_audit.json", "demo_audit_12.json", "demo_audit_4.json",
                  "repo_state.json"):
            (slides_ev / n).write_bytes((SRC_EV / n).read_bytes())
        p = subprocess.run([sys.executable, "make_cover.py"], cwd=sandbox,
                           capture_output=True, text=True, timeout=900)
        rebuilt = sandbox / "evidence" / "cover_image.png"
        ok = p.returncode == 0 and rebuilt.exists()
        redigest = hashlib.sha256(rebuilt.read_bytes()).hexdigest() if ok else ""
        check("rebuild_from_todays_evidence_is_byte_identical",
              ok and redigest == digest,
              f"rc={p.returncode} sha256 {redigest[:16]}... "
              f"{'==' if redigest == digest else '!='} shipped"
              + ("" if ok else f" stderr={p.stderr.strip()[:300]}"))

    check("cover_is_pinned_to_the_measured_repo_head",
          sidecar.get("built_from_head") == e["repo"]["head"],
          f"{str(sidecar.get('built_from_head'))[:8]} vs repo_state "
          f"{e['repo']['head'][:8]}")

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    (EV / "cover_controls.json").write_text(json.dumps({
        "schema": "cover_controls/v1",
        "png_sha256": digest,
        "bars": {"present_ncc": PRESENT, "absent_ncc": ABSENT,
                 "corruption_margin": MARGIN},
        "ncc_scores": {k: round(v, 6) for k, v in sorted(scores.items())},
        "ncc_scores_corrupted": dict(sorted(corrupt_scores.items())),
        "separation": ("true lines rasterise identically and score 1.0; a "
                       "one-character corruption of the longest line in each "
                       "figure scores strictly below the PRESENT bar"),
        "passed": passed, "total": total, "all_pass": passed == total,
        "controls": results,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} controls passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
