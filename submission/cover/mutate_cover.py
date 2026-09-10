#!/usr/bin/env python3
"""Mutation campaign for check_cover.py -- does the suite have teeth?

A suite that passes proves nothing on its own; this project exists because of
that.  So each mutant below is a way the cover could be wrong that a judge would
not see, applied to an ISOLATED FULL COPY of the tree, with the baseline
asserted GREEN in that copy first.  A mutant is KILLED if check_cover.py comes
back non-zero AND the control named in `expect` is the one that failed.

  python3 mutate_cover.py

Each sandbox REFUSES to be an existing directory: copying a tree into a
directory that already holds one nests it, the stale copy runs, and every mutant
comes back killed for the wrong reason.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SUB = HERE.parent                      # submission/  (cover + slides evidence)


def sandbox(root: pathlib.Path) -> pathlib.Path:
    dst = root / "submission"
    if dst.exists():
        raise SystemExit(f"sandbox {dst} already exists -- refusing to nest")
    shutil.copytree(SUB, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst / "cover"


def run(cover: pathlib.Path):
    p = subprocess.run([sys.executable, "check_cover.py"], cwd=cover,
                       capture_output=True, text=True, timeout=1800)
    failed = [ln.split(":")[0].replace("[FAIL] ", "").strip()
              for ln in p.stdout.splitlines() if ln.startswith("[FAIL]")]
    return p.returncode, failed, p.stdout


# ------------------------------------------------------------------ mutants
def m_hand_edit_png(c):
    p = c / "evidence" / "cover_image.png"
    b = bytearray(p.read_bytes())
    b[-40] ^= 0x01
    p.write_bytes(bytes(b))


def m_falsify_sidecar_text(c):
    p = c / "evidence" / "cover_image.json"
    d = json.loads(p.read_text())
    for it in d["placed"]:
        if it["label"] == "panel2_head":
            it["text"] = it["text"].replace("64", "640")
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def m_inflate_and_rebuild(c):
    p = c / "make_cover.py"
    p.write_text(p.read_text().replace(
        '"self_headline": (f"{s[\'summary\'][\'weak\']} of {s[\'summary\'][\'total\']}"\n'
        '                          f"  WEAK"),',
        '"self_headline": (f"{s[\'summary\'][\'total\']} of {s[\'summary\'][\'total\']}"\n'
        '                          f"  DISCRIMINATING"),'))
    subprocess.run([sys.executable, "make_cover.py"], cwd=c, check=True,
                   capture_output=True, timeout=900)


def m_cut_an_absence(c):
    p = c / "make_cover.py"
    p.write_text(p.read_text().replace(
        'for key in ("no_bob", "no_discriminating", "no_demo_url"):',
        'for key in ("no_bob", "no_discriminating"):'))
    subprocess.run([sys.executable, "make_cover.py"], cwd=c, check=True,
                   capture_output=True, timeout=900)


def m_evidence_moves_under_the_cover(c):
    p = c.parent / "slides" / "evidence" / "repo_state.json"
    d = json.loads(p.read_text())
    d["tests_passed_in_clone"] += 1
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def m_paint_out_a_figure(c):
    """Blank the pixels of one figure and re-stamp the sidecar's digest.

    Isolates the PIXEL arm: the sidecar still says the number is drawn, its
    sha256 still matches the file, and only a control that reads the raster can
    notice that the number is gone.
    """
    import hashlib
    import numpy as np
    from PIL import Image
    png = c / "evidence" / "cover_image.png"
    side = json.loads((c / "evidence" / "cover_image.json").read_text())
    it = [i for i in side["placed"] if i["label"] == "panel2_head"][0]
    with Image.open(png) as im:
        a = np.array(im.convert("RGB"))
    x, y = it["x_px"], it["y_px"]
    a[max(0, y - 60):y + 12, x:x + 460] = np.array([20, 28, 40], dtype=a.dtype)
    Image.fromarray(a).save(png)
    side["sha256"] = hashlib.sha256(png.read_bytes()).hexdigest()
    side["bytes"] = png.stat().st_size
    (c / "evidence" / "cover_image.json").write_text(
        json.dumps(side, indent=1, ensure_ascii=False) + "\n")


def m_shrink_the_absence_ledger(c):
    """Keep every absence, at a size nobody reads.

    Every other control stays green: the strings are still declared, still
    match the evidence, and still render into the pixels.  Only a control that
    asks whether the ledger is LEGIBLE can see this one.
    """
    p = c / "make_cover.py"
    p.write_text(p.read_text().replace(
        'text(fig, f"{key}_{k}", line, MARGIN + 34, y, 19, TEXT,',
        'text(fig, f"{key}_{k}", line, MARGIN + 34, y, 4, TEXT,'))
    subprocess.run([sys.executable, "make_cover.py"], cwd=c, check=True,
                   capture_output=True, timeout=900)


def m_disarm_the_layout_check(c):
    p = c / "make_cover.py"
    p.write_text(p.read_text().replace(
        "def check_layout():\n    for t in tracked:",
        "def check_layout():\n    return\n    for t in tracked:"))


def m_squash_the_aspect_ratio(c):
    from PIL import Image
    import hashlib
    png = c / "evidence" / "cover_image.png"
    with Image.open(png) as im:
        im.convert("RGB").resize((1920, 1000)).save(png)
    p = c / "evidence" / "cover_image.json"
    side = json.loads(p.read_text())
    side["sha256"] = hashlib.sha256(png.read_bytes()).hexdigest()
    side["bytes"] = png.stat().st_size
    p.write_text(json.dumps(side, indent=1, ensure_ascii=False) + "\n")


MUTANTS = [
    ("hand_edited_png", m_hand_edit_png, "sidecar_sha256_matches_file"),
    ("sidecar_text_falsified", m_falsify_sidecar_text,
     "declared_text_equals_evidence"),
    ("inflated_verdict_rebuilt", m_inflate_and_rebuild,
     "declared_text_equals_evidence"),
    # Cutting a whole absence is caught by the DECLARATION control, not the
    # legibility one -- measured, and the reason the legibility control was
    # rewritten to have a job of its own.  The expectation is recorded as what
    # actually fires, not as what would have been tidier.
    ("absence_line_cut", m_cut_an_absence, "sidecar_declares_every_figure"),
    ("absence_ledger_shrunk_to_4pt", m_shrink_the_absence_ledger,
     "absence_ledger_is_drawn_legibly"),
    ("evidence_moved_under_the_cover", m_evidence_moves_under_the_cover,
     "declared_text_equals_evidence"),
    ("figure_painted_out_of_the_pixels", m_paint_out_a_figure,
     "every_figure_is_in_the_shipped_pixels"),
    ("layout_check_disarmed", m_disarm_the_layout_check,
     "layout_check_fires_on_a_broken_layout"),
    ("aspect_ratio_squashed", m_squash_the_aspect_ratio,
     "aspect_ratio_is_16_9_exactly"),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = sandbox(pathlib.Path(tmp) / "baseline")
        rc, failed, out = run(base)
        if rc != 0:
            print(out)
            print("BASELINE IS NOT GREEN -- every kill below would be a lie")
            return 1
        print(f"[BASELINE] green in an isolated copy, {len(failed)} failures\n")

    killed, survived, wrong = [], [], []
    for name, apply, expect in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            c = sandbox(pathlib.Path(tmp) / name)
            apply(c)
            rc, failed, out = run(c)
            if rc == 0:
                survived.append(name)
                verdict = "SURVIVED"
            elif expect in failed:
                killed.append(name)
                verdict = f"killed by {expect}"
            else:
                wrong.append((name, expect, failed))
                verdict = f"died on the WRONG control: {failed}"
            print(f"[{'KILL' if rc and expect in failed else 'MISS'}] "
                  f"{name}: {verdict}")

    print(f"\n{len(killed)}/{len(MUTANTS)} killed on the named control; "
          f"{len(survived)} survived; {len(wrong)} died elsewhere")
    (HERE / "evidence" / "cover_mutants.json").write_text(json.dumps({
        "schema": "cover_mutants/v1",
        "baseline_asserted_green_first": True,
        "killed": killed, "survived": survived,
        "died_on_another_control": wrong,
        "total": len(MUTANTS),
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if len(killed) == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
