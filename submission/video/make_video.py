#!/usr/bin/env python3
"""Build the video presentation the lablab submission form requires.

  "Video and Slide Presentation: MP4 and PDF formats are mandatory."
      -- lablab.ai Hackathon Rule Book, "Cover Image and Presentation"
  "Provide a link to your video presentation (ensure it's under 300MB and
   within 5 minutes duration)."
      -- lablab.ai Submission Guidelines

GOAL_JOB_COMPLETION.md is explicit about what a demo video is:

      Demo video | shows the thing actually running, not slides of it running

So this is NOT a render of the slide deck.  Every terminal frame in it is a
byte-for-byte replay of stdout captured from a REAL run, in a credential-free
clone of the public repository, on this host.  The captures ship next to the
video in evidence/captures/ with their return codes, and check_video.py
re-runs three of the four commands live and compares.

  python3 make_video.py     # -> evidence/video_presentation.mp4
                            #    evidence/video_presentation.json

A VIDEO HAS NO TEXT STREAM, and it has ~6,000 frames rather than one.  A PDF
can be checked by extracting its text; a raster frame cannot.  So, exactly as
in ../cover/make_cover.py, every string sits at an INTEGER PIXEL origin, and
the sidecar names -- for each checkable string -- the frame index at which it
is fully drawn.  check_video.py decodes THAT frame out of the shipped MP4 and
finds the string in its pixels by normalised cross-correlation.

Two honesty constraints are enforced by the builder itself, not by review:

  * the deck's absence ledger is drawn in full, and the build REFUSES if the
    "IBM Bob 2.0 has not been used" line is missing from it;
  * every terminal line must be present byte-exactly in the capture it claims
    to come from.  A line this builder invented cannot be drawn.

The video is SILENT.  There is no narration and no audio track; the sidecar
records `has_audio: false` so that nothing downstream can imply otherwise.

Deterministic: SOURCE_DATE_EPOCH is pinned, no wall-clock string is rendered,
and libx264 is driven with fixed settings from a fixed frame list.
Needs PIL and ffmpeg.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("SOURCE_DATE_EPOCH", "1757000000")

from PIL import Image, ImageDraw, ImageFont                      # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
EV = HERE / "evidence"
CAP = EV / "captures"
MP4 = EV / "video_presentation.mp4"
SIDECAR = EV / "video_presentation.json"
SLIDE_EV = HERE.parent / "slides" / "evidence"

W, H, FPS = 1920, 1080, 25
BG = (0x0A, 0x0D, 0x12)
PANEL = (0x14, 0x1C, 0x28)
RULE = (0x22, 0x30, 0x3F)
ACCENT = (0x6F, 0xC3, 0xC6)
TEXT = (0xE9, 0xEE, 0xF3)
MUTED = (0x93, 0xA2, 0xB1)
WARN = (0xE2, 0xA2, 0x4A)
GREEN = (0x7F, 0xC6, 0x7F)

EVENT = "IBM Bob 2.0 Hackathon | lablab.ai | 2026-09-25 to 2026-09-27"
REPO = "github.com/jianwang-ntu/ibm-bob-2-hackathon"
TITLE = "Vacuity Auditor"
SUBTITLE = "Can this check ever go red?"

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
SANS = f"{FONT_DIR}/DejaVuSans.ttf"
SANS_B = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
MONO = f"{FONT_DIR}/DejaVuSansMono.ttf"
MONO_B = f"{FONT_DIR}/DejaVuSansMono-Bold.ttf"

_fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


# The duration window the rules and the rubric define between them.  The Rule
# Book criterion 1 band 2 penalises a presentation under 3 minutes; the
# Submission Guidelines cap it at 5.  Outside [180, 300) the build refuses.
MIN_S, MAX_S = 180.0, 300.0
MAX_BYTES = 300 * 1024 * 1024

MIN_LEDGER_PT = 20                    # legibility floor the ledger control reads
TERM_X, TERM_Y, TERM_LH, TERM_SIZE = 64, 168, 30, 20
TERM_WRAP = 132                       # cols; the widest capture line is 190
TERM_MAX_LINES = 28

cues: list[dict] = []                 # every checkable string, for the sidecar
_violations: list[str] = []


# ------------------------------------------------------------------ helpers
def wrap_mono(line: str, cols: int = TERM_WRAP, indent: str = "    ") -> list[str]:
    """Hard-wrap a captured line, preserving it exactly on rejoin."""
    if len(line) <= cols:
        return [line]
    out, rest = [line[:cols]], line[cols:]
    while rest:
        out.append(indent + rest[:cols - len(indent)])
        rest = rest[cols - len(indent):]
    return out


def unwrap_mono(parts: list[str], indent: str = "    ") -> str:
    head = parts[0]
    for p in parts[1:]:
        head += p[len(indent):] if p.startswith(indent) else p
    return head


def wrap_prop(text: str, f: ImageFont.FreeTypeFont, max_px: int) -> list[str]:
    """Greedy word-wrap measured with the real font metrics, not by character
    count -- the deck's builder was caught once by eyeballing a width."""
    words, rows, cur = text.split(" "), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if measure(trial, f) <= max_px or not cur:
            cur = trial
        else:
            rows.append(cur); cur = w
    if cur:
        rows.append(cur)
    return rows


def new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def draw_text(d: ImageDraw.ImageDraw, xy: tuple[int, int], s: str,
              f: ImageFont.FreeTypeFont, fill, anchor: str = "la") -> None:
    """Every origin is an integer pixel, which is what makes a rendered
    template comparable to the shipped pixels."""
    x, y = int(xy[0]), int(xy[1])
    d.text((x, y), s, font=f, fill=fill, anchor=anchor)


def measure(s: str, f: ImageFont.FreeTypeFont) -> int:
    return int(f.getbbox(s)[2] - f.getbbox(s)[0])


def cue(kind: str, text: str, x: int, y: int, fpath: str, size: int,
        checkable: bool, local_state: int, source: str | None = None,
        extra: dict | None = None) -> dict:
    """`local_state` is the index, WITHIN the group its generator returns, of
    the state on which this string is fully drawn.  build() offsets it to an
    absolute state index and then to a frame number; nothing here guesses."""
    c = {"kind": kind, "text": text, "x_px": int(x), "y_px": int(y),
         "font": pathlib.Path(fpath).name, "size": size,
         "checkable_in_pixels": bool(checkable),
         "_local": int(local_state), "frame": None}
    if source:
        c["source"] = source
    if extra:
        c.update(extra)
    cues.append(c)
    return c


# ------------------------------------------------------------------- chrome
def chrome(img: Image.Image, heading: str, sub: str | None = None) -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 96], fill=PANEL)
    d.line([(0, 96), (W, 96)], fill=RULE, width=2)
    draw_text(d, (64, 30), heading, font(SANS_B, 30), TEXT)
    if sub:
        draw_text(d, (64, 66), sub, font(SANS, 21), MUTED)
    d.line([(0, H - 56), (W, H - 56)], fill=RULE, width=2)
    draw_text(d, (64, H - 40), REPO, font(SANS, 19), MUTED)
    draw_text(d, (W - 64, H - 40), "silent -- no narration track",
              font(SANS, 19), MUTED, anchor="ra")
    return d


# -------------------------------------------------------------------- cards
def card_title() -> list[tuple[Image.Image, float]]:
    img = new_frame()
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], fill=BG)
    draw_text(d, (110, 250), TITLE, font(SANS_B, 96), TEXT)
    cue("card", TITLE, 110, 250, SANS_B, 96, True, 0)
    draw_text(d, (110, 372), SUBTITLE, font(SANS, 46), ACCENT)
    cue("card", SUBTITLE, 110, 372, SANS, 46, True, 0)
    line = "It audits the check, not the code the check is pointed at."
    draw_text(d, (110, 448), line, font(SANS, 27), MUTED)
    cue("card", line, 110, 448, SANS, 27, False, 0)

    d.rectangle([110, 540, W - 110, 760], fill=PANEL)
    draw_text(d, (140, 566), "STATUS, STATED FIRST", font(SANS_B, 21), WARN)
    cue("card", "STATUS, STATED FIRST", 140, 566, SANS_B, 21, False, 0)
    bob = "IBM Bob 2.0 has not been used on this project."
    draw_text(d, (140, 612), bob, font(SANS_B, 32), TEXT)
    cue("bob_absence", bob, 140, 612, SANS_B, 32, True, 0)
    for i, t in enumerate([
        "Access opens at kickoff and nothing in this recording claims otherwise.",
        "Everything shown below is a real run, captured on this host, in a",
        "credential-free clone of the public repository.",
    ]):
        draw_text(d, (140, 662 + i * 32), t, font(SANS, 24), MUTED)
        cue("card", t, 140, 662 + i * 32, SANS, 24, False, 0)
    draw_text(d, (110, 830), EVENT, font(SANS, 24), MUTED)
    cue("card", EVENT, 110, 830, SANS, 24, False, 0)
    draw_text(d, (110, 870), f"Solo entry - Wang Jian - {REPO}", font(SANS, 24), MUTED)
    cue("card", f"Solo entry - Wang Jian - {REPO}", 110, 870, SANS, 24, False, 0)
    return [(img, 13.0)]


def card_bullets(heading: str, sub: str, bullets: list[str],
                 dwell: float = 4.2, tail: float = 3.0,
                 kind: str = "card", checkable: bool = False,
                 note: str | None = None) -> list[tuple[Image.Image, float]]:
    """Reveal bullets one at a time; the last state holds for `tail`."""
    states: list[tuple[Image.Image, float]] = []
    for n in range(1, len(bullets) + 1):
        img = new_frame()
        d = chrome(img, heading, sub)
        y = 190
        for i, b in enumerate(bullets[:n]):
            f = font(SANS, 30)
            if measure(b, f) > W - 220:
                _violations.append(f"bullet overflows: {b[:60]}...")
            d.ellipse([110, y + 12, 122, y + 24], fill=ACCENT)
            draw_text(d, (146, y), b, f, TEXT)
            if n == len(bullets):
                cue(kind, b, 146, y, SANS, 30, checkable, len(bullets) - 1)
            y += 74
        if note and n == len(bullets):
            d.line([(110, H - 150), (W - 110, H - 150)], fill=RULE, width=2)
            draw_text(d, (110, H - 128), note, font(SANS, 24), MUTED)
            cue(kind, note, 110, H - 128, SANS, 24, False, len(bullets) - 1)
        states.append((img, dwell if n < len(bullets) else tail))
    return states


def card_ledger(items):
    """The absence ledger, drawn in full.

    Its own control -- absence_ledger_is_drawn_legibly -- checks that every
    row here is at least MIN_LEDGER_PT and sits inside the panel.  That is a
    job no other control does; on the sibling cover artifact the first version
    of this control was a strict subset of another one and could not fail."""
    img = new_frame()
    d = chrome(img, "THE LEDGER, ON THE SCREEN", "What this entry does not have")
    top, bot = 176, H - 96
    d.rectangle([100, top, W - 100, bot], fill=PANEL)
    x, y, size = 170, top + 26, MIN_LEDGER_PT + 2
    max_px = (W - 100) - x - 40
    f = font(SANS, size)
    for t in items:
        rows = wrap_prop(t, f, max_px)
        d.text((140, y), "-", font=font(SANS_B, size), fill=WARN)
        for k, row in enumerate(rows):
            if measure(row, f) > max_px:
                _violations.append("ledger row overflows: " + row[:60])
            if y + size > bot:
                _violations.append("ledger row outside the panel: " + row[:60])
            draw_text(d, (x, y), row, f, TEXT)
            cue("absence", row, x, y, SANS, size, True, 0,
                extra={"ledger_item": t, "row": k, "of_rows": len(rows)})
            y += 30
        y += 8
    return [(img, 6.0), (img, 13.0)]


# ----------------------------------------------------------------- terminal
def terminal_act(heading: str, sub: str, blocks: list[dict],
                 ) -> list[tuple[Image.Image, float]]:
    """Replay captured stdout, revealing one line at a time.

    Each block is {prompt, cwd, capture, rc, dwell, hold, checkable}.  Every
    output line is looked up in the named capture file and must match it
    byte-for-byte; a line the builder invented raises."""
    states: list[tuple[Image.Image, float]] = []
    shown: list[tuple[str, tuple[int, int, int], str]] = []
    for blk in blocks:
        prompt = f"$ {blk['prompt']}"
        shown.append((f"{blk['cwd']}", MUTED, "mono"))
        states.append((_term_frame(heading, sub, shown), 0.9))
        shown.append((prompt, ACCENT, "mono_b"))
        states.append((_term_frame(heading, sub, shown), blk.get("cmd_dwell", 2.6)))
        raw = (CAP / f"{blk['capture']}.txt").read_text(encoding="utf-8")
        cap_lines = raw.splitlines()
        wanted = list(blk.get("checkable_contains", []))
        for ln in cap_lines:
            for part in wrap_mono(ln):
                shown.append((part, TEXT if ln.strip() else MUTED, "mono"))
            states.append((_term_frame(heading, sub, shown), blk.get("dwell", 0.75)))
            # Declare a cue AT THE STATE THE LINE IS DRAWN ON, not at block end:
            # a long capture scrolls its own head off the 28-line window, and a
            # cue resolved at block end would point at a frame not showing it.
            for sub_sel in [w for w in wanted if w in ln]:
                _declare_line_cue(shown, blk, len(states) - 1, ln, sub_sel)
                wanted.remove(sub_sel)
        for missed in wanted:
            _violations.append(
                f"selector {missed!r} never matched a line of {blk['capture']}")
        rcline = f"[exit {blk['rc']}]  {blk['rc_gloss']}"
        shown.append((rcline, GREEN if blk["rc"] == 0 else WARN, "mono_b"))
        states.append((_term_frame(heading, sub, shown), blk.get("hold", 3.5)))
        shown.append(("", TEXT, "mono"))
    return states


def _visible(shown):
    return shown[-TERM_MAX_LINES:]


def _term_frame(heading, sub, shown) -> Image.Image:
    img = new_frame()
    d = chrome(img, heading, sub)
    y = TERM_Y
    for txt, col, style in _visible(shown):
        f = font(MONO_B if style == "mono_b" else MONO, TERM_SIZE)
        if measure(txt, f) > W - 2 * TERM_X:
            _violations.append(f"terminal line overflows: {txt[:60]}...")
        draw_text(d, (TERM_X, y), txt, f, col)
        y += TERM_LH
    return img


def _declare_line_cue(shown, blk, local_state, full_line, selector) -> None:
    """Record where this capture line is drawn in the state just appended.

    `full_line` is the byte-exact capture line; `drawn` is its first wrapped
    row, which is what is actually in the pixels.  The checker joins the cue
    back to the capture file on `capture_line`, and to the shipped frame on
    `text`, so a builder that invented either one fails a different control."""
    vis = _visible(shown)
    drawn = wrap_mono(full_line)[0]
    rows = [i for i, (t, _, _) in enumerate(vis) if t == drawn]
    if not rows:
        _violations.append(f"declared line not visible when drawn: {selector!r}")
        return
    cue("terminal", drawn, TERM_X, TERM_Y + rows[-1] * TERM_LH,
        MONO, TERM_SIZE, True, local_state, source=blk["capture"],
        extra={"capture_line": full_line, "selector": selector,
               "wrapped": len(wrap_mono(full_line)) > 1})


# --------------------------------------------------------------------- main
def build() -> None:
    if not CAP.exists():
        raise SystemExit("evidence/captures/ is missing -- nothing to replay")
    caps = json.loads((CAP / "captures.json").read_text(encoding="utf-8"))

    states: list[tuple[Image.Image, float]] = []

    def add(group: list) -> None:
        """Stamp every cue emitted since the last add() with the absolute state
        index this group starts at.  Generators number their cues locally; this
        is the only place a local index becomes an absolute one."""
        base = len(states)
        for c in cues[add.mark:]:
            c["_base"] = base
        add.mark = len(cues)
        states.extend(group)
    add.mark = 0

    add(card_title())

    add(card_bullets(
        "THE PROBLEM", "A green tick that cannot go red is read as evidence",
        ["When one agent writes a change AND the test that verifies it, the test very",
         "often cannot fail.  assert result is not None passes for every implementation.",
         "A reviewer sees a green tick and approves.  The tick meant nothing.",
         "Every tool on the shelf answers did the suite pass?, not could it have failed?"],
        dwell=4.0, tail=3.5,
        note="This is code review of AI-assisted changes -- one of the workflows the challenge brief names."))

    add(terminal_act(
        "IT RUNS", "A credential-free clone of the public repository, on this host",
        [dict(cwd="~/ibm-bob-2-hackathon", prompt="python3 -m pytest -q",
              capture="repo_tests", rc=caps["repo_tests"]["returncode"],
              rc_gloss="the tool's own suite is green in a clean clone",
              dwell=1.6, hold=4.5,
              checkable_contains=["passed in"])]))

    add(card_bullets(
        "THE GAP, MEASURED", "examples/demo_project -- one 4-line pricing function, two test files",
        ["Two test suites cover the same function.  Both pass under pytest.",
         "One of them constrains the code.  The other only looks like it does.",
         "pytest cannot tell them apart, because that is not the question it asks."],
        dwell=3.8, tail=3.0))

    add(terminal_act(
        "BOTH SUITES ARE GREEN", "and that is the whole problem",
        [dict(cwd="~/ibm-bob-2-hackathon/examples/demo_project",
              prompt="python3 -m pytest tests -q",
              capture="demo_pytest", rc=caps["demo_pytest"]["returncode"],
              rc_gloss="pytest is satisfied.  Ship it?",
              dwell=1.4, hold=5.0,
              checkable_contains=["passed in"])]))

    add(terminal_act(
        "THE AUDITOR ASKS THE OTHER QUESTION",
        "vacuity-audit audit -- mutate the module, and see whether each check turns red",
        [dict(cwd="~/ibm-bob-2-hackathon/examples/demo_project",
              prompt="python3 -m vacuity_auditor audit --root . --spec vacuity.toml",
              capture="demo_audit", rc=caps["demo_audit"]["returncode"],
              rc_gloss="WEAK -- named survivors remain.  Not a pass, and not a failure.",
              dwell=0.92, cmd_dwell=3.4, hold=13.0,
              checkable_contains=["real_suite_verifies_pricing     WEAK",
                                  "vacuous_suite_verifies_pricing  WEAK"])]))

    add(card_bullets(
        "THE ANSWER IT GIVES", "Four words, and three of them are not a pass",
        ["DISCRIMINATING  exit 0   every behaviour-changing mutation turned the check red",
         "WEAK            exit 3   some did; named survivors remain, and they are printed",
         "VACUOUS         exit 1   nothing did.  Green from this check is not evidence",
         "INCONCLUSIVE    exit 2   the audit could not conclude.  Never reported as a pass"],
        dwell=3.4, tail=4.0,
        note="Each band has its own exit code so a merge gate can act on the difference."))

    add(terminal_act(
        "IT AUDITS ITSELF", "the static scan, run here on the tool's own test suite",
        [dict(cwd="~/ibm-bob-2-hackathon", prompt="python3 -m vacuity_auditor scan --root .",
              capture="self_scan", rc=caps["self_scan"]["returncode"],
              rc_gloss="5 candidates in its OWN tests.  These locate; they do not decide.",
              dwell=1.5, hold=6.5,
              checkable_contains=["no_assertion           tests/test_mutants.py"])]))

    self_ev = json.loads((SLIDE_EV / "self_audit.json").read_text(encoding="utf-8"))
    weak = sum(1 for c in self_ev["claims"] if c["verdict"] == "WEAK")
    total = len(self_ev["claims"])
    disc = sum(1 for c in self_ev["claims"] if c["verdict"] == "DISCRIMINATING")
    add(card_bullets(
        "AND THE FULL SELF-AUDIT IS NOT FLATTERING",
        "read from the repository's committed evidence/self_audit.json -- not re-run in this recording",
        [f"{weak} of {total} claims about this tool's own tests come back WEAK.",
         f"{disc} are DISCRIMINATING.  The tool's own suite is not clean either.",
         "The worst is baseline_guard_reads_baseline at 3 / 8: its tests match reason",
         "strings by substring, so appending to one does not turn them red."],
        dwell=3.6, tail=4.5,
        note="A demo that audited itself and reported a clean bill of health is the exact failure this tool exists to find."))

    add(card_bullets(
        "BUSINESS VALUE, AND WHAT WOULD VALIDATE IT",
        "labelled as a plan, because that is what it is",
        ["The user is a reviewer merging AI-written changes at a volume nobody can read.",
         "The change is at the merge gate: a VACUOUS check stops counting as evidence.",
         "Open-source core under MIT; the paid surface would be hosted CI runs.",
         "No revenue, no customers, no pricing validated, and no market study."],
        dwell=3.6, tail=4.0,
        note="Audit N public repositories and publish the base rate of VACUOUS claims -- that is the experiment that would test it.  It is not done."))

    ledger = [a["text"] for a in json.loads(
        (SLIDE_EV / "slides_presentation.json").read_text(encoding="utf-8"))["absences"]]
    add(card_ledger(ledger))

    add(card_bullets(
        "TRY IT", "Every number in this recording is reproducible from a clean clone",
        ["git clone https://github.com/jianwang-ntu/ibm-bob-2-hackathon",
         "cd ibm-bob-2-hackathon && pip install -e .",
         "cd examples/demo_project && vacuity-audit audit --root . --spec vacuity.toml"],
        dwell=3.5, tail=7.0,
        note="The four captures replayed above ship in submission/video/evidence/captures/ with their return codes."))

    if _violations:
        raise SystemExit("REFUSING TO WRITE -- layout violations:\n  " +
                         "\n  ".join(_violations))
    if not any(c["kind"] == "bob_absence" for c in cues):
        raise SystemExit("REFUSING TO WRITE -- the IBM Bob 2.0 absence is not drawn")

    total_s = sum(dur for _, dur in states)
    if not (MIN_S <= total_s < MAX_S):
        raise SystemExit(f"REFUSING TO WRITE -- {total_s:.1f}s is outside "
                         f"[{MIN_S}, {MAX_S}) (Rule Book band 2 / Guidelines cap)")

    # ---- resolve every cue's frame index from the cumulative state timeline.
    # A cue names (group base state, local state within the group).  Both are
    # recorded at draw time; neither is guessed here.
    frame_of_state, acc = [], 0.0
    for _, dur in states:
        frame_of_state.append(int(round(acc * FPS)))
        acc += dur
    for c in cues:
        st = c.pop("_base") + c.pop("_local")
        if st >= len(states):
            raise SystemExit(f"cue points past the timeline: {c['text'][:50]!r}")
        # +6 frames: land inside the state's dwell, never on its boundary
        c["frame"] = frame_of_state[st] + 6
        c["state"] = st
    unresolved = [c for c in cues if c["frame"] is None]
    if unresolved:
        raise SystemExit(f"{len(unresolved)} cue(s) resolved to no frame")

    EV.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vidbuild_"))
    try:
        listing = []
        for i, (img, dur) in enumerate(states):
            p = tmp / f"f{i:05d}.png"
            img.save(p)
            listing.append(f"file '{p}'\nduration {dur:.3f}")
        listing.append(f"file '{tmp / f'f{len(states) - 1:05d}.png'}'")
        (tmp / "list.txt").write_text("\n".join(listing) + "\n", encoding="utf-8")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
               "-vsync", "cfr", "-r", str(FPS),
               "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(MP4)]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    data = MP4.read_bytes()
    if len(data) > MAX_BYTES:
        MP4.unlink()
        raise SystemExit(f"REFUSING TO SHIP -- {len(data)} bytes exceeds 300 MB")

    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(MP4)],
        capture_output=True, text=True, check=True).stdout)
    vs = [s for s in probe["streams"] if s["codec_type"] == "video"]
    aud = [s for s in probe["streams"] if s["codec_type"] == "audio"]

    sidecar = {
        "schema": "video_presentation/v1",
        "mp4": "submission/video/evidence/video_presentation.mp4",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "duration_s": round(float(probe["format"]["duration"]), 3),
        "duration": f"{int(total_s // 60)}:{total_s % 60:04.1f}",
        "planned_duration_s": round(total_s, 3),
        "fps": FPS,
        "width_px": int(vs[0]["width"]),
        "height_px": int(vs[0]["height"]),
        "aspect_ratio": "16:9",
        "aspect_ratio_exact": f'{vs[0]["width"]} * 9 == {vs[0]["height"]} * 16 -> '
                              f'{int(vs[0]["width"]) * 9 == int(vs[0]["height"]) * 16}',
        "codec": vs[0]["codec_name"],
        "container": probe["format"]["format_name"],
        "has_audio": bool(aud),
        "silent": not aud,
        "silent_note": "There is no narration and no audio track.  Stated here so "
                       "that no downstream text can imply one.",
        "requirement": 'lablab Hackathon Rule Book, "Cover Image and Presentation": '
                       '"Video and Slide Presentation: MP4 and PDF formats are mandatory."',
        "published_limits": "MP4, supplied as a link, under 300MB, within 5 minutes; "
                            "Rule Book criterion 1 band 2 penalises under 3 minutes",
        "duration_window_enforced": [MIN_S, MAX_S],
        "built_by": "submission/video/make_video.py",
        "source_date_epoch": os.environ["SOURCE_DATE_EPOCH"],
        "states": len(states),
        "captures": caps,
        "replayed_not_reconstructed": "Every terminal line drawn in this video is a "
                                      "byte-exact line of the capture named on its cue, "
                                      "captured from a real run in a credential-free "
                                      "clone.  check_video.py re-runs three of the four "
                                      "commands live and compares.",
        "cues": cues,
    }
    SIDECAR.write_text(json.dumps(sidecar, indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"wrote {MP4}  {len(data):,} bytes  {sidecar['duration_s']}s  "
          f"{sidecar['width_px']}x{sidecar['height_px']}  audio={sidecar['has_audio']}")
    print(f"wrote {SIDECAR}  cues={len(cues)}  "
          f"checkable={sum(1 for c in cues if c['checkable_in_pixels'])}")



if __name__ == "__main__":
    sys.exit(build())
