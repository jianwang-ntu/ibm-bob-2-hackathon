#!/usr/bin/env python3
"""Controls for evidence/video_presentation.mp4 -- the required video presentation.

A video is the least checkable artifact in a submission and the one a judge
weights most heavily.  A PDF has a text stream; a PNG has none but has one
frame; an MP4 has none and has five thousand.  Nothing downstream reads it, so
a terminal session that never ran would be seen by a human and by no control at
all.  On an entry whose whole subject is checks that cannot go red, that would
be exactly the defect the tool exists to find.

So this suite treats THE SHIPPED MP4 as the thing under test, on six axes, each
with its own refusal arm:

  bytes    ACCEPT the container, duration, frame size, silence and file size are
           what the published limits require and what the sidecar says
  replay   ACCEPT every terminal line drawn in the video is a byte-exact line of
           the capture its cue names; REJECT a line that is not
  pixels   ACCEPT each declared string is FOUND IN THE DECODED FRAME its cue
           names, by exact-ink template match; REJECT decoys, so the matcher is
           shown able to say NOT FOUND
  honesty  ACCEPT the absence ledger is drawn in full, legibly, and rejoins the
           deck's own ledger exactly; ACCEPT the IBM Bob 2.0 absence is stated
           AND located in the pixels; REJECT any claim that Bob 2.0 was used
  live     ACCEPT the captures still reproduce -- the commands are re-run HERE,
           in a fresh credential-free clone, and their return codes and output
           compared; REJECT a capture whose command now answers differently
  build    ACCEPT the shipped bytes are what make_video.py produces from today's
           captures, rebuilt in a sandbox that refuses an existing directory

HOW A STRING IS FOUND IN A FRAME.  Every string in the video sits at an integer
pixel origin, which makes its rasterisation position-independent.  This file
re-renders the string with the same font and size, white on black, crops it to
its ink, and slides it over the decoded frame under zero-mean normalised
cross-correlation.  NCC is invariant to the affine intensity map between the
template's white-on-black and the frame's own colours, so a template never has
to be told what colour it was drawn in.

The bar is EXACTNESS, not similarity.  A one-character change in a real line
still scores far above any unrelated string, so a loose bar could not tell a
true line from a doctored one.  Both numbers are measured on every run.

  python3 check_video.py                    # all six groups
  python3 check_video.py --groups bytes     # for the mutation campaign only

Needs numpy, Pillow, ffmpeg, ffprobe and git.  A missing one is a FAILURE, not
a skip: a control that quietly does not run is worse than no control.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
EV = HERE / "evidence"
CAP = EV / "captures"
MP4 = EV / "video_presentation.mp4"
SIDECAR = EV / "video_presentation.json"
SLIDE_EV = HERE.parent / "slides" / "evidence"

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
REPO_URL = "https://github.com/jianwang-ntu/ibm-bob-2-hackathon.git"

PRESENT = 0.9995      # at or above -> that exact rasterisation is in the frame
ABSENT = 0.90         # below -> not in that frame at all
MIN_LEDGER_PT = 20    # legibility floor the ledger control enforces
MIN_S, MAX_S = 180.0, 300.0
MAX_BYTES = 300 * 1024 * 1024

results: list[dict] = []


def check(name: str, ok: bool, detail) -> bool:
    results.append({"control": name, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return bool(ok)


# ---------------------------------------------------------------- rendering
def render_template(s: str, font_name: str, size: int):
    """Rasterise one string white on black with the SHIPPED font, cropped to
    its ink.  Re-implemented here rather than imported from make_video.py:
    two implementations that have to agree."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    f = ImageFont.truetype(f"{FONT_DIR}/{font_name}", size)
    img = Image.new("L", (1920, 240), 0)
    ImageDraw.Draw(img).text((40, 60), s, font=f, fill=255)
    a = np.asarray(img, dtype=np.float64)
    ys, xs = np.nonzero(a > 8)
    if len(ys) == 0:
        return None
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


class Matcher:
    """Zero-mean normalised cross-correlation of a template over one frame."""

    def __init__(self, img):
        import numpy as np
        self.np = np
        self.H, self.W = img.shape
        self.F = np.fft.rfft2(img)
        self.F2 = np.fft.rfft2(img * img)

    def _boxsum(self, F, h, w):
        np = self.np
        ones = np.zeros((self.H, self.W))
        ones[:h, :w] = 1.0
        return np.fft.irfft2(F * np.conj(np.fft.rfft2(ones)), s=(self.H, self.W))

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
        num = np.fft.irfft2(self.F * np.conj(np.fft.rfft2(pad)), s=(self.H, self.W))
        s1 = self._boxsum(self.F, h, w)
        s2 = self._boxsum(self.F2, h, w)
        n = h * w
        var = s2 - (s1 * s1) / n
        var[var < 1e-9] = 1e-9
        ncc = num / (tnorm * np.sqrt(var))
        return float(ncc[:self.H - h + 1, :self.W - w + 1].max())


_frames: dict[int, object] = {}


def frame(n: int):
    """Decode one frame of the SHIPPED mp4 as greyscale."""
    import numpy as np
    from PIL import Image
    if n in _frames:
        return _frames[n]
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "f.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(MP4), "-vf", f"select=eq(n\\,{n})",
                        "-vsync", "0", "-frames:v", "1", str(out)], check=True)
        with Image.open(out) as im:
            a = np.asarray(im.convert("L"), dtype=np.float64)
    _frames[n] = a
    return a


def wrap_mono(line: str, cols: int = 132, indent: str = "    ") -> list[str]:
    if len(line) <= cols:
        return [line]
    out, rest = [line[:cols]], line[cols:]
    while rest:
        out.append(indent + rest[:cols - len(indent)])
        rest = rest[cols - len(indent):]
    return out


def corrupt(s: str) -> str:
    """Derive a corruption FROM the string, so it keeps corrupting after the
    measurements move.  A corruption that changes nothing is caught by the
    control that uses it, not credited."""
    digits = [i for i, ch in enumerate(s) if ch.isdigit()]
    if digits:
        i = digits[0]
        return s[:i] + str((int(s[i]) + 1) % 10) + s[i + 1:]
    letters = [i for i, ch in enumerate(s) if ch.isalpha()]
    i = letters[len(letters) // 2]
    return s[:i] + ("x" if s[i] != "x" else "y") + s[i + 1:]


# ------------------------------------------------------------------- checks
def c_bytes(sc: dict) -> None:
    data = MP4.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    check("accept_sidecar_sha256_matches_the_shipped_file",
          digest == sc["sha256"] and len(data) == sc["bytes"],
          f"{len(data):,} bytes, sha256 {digest[:16]}...")
    check("accept_size_is_under_the_published_300mb_cap",
          len(data) <= MAX_BYTES,
          f"{len(data) / 1024 / 1024:.2f} MB against a 300 MB cap")

    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
         "-show_streams", str(MP4)], capture_output=True, text=True,
        check=True).stdout)
    vid = [s for s in probe["streams"] if s["codec_type"] == "video"]
    aud = [s for s in probe["streams"] if s["codec_type"] == "audio"]

    check("accept_container_is_the_mandatory_mp4_h264",
          "mp4" in probe["format"]["format_name"] and vid[0]["codec_name"] == "h264",
          f'{probe["format"]["format_name"]} / {vid[0]["codec_name"]} -- the Rule '
          f'Book says "MP4 and PDF formats are mandatory"')

    dur = float(probe["format"]["duration"])
    check("accept_duration_inside_the_published_window",
          MIN_S <= dur < MAX_S,
          f"{int(dur // 60)}:{dur % 60:04.1f} inside [3:00, 5:00) -- the Guidelines "
          f"cap 5 min, Rule Book criterion 1 band 2 penalises under 3 min")

    w, h = int(vid[0]["width"]), int(vid[0]["height"])
    check("accept_frame_is_16_9_exactly", w * 9 == h * 16, f"{w}x{h}: {w}*9 == {h}*16")

    # Silence is asserted BOTH ways: no audio stream in the file, and the
    # sidecar saying so.  A narrated video would be a different artifact and
    # nothing downstream may imply this one has any narration.
    check("accept_no_audio_stream_and_the_sidecar_says_silent",
          not aud and sc["has_audio"] is False and sc["silent"] is True,
          f"{len(aud)} audio streams; sidecar has_audio={sc['has_audio']}")


def c_replay(sc: dict) -> None:
    """Every terminal line drawn is a byte-exact line of its named capture."""
    term = [c for c in sc["cues"] if c["kind"] == "terminal"]
    caps = {n: (CAP / f"{n}.txt").read_text(encoding="utf-8").splitlines()
            for n in {c["source"] for c in term}}

    def joins(cue: dict) -> bool:
        return (cue["capture_line"] in caps[cue["source"]]
                and wrap_mono(cue["capture_line"])[0] == cue["text"])

    ok = [c for c in term if joins(c)]
    check("accept_every_terminal_cue_joins_to_its_capture_byte_exactly",
          len(ok) == len(term) and bool(term),
          f"{len(ok)} of {len(term)} terminal cues found byte-exactly in "
          f"{len(caps)} capture files")

    # BOTH ARMS IN ONE CONTROL.  The mutation campaign caught the first version
    # of this: it asserted only that a CORRUPTED line fails to join, which no
    # corruption of the artifact can ever falsify -- a refusal arm with no
    # accept arm is a check that cannot go red.  It now also requires the
    # uncorrupted line to join, and the corruption to have changed something.
    victim = dict(term[0])
    victim["capture_line"] = corrupt(victim["capture_line"])
    changed = victim["capture_line"] != term[0]["capture_line"]
    check("reject_a_terminal_line_that_is_not_in_its_capture",
          changed and joins(term[0]) and not joins(victim),
          f"the real line of {term[0]['source']} joins; a one-character "
          f"corruption of it does not (the corruption changed something: {changed})")

    check("accept_every_named_capture_exists_and_is_not_empty",
          all(len(v) > 0 for v in caps.values()),
          {n: len(v) for n, v in caps.items()})


def c_pixels(sc: dict) -> None:
    """Each declared string is found in the frame its cue names."""
    want = [c for c in sc["cues"] if c["checkable_in_pixels"]]
    scores, missing = {}, []
    for c in want:
        tpl = render_template(c["text"], c["font"], c["size"])
        if tpl is None:
            missing.append((c["text"][:40], "template is blank"))
            continue
        s = Matcher(frame(c["frame"])).best(tpl)
        scores[c["text"][:48]] = round(s, 6)
        if s < PRESENT:
            missing.append((c["text"][:40], round(s, 6)))
    check("accept_every_declared_string_is_in_the_shipped_pixels",
          not missing and bool(want),
          f"{len(want) - len(missing)} of {len(want)} at or above {PRESENT}; "
          f"worst true line {min(scores.values()) if scores else 'n/a'}")
    for t, s in missing:
        print(f"        MISSING {t!r} -> {s}")

    # REFUSAL ARM.  The matcher must be able to say NOT FOUND, or the control
    # above is a check that cannot go red.  Decoys are DERIVED from the real
    # lines, so they keep decoying after the content moves.
    ref = want[0]
    m = Matcher(frame(ref["frame"]))
    decoys = [corrupt(ref["text"]), ref["text"][::-1],
              "This sentence is not anywhere in this video at all."]
    dscores = []
    for d in decoys:
        tpl = render_template(d, ref["font"], ref["size"])
        dscores.append(-1.0 if tpl is None else round(m.best(tpl), 6))
    check("matcher_reports_absent_strings_as_absent",
          all(s < ABSENT for s in dscores),
          f"{len(decoys)} decoys all below {ABSENT}: {dscores}")

    one_char = corrupt(ref["text"])
    tpl = render_template(one_char, ref["font"], ref["size"])
    s1 = m.best(tpl) if tpl is not None else -1.0
    check("a_one_character_change_does_not_reach_the_present_bar",
          s1 < PRESENT,
          f"one changed character scores {s1:.6f} against PRESENT {PRESENT}")


def c_honesty(sc: dict) -> None:
    deck = json.loads((SLIDE_EV / "slides_presentation.json").read_text(
        encoding="utf-8"))
    deck_items = [a["text"] for a in deck["absences"]]
    led = [c for c in sc["cues"] if c["kind"] == "absence"]

    # The two surfaces must not be able to drift: rejoining the video's drawn
    # rows must reproduce the deck's ledger exactly, item for item.
    rejoined, cur = [], []
    for c in sorted(led, key=lambda c: c["y_px"]):
        cur.append(c)
        if c["row"] == c["of_rows"] - 1:
            rejoined.append(" ".join(x["text"] for x in cur))
            cur = []
    check("accept_the_videos_ledger_rejoins_the_decks_ledger_exactly",
          rejoined == deck_items,
          f"{len(rejoined)} items rejoined against {len(deck_items)} in the deck; "
          f"{sum(1 for a, b in zip(rejoined, deck_items) if a != b)} differ")

    # A job no other control does.  On the sibling cover artifact the first
    # version of this control asserted only that each label appeared in the
    # placed list -- a strict subset of another control, and it could not fail.
    too_small = [c["text"][:40] for c in led if c["size"] < MIN_LEDGER_PT]
    outside = [c["text"][:40] for c in led if not (176 <= c["y_px"] <= 1080 - 96)]
    check("absence_ledger_is_drawn_legibly",
          not too_small and not outside and bool(led),
          f"{len(led)} ledger rows, all >= {MIN_LEDGER_PT}pt and inside the panel")

    bob = [c for c in sc["cues"] if c["kind"] == "bob_absence"]
    tpl = render_template(bob[0]["text"], bob[0]["font"], bob[0]["size"]) if bob else None
    s = Matcher(frame(bob[0]["frame"])).best(tpl) if tpl is not None else -1.0
    check("accept_the_bob_absence_is_stated_and_located_in_the_pixels",
          len(bob) == 1 and s >= PRESENT and "has not been used" in bob[0]["text"],
          f"{(bob[0]['text'] if bob else 'ABSENT')!r} at {s:.6f}")

    # REJECT any affirmative claim of Bob 2.0 usage anywhere in the cue text.
    # The scanner is proved non-vacuous on a planted string in the same call,
    # so a pattern that matches nothing cannot pass this quietly.
    claim = re.compile(r"\b(built|created|developed|generated|written|assisted)\b"
                       r"[^.]{0,60}\bBob 2\.0\b|\bBob 2\.0\b[^.]{0,40}"
                       r"\b(was|is|were)\s+(used|applied)\b", re.I)
    hits = [c["text"] for c in sc["cues"] if claim.search(c["text"])]
    planted = "This project was built with IBM Bob 2.0 throughout."
    check("reject_a_claim_that_bob_2_0_was_used",
          not hits and bool(claim.search(planted)),
          f"{len(hits)} affirmative-usage hits across {len(sc['cues'])} cues; "
          f"the scanner fires on the planted control")

    # The retired claim must be gone from the DRAWN LEDGER, not merely from the
    # source that draws it -- those are different surfaces, and a defect closed
    # in one surface is not closed.
    retired = [c["text"] for c in led if "no video yet" in c["text"]]
    check("reject_the_retired_no_video_yet_claim_in_the_drawn_ledger",
          not retired and any("hosted demo URL" in c["text"] for c in led),
          f"{len(retired)} occurrences of the retired clause; the demo-URL "
          f"absence it was split from is still drawn")


def c_live(sc: dict) -> None:
    """Re-run the captured commands HERE, in a fresh credential-free clone.

    This is the control that separates a replay from a fabrication: the
    captures are not trusted, they are reproduced.
    """
    caps = sc["captures"]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="checkvid_clone_"))
    try:
        clone = tmp / "ibm-bob-2-hackathon"
        rc = subprocess.run(["git", "clone", "--quiet", REPO_URL, str(clone)],
                            capture_output=True, text=True)
        if rc.returncode != 0:
            check("accept_captures_reproduce_in_a_fresh_clone", False,
                  f"clone failed: {rc.stderr.strip()[:120]}")
            return
        env = dict(os.environ)
        env["PYTHONPATH"] = str(clone)

        def norm(s: str) -> str:
            return re.sub(r"\d+\.\d+s", "<s>", s).strip()

        agree, disagree, reordered = [], [], []
        for name, meta in caps.items():
            if name.startswith("_"):
                continue
            cwd = clone if meta["cwd"] == "." else clone / meta["cwd"]
            got = subprocess.run(meta["cmd"].split(), cwd=cwd, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, timeout=1200)
            want = (CAP / f"{name}.txt").read_text(encoding="utf-8")
            same_rc = got.returncode == meta["returncode"]
            live = norm(got.stdout).replace(str(clone), "<clone>")
            recorded = norm(want).replace("/tmp/ibm-bob-2-hackathon", "<clone>")
            # Compared on the MULTISET of lines, not the sequence.  Measured
            # 2026-09-10T16:03Z over three runs: the auditor fans its mutants
            # across 4 workers and prints survivors in COMPLETION order, so a
            # re-run gives the same survivors in a different order.  Demanding
            # byte-identical output would be a control that goes red for a
            # reason that is not a defect; relaxing it to a substring would be
            # one that cannot go red at all.  The multiset is the honest bar,
            # and whether the order also matched is reported either way.
            same_set = sorted(live.splitlines()) == sorted(recorded.splitlines())
            if same_rc and same_set:
                agree.append(f"{name}(rc={got.returncode}"
                             + ("" if live == recorded else ",reordered") + ")")
                if live != recorded:
                    reordered.append(name)
            else:
                disagree.append(f"{name}(rc={got.returncode}/{meta['returncode']},"
                                f"lines={'same set' if same_set else 'DIFFER'})")
        check("accept_captures_reproduce_in_a_fresh_clone",
              not disagree and bool(agree),
              f"{len(agree)} of {len(agree) + len(disagree)} reproduced (same rc, "
              f"same line multiset): {', '.join(agree + disagree)}"
              + (f"; survivor order varies on {reordered}"
                 if reordered else "; order identical too"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def c_build(sc: dict) -> None:
    """The shipped bytes are what make_video.py produces from today's captures.

    Run in a sandbox that REFUSES an existing directory -- a copy that nests
    itself one level deeper leaves the check reading a stale tree, which is a
    false pass this project documents having met.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="checkvid_build_"))
    try:
        dst = tmp / "video"
        if dst.exists():
            check("rebuild_from_todays_captures_reproduces_the_shipped_bytes",
                  False, "sandbox refuses an existing directory")
            return
        shutil.copytree(HERE, dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.mp4"))
        shutil.copytree(SLIDE_EV, tmp / "slides" / "evidence",
                        ignore=shutil.ignore_patterns("__pycache__"))
        r = subprocess.run([sys.executable, "make_video.py"], cwd=dst,
                           capture_output=True, text=True, timeout=1800)
        built = dst / "evidence" / "video_presentation.mp4"
        same = (built.exists()
                and hashlib.sha256(built.read_bytes()).hexdigest() == sc["sha256"])
        check("rebuild_from_todays_captures_reproduces_the_shipped_bytes", same,
              f"rc={r.returncode} "
              + ("byte-identical" if same else "DIFFERS from the shipped sha256 -- "
                 + (r.stdout.strip()[-160:] or r.stderr.strip()[-160:])))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------- main
def main() -> int:
    for mod in ("numpy", "PIL"):
        try:
            __import__(mod)
        except ImportError:
            print(f"[FAIL] dependency {mod} is missing -- a failure, not a skip")
            return 1
    for exe in ("ffmpeg", "ffprobe", "git"):
        if shutil.which(exe) is None:
            print(f"[FAIL] {exe} is missing -- a failure, not a skip")
            return 1
    if not MP4.exists() or not SIDECAR.exists():
        print("[FAIL] the artifact or its sidecar is absent")
        return 1

    sc = json.loads(SIDECAR.read_text(encoding="utf-8"))
    groups = {"bytes": c_bytes, "replay": c_replay, "pixels": c_pixels,
              "honesty": c_honesty, "live": c_live, "build": c_build}
    # --groups exists for the mutation campaign, which runs this suite dozens of
    # times.  It never narrows a normal run: with no flag every group runs, and
    # the evidence file is written ONLY on a full run, so a partial run can
    # never be mistaken for one.
    want = list(groups)
    for i, a in enumerate(sys.argv):
        if a == "--groups" and i + 1 < len(sys.argv):
            want = [g for g in sys.argv[i + 1].split(",") if g in groups]
    for g in want:
        groups[g](sc)

    passed = sum(1 for r in results if r["pass"])
    print(f"\n{passed}/{len(results)} controls passed")
    if want == list(groups):
        (EV / "video_controls.json").write_text(
            json.dumps({"controls": results, "groups_run": want,
                        "passed": passed, "total": len(results),
                        "present_bar": PRESENT, "absent_bar": ABSENT},
                       indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
