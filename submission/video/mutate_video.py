#!/usr/bin/env python3
"""Mutation campaign against check_video.py.

The entry this belongs to is a tool that asks of a check: can it ever go red?
It would be indefensible for that entry's own controls to be unfalsifiable, so
this file answers the same question about them, the same way the tool does --
by breaking the artifact and requiring the named control to notice.

Four guards, taken directly from the audited tool's own design:

  1  GREEN BASELINE.  The unmutated tree must pass first.  A campaign layered
     on a suite that was already red scores 100% for free.
  2  SANDBOX REFUSES AN EXISTING DIRECTORY.  A copy that nests itself one level
     deeper leaves the checker reading a stale tree -- which is where false
     100%s actually come from.
  3  A MUTANT THAT CHANGES NOTHING IS REPORTED BAD, not credited.
  4  EVERY CONTROL KILLED BY AT LEAST ONE MUTANT is asserted separately.  A
     mutant killing its named control does not prove the OTHER controls can
     fail; only coverage does.

Each mutant names the control it is aimed at.  Controls it also kills are
reported rather than suppressed: the sidecar is a shared input, so some
corruptions legitimately trip more than one control, and hiding that would be
its own kind of dishonesty.

  python3 mutate_video.py

Runs the fast control groups (bytes, replay, pixels, honesty).  `live` re-runs
the captured commands against a fresh network clone and `build` re-encodes the
whole video; both are exercised by check_video.py itself on every full run and
are too slow to mutate dozens of times.  That limit is stated, not hidden.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
GROUPS = "bytes,replay,pixels,honesty"

# Controls this campaign does NOT falsify with a mutant, and why.  Written down
# so that a reader can see the campaign's edge rather than infer a clean sweep.
NOT_MUTATED = {
    "accept_size_is_under_the_published_300mb_cap":
        "falsifying it needs a >300 MB artifact; the shipped file is 3.0 MB and "
        "the cap is read off the real file every run",
    "matcher_reports_absent_strings_as_absent":
        "this IS the refusal arm for the pixel control; it fires on three real "
        "decoys every run and reports their scores",
    "a_one_character_change_does_not_reach_the_present_bar":
        "same -- it measures the separation on a live corruption every run",
    "accept_captures_reproduce_in_a_fresh_clone": "in the `live` group, not run here",
    "rebuild_from_todays_captures_reproduces_the_shipped_bytes":
        "in the `build` group, not run here",
}


def run_checks(root: pathlib.Path) -> dict[str, bool]:
    r = subprocess.run([sys.executable, "check_video.py", "--groups", GROUPS],
                       cwd=root, capture_output=True, text=True, timeout=1800)
    out = {}
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith("[PASS] ") or line.startswith("[FAIL] "):
            name = line[7:].split(":", 1)[0].strip()
            out[name] = line.startswith("[PASS] ")
    if not out:
        raise SystemExit(f"the suite produced no control lines:\n{r.stdout[-800:]}"
                         f"\n{r.stderr[-800:]}")
    return out


def sandbox() -> pathlib.Path:
    """Guard 2: a fresh directory that must not already exist."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mutvid_"))
    dst = tmp / "video"
    if dst.exists():
        raise SystemExit("sandbox refuses an existing directory")
    shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    slides = tmp / "slides" / "evidence"
    shutil.copytree(HERE.parent / "slides" / "evidence", slides,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return dst


# ------------------------------------------------------------------ mutants
def _sidecar(root: pathlib.Path) -> tuple[pathlib.Path, dict]:
    p = root / "evidence" / "video_presentation.json"
    return p, json.loads(p.read_text(encoding="utf-8"))


def _write(p: pathlib.Path, sc: dict) -> None:
    p.write_text(json.dumps(sc, indent=1, ensure_ascii=False) + "\n",
                 encoding="utf-8")


def m_sha256_bumped(root):
    p, sc = _sidecar(root)
    sc["sha256"] = sc["sha256"][:-1] + ("0" if sc["sha256"][-1] != "0" else "1")
    _write(p, sc)


def m_has_audio_true(root):
    p, sc = _sidecar(root)
    sc["has_audio"] = True
    _write(p, sc)


def m_capture_line_doctored(root):
    p, sc = _sidecar(root)
    for c in sc["cues"]:
        if c["kind"] == "terminal":
            c["capture_line"] = c["capture_line"].replace("passed", "pasted") \
                if "passed" in c["capture_line"] else c["capture_line"] + " X"
            break
    _write(p, sc)


def m_capture_file_emptied(root):
    (root / "evidence" / "captures" / "self_scan.txt").write_text("", encoding="utf-8")


def m_cue_frame_shifted(root):
    """Point a checkable string at a frame that does not show it."""
    p, sc = _sidecar(root)
    frames = sorted({c["frame"] for c in sc["cues"] if c["checkable_in_pixels"]})
    for c in sc["cues"]:
        if c["kind"] == "terminal" and c["checkable_in_pixels"]:
            c["frame"] = frames[0] if c["frame"] != frames[0] else frames[-1]
            break
    _write(p, sc)


def m_ledger_row_shrunk(root):
    p, sc = _sidecar(root)
    for c in sc["cues"]:
        if c["kind"] == "absence":
            c["size"] = 8
            break
    _write(p, sc)


def m_ledger_item_dropped(root):
    p, sc = _sidecar(root)
    victims = [c for c in sc["cues"] if c["kind"] == "absence"]
    drop = victims[-1]
    sc["cues"] = [c for c in sc["cues"] if c is not drop]
    _write(p, sc)


def m_bob_absence_removed(root):
    p, sc = _sidecar(root)
    sc["cues"] = [c for c in sc["cues"] if c["kind"] != "bob_absence"]
    _write(p, sc)


def m_bob_usage_claimed(root):
    p, sc = _sidecar(root)
    src = [c for c in sc["cues"] if c["kind"] == "card"][0]
    planted = dict(src)
    planted["text"] = "Every module here was built with IBM Bob 2.0 in Agent mode."
    planted["checkable_in_pixels"] = False
    sc["cues"].append(planted)
    _write(p, sc)


def m_retired_claim_restored(root):
    p, sc = _sidecar(root)
    for c in sc["cues"]:
        if c["kind"] == "absence" and "hosted demo URL" in c["text"]:
            c["text"] = "No hosted demo URL and no video yet: both need accounts."
            c["checkable_in_pixels"] = False
            break
    _write(p, sc)


def m_container_remuxed(root):
    """Same frames, wrong container -- the format control alone should notice."""
    mp4 = root / "evidence" / "video_presentation.mp4"
    tmp = mp4.with_suffix(".mkv")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(mp4), "-c", "copy", str(tmp)], check=True)
    tmp.replace(mp4)


def m_frame_squashed(root):
    """Re-encode at 1600x1080, which is no longer 16:9."""
    mp4 = root / "evidence" / "video_presentation.mp4"
    tmp = mp4.with_name("squashed.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(mp4), "-vf", "scale=1600:1080", "-t", "200",
                    "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p",
                    str(tmp)], check=True)
    tmp.replace(mp4)


def m_duration_cut(root):
    """A 60-second cut is under the Rule Book's own 3-minute band."""
    mp4 = root / "evidence" / "video_presentation.mp4"
    tmp = mp4.with_name("cut.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(mp4), "-t", "60", "-c", "copy", str(tmp)], check=True)
    tmp.replace(mp4)


MUTANTS = [
    ("sha256_bumped", m_sha256_bumped,
     "accept_sidecar_sha256_matches_the_shipped_file"),
    ("has_audio_true", m_has_audio_true,
     "accept_no_audio_stream_and_the_sidecar_says_silent"),
    ("capture_line_doctored", m_capture_line_doctored,
     "accept_every_terminal_cue_joins_to_its_capture_byte_exactly"),
    ("capture_file_emptied", m_capture_file_emptied,
     "accept_every_named_capture_exists_and_is_not_empty"),
    ("cue_frame_shifted", m_cue_frame_shifted,
     "accept_every_declared_string_is_in_the_shipped_pixels"),
    ("ledger_row_shrunk", m_ledger_row_shrunk, "absence_ledger_is_drawn_legibly"),
    ("ledger_item_dropped", m_ledger_item_dropped,
     "accept_the_videos_ledger_rejoins_the_decks_ledger_exactly"),
    ("bob_absence_removed", m_bob_absence_removed,
     "accept_the_bob_absence_is_stated_and_located_in_the_pixels"),
    ("bob_usage_claimed", m_bob_usage_claimed,
     "reject_a_claim_that_bob_2_0_was_used"),
    ("retired_claim_restored", m_retired_claim_restored,
     "reject_the_retired_no_video_yet_claim_in_the_drawn_ledger"),
    ("container_remuxed", m_container_remuxed,
     "accept_container_is_the_mandatory_mp4_h264"),
    ("frame_squashed", m_frame_squashed, "accept_frame_is_16_9_exactly"),
    ("duration_cut", m_duration_cut,
     "accept_duration_inside_the_published_window"),
]


def main() -> int:
    # Guard 1: green baseline, asserted BEFORE anything is mutated.
    base_root = sandbox()
    baseline = run_checks(base_root)
    shutil.rmtree(base_root.parent, ignore_errors=True)
    red = [k for k, v in baseline.items() if not v]
    print(f"baseline: {sum(baseline.values())}/{len(baseline)} controls pass")
    if red:
        print(f"REFUSING -- baseline is already red on {red}; a campaign on a "
              f"red baseline scores for free")
        return 1

    rows, killed_by = [], {k: [] for k in baseline}
    for name, apply, target in MUTANTS:
        root = sandbox()
        try:
            apply(root)
            got = run_checks(root)
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
        now_failing = sorted(k for k, v in got.items()
                             if not v and baseline.get(k, True))
        for k in now_failing:
            killed_by[k].append(name)
        verdict = ("BAD -- changed nothing" if not now_failing else
                   "KILLED" if target in now_failing else
                   "MISSED ITS TARGET")
        rows.append({"mutant": name, "target": target, "verdict": verdict,
                     "controls_that_went_red": now_failing,
                     "also_killed": [k for k in now_failing if k != target]})
        extra = [k for k in now_failing if k != target]
        print(f"[{verdict:18}] {name:24} -> {target}"
              + (f"   (also: {len(extra)})" if extra else ""))

    killed = sum(1 for r in rows if r["verdict"] == "KILLED")
    unfalsified = sorted(k for k, v in killed_by.items()
                         if not v and k not in NOT_MUTATED)
    print(f"\n{killed}/{len(rows)} mutants killed on their NAMED control")
    print(f"{sum(1 for v in killed_by.values() if v)}/{len(killed_by)} controls "
          f"were driven red by at least one mutant")
    for k, why in NOT_MUTATED.items():
        if k in killed_by and not killed_by[k]:
            print(f"    not mutated: {k} -- {why}")
    if unfalsified:
        print(f"UNFALSIFIED CONTROLS (no mutant, no stated reason): {unfalsified}")

    (HERE / "evidence" / "video_mutants.json").write_text(
        json.dumps({"baseline_green": True, "groups": GROUPS,
                    "mutants": rows, "killed_on_target": killed,
                    "total": len(rows), "killed_by": killed_by,
                    "not_mutated_and_why": NOT_MUTATED,
                    "unfalsified": unfalsified},
                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if killed == len(rows) and not unfalsified else 1


if __name__ == "__main__":
    sys.exit(main())
