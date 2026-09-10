#!/usr/bin/env python3
"""Build the slide presentation PDF the lablab Rule Book makes mandatory.

  "Video and Slide Presentation: MP4 and PDF formats are mandatory."
      -- lablab.ai Hackathon Rule Book, "Cover Image and Presentation"
      (rules_canonical_20260909T2300Z/rulebook.body.txt:16)

The deck is GENERATED, not authored.  Every figure on every slide is read out of
evidence/*.json at build time -- the auditor's own report files and one measured
readback of the public repository -- and check_slides.py re-derives the same
figures independently and fails if the shipped PDF stops matching them.

That is not decoration for this particular entry: the project's whole argument
is that a claim which nothing can falsify is not evidence.  A deck whose numbers
no control reads would be exactly the failure the tool exists to find.

Layout is measured, not eyeballed.  Every string is wrapped with the real font
metrics and the build FAILS if any text escapes the page margins, overlaps
another string, straddles a panel edge, or lands on a chart it does not own.

  python3 make_slides.py        # -> evidence/slides_presentation.pdf
                                #    evidence/slides_presentation.json

Deterministic: SOURCE_DATE_EPOCH is pinned below, so two builds from the same
evidence produce byte-identical PDFs -- which is how check_slides.py ties the
shipped bytes to this builder.  Needs matplotlib.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

# Pinned BEFORE matplotlib is imported: matplotlib reads it for /CreationDate.
os.environ.setdefault("SOURCE_DATE_EPOCH", "1757000000")

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42        # real text, so a judge can copy it
matplotlib.rcParams["font.family"] = "DejaVu Sans"
import matplotlib.pyplot as plt                                  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages             # noqa: E402
from matplotlib.patches import Rectangle                         # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
EV = HERE / "evidence"
PDF = EV / "slides_presentation.pdf"
SIDECAR = EV / "slides_presentation.json"

TITLE = "Vacuity Auditor: can this check ever go red?"
EVENT = "IBM Bob 2.0 Hackathon | lablab.ai | 2026-09-25 to 2026-09-27"
REPO = "github.com/jianwang-ntu/ibm-bob-2-hackathon"

FIGSIZE = (13.333, 7.5)                 # 16:9
L, R = 0.055, 0.945                     # content margins, figure fraction
BG = "#0A0D12"
PANEL = "#141C28"
RULE = "#22303F"
ACCENT = "#6FC3C6"
TEXT = "#E9EEF3"
MUTED = "#93A2B1"
WARN = "#E2A24A"
BAD = "#D9534F"
GOOD = "#7CBF7C"
MONO = "DejaVu Sans Mono"

recorded: list[dict] = []               # every string, for the sidecar
tracked: list[dict] = []                # every artist, for the layout check
panels: list[dict] = []                 # every background block, likewise
extra_violations: list[dict] = []       # raised during slide construction
_page = {"n": 0}


# ------------------------------------------------------------------- layout
def _renderer(fig):
    return fig.canvas.get_renderer()


def text_width(fig, s, size, weight="normal", family="DejaVu Sans", style="normal"):
    """Width of `s` as a fraction of page width, from the real font metrics."""
    probe = fig.text(0, 0, s, fontsize=size, fontweight=weight, family=family,
                     style=style)
    w = probe.get_window_extent(_renderer(fig)).width / fig.bbox.width
    probe.remove()
    return w


def wrap(fig, s, size, maxw, **kw):
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and text_width(fig, trial, size, **kw) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def say(fig, x, y, s, size=15, color=TEXT, weight="normal", ha="left",
        va="center", family="DejaVu Sans", style="normal", role="body",
        record=True, ax=None):
    """Draw ONE string on one line and remember it.

    A checkable figure must live inside a single say/flow call: that is what
    keeps its words adjacent in the PDF content stream, and therefore findable
    by check_slides.py.
    """
    target = ax if ax is not None else fig
    art = target.text(x, y, s, fontsize=size, color=color, fontweight=weight,
                      ha=ha, va=va, family=family, style=style)
    tracked.append({"art": art, "page": _page["n"], "ax": ax, "text": s})
    if record:
        recorded.append({"slide": _page["n"], "role": role, "text": s})
    return art


def flow(fig, x, y, s, size=15, maxw=None, lead=1.55, role="body", **kw):
    """Draw one string wrapped to `maxw`, recorded as the single string it is.

    Wrapping is safe for the claim checks: consecutive text objects extract in
    order, so a wrapped claim survives whitespace normalisation intact.
    """
    maxw = maxw if maxw is not None else (R - L)
    kwm = {k: kw[k] for k in ("weight", "family", "style") if k in kw}
    lines = wrap(fig, s, size, maxw, **kwm)
    dy = size * lead / (FIGSIZE[1] * 72.0)
    for i, ln in enumerate(lines):
        say(fig, x, y - i * dy, ln, size=size, role=role, record=False, **kw)
    recorded.append({"slide": _page["n"], "role": role, "text": s})
    return y - (len(lines) - 1) * dy - dy


def bullets(fig, x, y, items, size=15, maxw=None, gap=0.026, marker="-  ", **kw):
    for it in items:
        y = flow(fig, x, y, f"{marker}{it}", size=size, maxw=maxw, role="bullet",
                 **kw) - gap
    return y


def panel(fig, rect, color=PANEL):
    """A background block. Text goes on top of it in FIGURE coordinates."""
    fig.add_artist(Rectangle((rect[0], rect[1]), rect[2], rect[3],
                             transform=fig.transFigure, facecolor=color,
                             edgecolor=RULE, lw=1.0, zorder=0))
    panels.append({"page": _page["n"], "rect": rect})
    return rect


def new_slide(title=None, kicker=None):
    _page["n"] += 1
    fig = plt.figure(figsize=FIGSIZE, facecolor=BG)
    fig.patch.set_facecolor(BG)
    if kicker:
        say(fig, L, 0.945, kicker.upper(), size=11.5, color=ACCENT, weight="bold",
            role="kicker")
    if title:
        if len(wrap(fig, title, 27, R - L, weight="bold")) > 1:
            extra_violations.append({"kind": "title_wraps", "page": _page["n"],
                                     "text": title})
        flow(fig, L, 0.885, title, size=27, weight="bold", maxw=R - L, role="title")
        fig.add_artist(plt.Line2D([L, R], [0.840, 0.840], transform=fig.transFigure,
                                  color=RULE, lw=1.2))
    say(fig, R, 0.040, f"{_page['n']}", size=10.5, color=MUTED, ha="right",
        role="pageno", record=False)
    say(fig, L, 0.040, REPO, size=10.5, color=MUTED, role="footer", record=False)
    return fig


def layout_violations(fig):
    """Text off the page, text on text, or text straddling a panel it sits on."""
    fig.canvas.draw()
    r = _renderer(fig)
    mine = [t for t in tracked if t["page"] == _page["n"]]
    boxes = []
    for t in mine:
        b = t["art"].get_window_extent(r)
        boxes.append({
            "text": t["text"], "ax": t["ax"],
            "x0": b.x0 / fig.bbox.width, "x1": b.x1 / fig.bbox.width,
            "y0": b.y0 / fig.bbox.height, "y1": b.y1 / fig.bbox.height,
        })
    bad = [v for v in extra_violations if v["page"] == _page["n"]]
    for b in boxes:
        if b["x0"] < 0.03 or b["x1"] > 0.975 or b["y0"] < 0.02 or b["y1"] > 0.99:
            bad.append({"kind": "off_page", "page": _page["n"],
                        "text": b["text"][:70],
                        "box": [round(b[k], 4) for k in ("x0", "x1", "y0", "y1")]})
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ov_x = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
            ov_y = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
            if ov_x > 0.004 and ov_y > 0.004:
                bad.append({"kind": "text_on_text", "page": _page["n"],
                            "a": a["text"][:50], "b": b["text"][:50],
                            "overlap": [round(ov_x, 4), round(ov_y, 4)]})
    # A panel is checked with CLEARANCE, not mere containment: text that stops
    # 1 px short of a panel border reads as touching it, and a containment test
    # alone passes exactly that.
    CLEAR = 0.008
    for pan in [p for p in panels if p["page"] == _page["n"]]:
        px0, py0, pw, ph = pan["rect"]
        px1, py1 = px0 + pw, py0 + ph
        for b in boxes:
            inter_x = min(b["x1"], px1 + CLEAR) - max(b["x0"], px0 - CLEAR)
            inter_y = min(b["y1"], py1 + CLEAR) - max(b["y0"], py0 - CLEAR)
            if inter_x <= 0 or inter_y <= 0:
                continue
            inside = (b["x0"] >= px0 - 0.002 and b["x1"] <= px1 + 0.002
                      and b["y0"] >= py0 - 0.002 and b["y1"] <= py1 + 0.002)
            if not inside:
                bad.append({"kind": "text_straddles_panel", "page": _page["n"],
                            "text": b["text"][:70],
                            "panel": [round(v, 3) for v in pan["rect"]]})
    return bad


# ------------------------------------------------------------------ evidence
def load():
    j = lambda n: json.loads((EV / n).read_text(encoding="utf-8"))
    return {
        "self": j("self_audit.json"),
        "demo12": j("demo_audit_12.json"),
        "demo4": j("demo_audit_4.json"),
        "repo": j("repo_state.json"),
    }


def _by_id(report, claim_id):
    for c in report["claims"]:
        if c["claim_id"] == claim_id:
            return c
    raise KeyError(f"{claim_id} not in report")


def _evidential(c):
    """Denominator the kill count was actually measured against.

    `mutants_applied` includes runs where the check never executed.  The tool
    itself reports 3/8 from 10 applied for exactly this reason, and printing
    3/10 here would be the same defect the project exists to find.
    """
    return c["mutants_applied"] - c["mutants_did_not_run"]


def facts(e):
    """Every number the deck is allowed to print, derived here and nowhere else."""
    s, d12, d4, repo = e["self"], e["demo12"], e["demo4"], e["repo"]
    real12, vac12 = _by_id(d12, "real_suite_verifies_pricing"), _by_id(d12, "vacuous_suite_verifies_pricing")
    real4 = _by_id(d4, "real_suite_verifies_pricing")
    rows = [(c["claim_id"], c["verdict"], c["mutants_killed"], _evidential(c))
            for c in s["claims"]]
    worst = min(rows, key=lambda r: r[2] / r[3])
    return {
        "self_rows": rows,
        "self_total": s["summary"]["total"],
        "self_weak": s["summary"]["weak"],
        "self_discriminating": s["summary"]["discriminating"],
        "self_vacuous": s["summary"]["vacuous"],
        "self_static_candidates": len(s["claims"][0]["static_findings"]),
        "self_no_assertion": sum(1 for f in s["claims"][0]["static_findings"]
                                 if f["pattern"] == "no_assertion"),
        "worst_claim": worst[0], "worst_killed": worst[2], "worst_evidential": worst[3],
        "real12_verdict": real12["verdict"], "real12_killed": real12["mutants_killed"],
        "real12_n": _evidential(real12),
        "vac12_verdict": vac12["verdict"], "vac12_killed": vac12["mutants_killed"],
        "vac12_n": _evidential(vac12),
        "real4_verdict": real4["verdict"], "real4_killed": real4["mutants_killed"],
        "real4_n": _evidential(real4),
        "demo_static": len(d12["claims"][0]["static_findings"]),
        "vac12_survivors": [s_["mutant"] for s_ in vac12["survivors"]],
        "head": repo["head"], "head8": repo["head"][:8],
        "tracked": repo["tracked_files"],
        "modules": repo["module_count"],
        "test_files": repo["test_file_count"],
        "tests_passed": repo["tests_passed_in_clone"],
        "commits": repo["commit_count"],
        "authors": len(repo["distinct_commit_authors"]),
        "licence": repo["licence"],
    }


# ------------------------------------------------------------ claim strings
def claim_strings(F):
    """The figures the deck prints, as they must appear in the PDF.

    check_slides.py re-derives every one of these from evidence/*.json without
    importing this module, and looks for them in the shipped bytes.
    """
    return [
        ("headline_self",
         f"{F['self_weak']} of {F['self_total']} claims come back WEAK, "
         f"{F['self_discriminating']} DISCRIMINATING."),
        ("worst_self",
         f"The worst is {F['worst_claim']} at {F['worst_killed']} / "
         f"{F['worst_evidential']}."),
        ("demo_split",
         f"{F['real12_killed']} / {F['real12_n']} against "
         f"{F['vac12_killed']} / {F['vac12_n']}, and pytest calls both green."),
        ("budget_flip",
         f"At a budget of 4 the same suite reports {F['real4_verdict']} "
         f"{F['real4_killed']} / {F['real4_n']}; at 12 it reports "
         f"{F['real12_verdict']} {F['real12_killed']} / {F['real12_n']}."),
        ("repo_state",
         f"{F['tracked']} tracked files, {F['modules']} modules, "
         f"{F['test_files']} test files, {F['tests_passed']} tests passing in a "
         f"clean anonymous clone at {F['head8']}."),
        ("sole_author",
         f"{F['commits']} commits, {F['authors']} commit author, "
         f"{F['licence']} licensed."),
        ("demo_static_scan",
         f"The static scan flags {F['demo_static']} vacuity candidates in the "
         f"worked example before anything is executed."),
        ("self_static_scan",
         f"In this repository's own tests it flags "
         f"{F['self_static_candidates']} candidates, of which "
         f"{F['self_no_assertion']} is a no_assertion true positive."),
    ]


def absence_strings(F):
    """The absences the deck is required to state. Checked, so they cannot be cut."""
    return [
        ("no_bob",
         "IBM Bob 2.0 has not been used on this project. Access opens at "
         "kickoff and nothing here claims otherwise."),
        ("no_discriminating",
         f"Nothing in this repository's own audit is DISCRIMINATING: "
         f"{F['self_weak']} of {F['self_total']} claims are WEAK."),
        ("no_oracle_sensitivity",
         "Oracle sensitivity - swapping a check's input for noise - is "
         "designed and not implemented. It is in no number here."),
        ("python_only",
         "Python only. The AST operators and the pytest exit-code semantics "
         "read no other language."),
        ("budget_caveat",
         "The verdict depends on the mutant budget and the tool does not warn "
         "you. Treat DISCRIMINATING at a low budget as no counterexample "
         "found yet."),
        ("no_revenue",
         "No revenue, no customers, no pricing validated. The business model "
         "here is a plan, not a result."),
        ("no_market_study",
         "No market study was conducted. The only demand evidence here is the "
         "base rate measured on this repository and its worked example."),
        ("no_demo_url",
         "No hosted demo URL: deploying one needs an account this entry does "
         "not hold."),
    ]


# -------------------------------------------------------------------- slides
def slide_title(F):
    fig = new_slide()
    say(fig, L, 0.700, "Vacuity Auditor", size=54, weight="bold", role="title")
    say(fig, L, 0.605, "Can this check ever go red?", size=26, color=ACCENT,
        role="subtitle")
    fig.add_artist(plt.Line2D([L, 0.52], [0.560, 0.560], transform=fig.transFigure,
                              color=RULE, lw=1.4))
    flow(fig, L, 0.500,
         "A per-claim auditor for AI-assisted code review. It audits the check, "
         "not the code the check is pointed at, and answers in one of four words.",
         size=17, maxw=0.50, color=MUTED)
    say(fig, L, 0.340, EVENT, size=14, color=MUTED, role="event")
    say(fig, L, 0.295, "Solo entry - Wang Jian - " + REPO, size=14, color=MUTED,
        role="entrant")

    panel(fig, (0.600, 0.235, 0.345, 0.360))
    say(fig, 0.625, 0.555, "STATUS, STATED FIRST", size=11.5, color=WARN,
        weight="bold", role="kicker")
    flow(fig, 0.625, 0.505,
         "IBM Bob 2.0 has not been used on this project. Access opens at "
         "kickoff and nothing here claims otherwise.",
         size=13, maxw=0.295, color=TEXT, role="absence")
    flow(fig, 0.625, 0.345,
         "Every figure here is generated from evidence/*.json and re-checked "
         "against these PDF bytes.",
         size=13, maxw=0.295, color=MUTED)
    return fig


def slide_problem(F):
    fig = new_slide("A green tick that cannot go red is read as evidence",
                    kicker="Problem - the developer workflow this improves")
    y = 0.760
    y = bullets(fig, L, y, [
        "Code review of AI-assisted changes - one of the workflows the challenge "
        "brief names by hand, alongside onboarding, debugging and testing.",
        "When one agent writes a change AND the test that verifies it, the test "
        "very often cannot fail. assert result is not None passes for every "
        "implementation that returns an object.",
        "An assertion inside try: ... except: pass passes for all of them. A suite "
        "that collected zero tests exits green, and pytest exit 5 looks like "
        "success to a CI badge.",
        "A reviewer sees a green tick and approves. The tick meant nothing, and "
        "no tool on the shelf says so: they all answer did the suite pass?, not "
        "could it have failed?",
    ], size=16, maxw=0.86)

    panel(fig, (L, 0.095, R - L, 0.172))
    say(fig, L + 0.022, 0.230, "MEASURED, NOT ASSERTED", size=11.5, color=ACCENT,
        weight="bold", role="kicker")
    flow(fig, L + 0.022, 0.180,
         "In this repository's worked example two green suites cover the same "
         "four-line function: " + claim_text(F, "demo_split"),
         size=16, maxw=R - L - 0.044, role="claim")
    return fig


def claim_text(F, label):
    for lab, s in claim_strings(F):
        if lab == label:
            return s
    raise KeyError(label)


def slide_gap(F):
    fig = new_slide("Two green suites. One is evidence, one is decoration.",
                    kicker="The gap, measured")
    say(fig, L, 0.775,
        "examples/demo_project - one 4-line pricing function, two test files, "
        "both passing under pytest", size=15, color=MUTED)

    panel(fig, (L, 0.470, R - L, 0.255))
    cols = [L + 0.022, 0.46, 0.60, 0.70]
    hdr_y = 0.690
    for x, h in zip(cols, ["CLAIM", "VERDICT", "KILLED", "WHAT THAT MEANS"]):
        say(fig, x, hdr_y, h, size=12, color=ACCENT, weight="bold", role="header")
    rows = [
        ("real_suite_verifies_pricing", F["real12_verdict"],
         f"{F['real12_killed']} / {F['real12_n']}", "evidence, with named gaps"),
        ("vacuous_suite_verifies_pricing", F["vac12_verdict"],
         f"{F['vac12_killed']} / {F['vac12_n']}", "green for almost any wrong code"),
    ]
    y = 0.620
    for cid, verdict, killed, meaning in rows:
        col = GOOD if cid.startswith("real") else BAD
        say(fig, cols[0], y, cid, size=14, family=MONO, role="cell")
        say(fig, cols[1], y, verdict, size=14, color=col, weight="bold", role="cell")
        say(fig, cols[2], y, killed, size=14, color=col, weight="bold", role="cell")
        say(fig, cols[3], y, meaning, size=13.5, color=MUTED, role="cell")
        y -= 0.070

    flow(fig, L, 0.395,
         "Neither is clean, and that is the honest answer. The real suite never "
         "tests a 0% discount, so a mutant moving its guard survives it - a gap "
         "in a test its author believed complete. The split, and the named "
         "survivors, are the signal; a single pass/fail letter is not.",
         size=15.5, maxw=R - L, color=TEXT)
    y = 0.255
    say(fig, L, y, "Survivors the vacuous suite accepts, verbatim from the report:",
        size=14, color=MUTED, role="lead")
    for m in F["vac12_survivors"][:4]:
        y -= 0.045
        say(fig, L + 0.020, y, m, size=13, family=MONO, color=WARN, role="survivor")
    return fig


def slide_how(F):
    fig = new_slide("Four stages, and the order is load-bearing",
                    kicker="Solution - what it does")
    boxes = [
        ("1  Green-baseline guard",
         "Before any mutation the unmutated tree must be green, and green is "
         "checked properly: pytest exits 5 on zero collected and 4 on a usage "
         "error. A campaign layered on either scores 100% for free."),
        ("2  Static vacuity scan",
         "AST patterns that make a check unable to go red - no_assertion, "
         "presence_only, self_comparison, swallowed_assertion and three more. "
         "These are candidates, never verdicts. They locate; stage 3 decides."),
        ("3  Mutation as a negative control",
         "Mutants are built by rewriting the AST and unparsing, so every one is "
         "valid Python. Docstrings and log strings are excluded: they change no "
         "behaviour and would brand correct checks VACUOUS."),
        ("4  Two guards on the result",
         "A mutant that stops the check RUNNING looks like a kill from outside; "
         "those runs leave both numerator and denominator. And each sandbox "
         "refuses to be an existing directory, which is where nested-copy 100%s "
         "come from."),
    ]
    x0, w, gap = L, (R - L - 3 * 0.018) / 4, 0.018
    for i, (head, body) in enumerate(boxes):
        x = x0 + i * (w + gap)
        panel(fig, (x, 0.300, w, 0.470))
        flow(fig, x + 0.014, 0.730, head, size=15, weight="bold", maxw=w - 0.028,
             color=ACCENT, role="boxhead")
        flow(fig, x + 0.014, 0.640, body, size=12.5, maxw=w - 0.028, color=TEXT,
             role="boxbody")
    flow(fig, L, 0.215,
         "Stages 1 and 4 are the whole point. Every false 100% this tool has met "
         "came from a campaign that scored a suite which never ran, or from a "
         "copy that nested itself one directory deeper and left the check "
         "reading a stale tree.", size=15.5, maxw=R - L, color=MUTED)
    return fig


def slide_verdicts(F):
    fig = new_slide("Four words, and three of them are not a pass",
                    kicker="The answer it gives")
    rows = [
        ("DISCRIMINATING", GOOD, "0",
         "every behaviour-changing mutation of the claimed region turned the "
         "check red"),
        ("WEAK", WARN, "3",
         "some did, and named survivors remain: the check accepts specific "
         "wrong implementations"),
        ("VACUOUS", BAD, "1",
         "nothing did. Green from this check is not evidence for this claim"),
        ("INCONCLUSIVE", MUTED, "2",
         "the audit could not reach a conclusion. Never reported as a pass"),
    ]
    y = 0.740
    for name, col, code, meaning in rows:
        say(fig, L, y, name, size=17, color=col, weight="bold", family=MONO,
            role="verdict")
        say(fig, 0.30, y, f"exit {code}", size=14, color=MUTED, family=MONO,
            role="exit")
        flow(fig, 0.395, y, meaning, size=15, maxw=R - 0.395, color=TEXT,
             role="verdictbody")
        y -= 0.125
    panel(fig, (L, 0.080, R - L, 0.185))
    flow(fig, L + 0.022, 0.230,
         "Each band has its own exit code on purpose: not evidence, could not "
         "tell and evidence with gaps call for three different actions, and "
         "collapsing them into pass/fail is what makes a review tick "
         "meaningless in the first place.",
         size=15, maxw=R - L - 0.044, color=MUTED, role="note")
    return fig


def slide_self(F):
    fig = new_slide("It audits itself, and the result is not flattering",
                    kicker="Evidence - reproducible with one command")
    say(fig, L, 0.780,
        "vacuity-audit audit --root . --spec vacuity.toml   (--max-mutants 10)",
        size=14, family=MONO, color=ACCENT, role="command")

    panel(fig, (L, 0.272, R - L, 0.468))
    cols = [L + 0.022, 0.60, 0.72]
    say(fig, cols[0], 0.705, "CLAIM", size=12, color=ACCENT, weight="bold",
        role="header")
    say(fig, cols[1], 0.705, "VERDICT", size=12, color=ACCENT, weight="bold",
        role="header")
    say(fig, cols[2], 0.705, "KILLED / EVIDENTIAL", size=12, color=ACCENT,
        weight="bold", role="header")
    y = 0.640
    for cid, verdict, killed, n in F["self_rows"]:
        say(fig, cols[0], y, cid, size=13.5, family=MONO, role="cell")
        say(fig, cols[1], y, verdict, size=13.5, color=WARN, weight="bold",
            role="cell")
        say(fig, cols[2], y, f"{killed} / {n}", size=13.5, color=WARN,
            weight="bold", role="cell")
        y -= 0.062
    flow(fig, cols[0], 0.345,
         claim_text(F, "headline_self") + " " + claim_text(F, "worst_self")
         + " Its tests match reason strings by substring, so appending to one "
           "does not turn them red - a gap the tool found in its own suite.",
         size=13.5, maxw=R - L - 0.044, color=MUTED, role="claim")

    flow(fig, L, 0.230, claim_text(F, "self_static_scan"), size=15.5,
         maxw=R - L, role="claim")
    flow(fig, L, 0.165,
         "Nothing here is DISCRIMINATING. That is a real finding about this "
         "repository's own tests, the survivors are published in "
         "evidence/self_audit.json, and it is stated rather than hidden.",
         size=15, maxw=R - L, color=TEXT)
    return fig


def slide_budget(F):
    fig = new_slide("The number moves with the budget, and we say so",
                    kicker="The caveat a demo usually hides")
    panel(fig, (L, 0.480, R - L, 0.270))
    flow(fig, L + 0.022, 0.700, claim_text(F, "budget_flip"), size=19,
         maxw=R - L - 0.044, weight="bold", role="claim")
    flow(fig, L + 0.022, 0.585,
         "Same suite, same module, same tool. --max-mutants caps the pool and "
         "the cap is taken in generation order, not by sampling.",
         size=15, maxw=R - L - 0.044, color=MUTED)
    y = bullets(fig, L, 0.400, [
        "A small budget can turn a real gap into a clean bill of health. "
        "DISCRIMINATING at a low budget means no counterexample found yet, not "
        "none exists.",
        "This is on the slide, in the README and in the tool's own limitations "
        "list. It is the single most misleading thing the tool can output and "
        "it is not implemented away.",
        "Fixing it properly - warning when the cap binds, and sampling instead "
        "of truncating - is named on the roadmap and is not built.",
    ], size=15.5, maxw=R - L)
    return fig


def slide_competition(F):
    fig = new_slide("Prior art is older; the question is different.",
                    kicker="Competitive analysis")
    panel(fig, (L, 0.395, 0.425, 0.365))
    say(fig, L + 0.020, 0.720, "MUTATION TESTING TODAY", size=11.5, color=ACCENT,
        weight="bold", role="kicker")
    bullets(fig, L + 0.020, 0.665, [
        "mutmut, cosmic-ray and Pitest all do the mutation itself better than "
        "this does.",
        "They score a SUITE: one quality number over a whole test tree.",
        "None pairs a single check with the module it claims to verify.",
    ], size=12.5, maxw=0.380)

    panel(fig, (0.520, 0.395, 0.425, 0.365))
    say(fig, 0.540, 0.720, "WHAT THIS ADDS", size=11.5, color=ACCENT,
        weight="bold", role="kicker")
    bullets(fig, 0.540, 0.665, [
        "A PER-CLAIM question: does this check read this module?",
        "A green-baseline guard, so a suite that never ran cannot score.",
        "The did-not-run exclusion and the sandbox-nesting refusal - where "
        "false 100%s actually come from.",
    ], size=12.5, maxw=0.380)

    flow(fig, L, 0.330,
         "Stated against ourselves: on raw mutation quality the incumbents win, "
         "and a team that only wants a suite-level score should use them. The "
         "claim here is narrower - a per-claim verdict with named survivors is "
         "what an AI-assisted review needs, and the guards above are what keep "
         "the number honest.",
         size=15, maxw=R - L)
    flow(fig, L, 0.150,
         "Also unlike them, this tool publishes its own audit and comes back "
         "WEAK on every claim rather than shipping a green badge.",
         size=15, maxw=R - L, color=MUTED)
    return fig


def slide_value(F):
    fig = new_slide("Who it is for, and what it changes",
                    kicker="Business value")
    y = bullets(fig, L, 0.770, [
        "The user is a reviewer or a tech lead merging AI-written changes, where "
        "the volume of generated tests is what makes reading them all impossible.",
        "The change is at the merge gate: a check labelled VACUOUS stops being "
        "read as evidence, and attention goes where the suite is provably blind.",
        "The cost avoided is a defect shipped behind a green tick. This entry "
        "puts no currency figure on that, because it has measured none.",
    ], size=15, maxw=R - L, gap=0.024)

    panel(fig, (L, 0.070, R - L, 0.375))
    say(fig, L + 0.022, 0.408, "DEMAND EVIDENCE, AND ITS SAMPLE SIZE",
        size=11.5, color=ACCENT, weight="bold", role="kicker")
    flow(fig, L + 0.022, 0.358, claim_text(F, "demo_static_scan"), size=14.5,
         maxw=R - L - 0.044, role="claim")
    flow(fig, L + 0.022, 0.290, claim_text(F, "headline_self"), size=14.5,
         maxw=R - L - 0.044, role="claim")
    flow(fig, L + 0.022, 0.220,
         "One repository and one worked example: far too small to generalise "
         "from.", size=13.5, maxw=R - L - 0.044, color=MUTED)
    flow(fig, L + 0.022, 0.150,
         "No market study was conducted. The only demand evidence here is the "
         "base rate measured on this repository and its worked example.",
         size=13.5, maxw=R - L - 0.044, color=WARN, role="absence")
    return fig


def slide_market(F):
    fig = new_slide("The business model, labelled as a plan",
                    kicker="Market and revenue")
    panel(fig, (L, 0.430, 0.425, 0.330))
    say(fig, L + 0.020, 0.720, "WHO WOULD PAY, AND FOR WHAT", size=11.5,
        color=ACCENT, weight="bold", role="kicker")
    bullets(fig, L + 0.020, 0.668, [
        "Open-source core under MIT - the auditor itself, free.",
        "The paid surface would be a CI service: hosted runs, budget "
        "management, and drift alerts on a claim's verdict.",
        "The buyer is an engineering org with a merge gate.",
    ], size=12.5, maxw=0.380)

    panel(fig, (0.520, 0.430, 0.425, 0.330))
    say(fig, 0.540, 0.720, "WHAT WOULD VALIDATE IT", size=11.5, color=ACCENT,
        weight="bold", role="kicker")
    bullets(fig, 0.540, 0.668, [
        "Audit N public repositories and publish the base rate of VACUOUS "
        "claims. None of that is done.",
        "Then price against the review hours it redirects.",
        "Until both exist, any figure would be invented.",
    ], size=12.5, maxw=0.380)

    flow(fig, L, 0.360,
         "No revenue, no customers, no pricing validated. The business model "
         "here is a plan, not a result.",
         size=17, maxw=R - L, weight="bold", color=WARN, role="absence")
    flow(fig, L, 0.248,
         "A deck that answers the market question with a large number it did "
         "not measure scores well and is not true. Nobody here has measured the "
         "review hours redirected either. This one answers with the model, the "
         "buyer and the two experiments that would test it, and leaves the "
         "number blank until they are run.",
         size=15, maxw=R - L)
    return fig


def slide_future(F):
    fig = new_slide("What comes next, and what Bob 2.0 is for",
                    kicker="Future goals and plans")
    panel(fig, (L, 0.300, 0.425, 0.470))
    say(fig, L + 0.020, 0.730, "ROADMAP, IN PRIORITY ORDER", size=11.5,
        color=ACCENT, weight="bold", role="kicker")
    bullets(fig, L + 0.020, 0.678, [
        "Oracle sensitivity: swap a check's INPUT for noise and see whether the "
        "verdict moves at all.",
        "Warn when --max-mutants binds, and sample instead of truncating.",
        "Diff-scoping and an incremental mode, so a merge gate can run it.",
        "Languages beyond Python, which needs new AST operators per language.",
    ], size=12.5, maxw=0.380)

    panel(fig, (0.520, 0.300, 0.425, 0.470))
    say(fig, 0.540, 0.730, "THE 44-HOUR WINDOW, WITH BOB 2.0", size=11.5,
        color=ACCENT, weight="bold", role="kicker")
    bullets(fig, 0.540, 0.678, [
        "Bob 2.0 access opens at kickoff; nothing in this repository has used "
        "it and nothing here claims it has.",
        "The planned use is Agent mode and subagents on the roadmap items "
        "opposite, with every Bob-assisted file disclosed as the rules require.",
        "The auditor will then be pointed at Bob's own output, which is the "
        "sharpest test of the idea available.",
    ], size=12.5, maxw=0.380)

    flow(fig, L, 0.235,
         "Oracle sensitivity - swapping a check's input for noise - is designed "
         "and not implemented. It is in no number here.",
         size=15.5, maxw=R - L, color=WARN, role="absence")
    flow(fig, L, 0.125,
         "Python only. The AST operators and the pytest exit-code semantics "
         "read no other language.",
         size=15.5, maxw=R - L, color=WARN, role="absence")
    return fig


def slide_absences(F):
    fig = new_slide("What is not built", kicker="The ledger, on the slide")
    y = 0.775
    for _, s in absence_strings(F):
        y = flow(fig, L, y, "-  " + s, size=14.5, maxw=R - L, color=TEXT,
                 role="absence") - 0.014
    fig.add_artist(plt.Line2D([L, R], [0.185, 0.185], transform=fig.transFigure,
                              color=RULE, lw=1.2))
    flow(fig, L, 0.145,
         "An honest smaller tool beats an inflated description of a larger one, "
         "and a project whose subject is unfalsifiable claims does not get to "
         "make any.",
         size=15, maxw=R - L, color=MUTED)
    return fig


def slide_close(F):
    fig = new_slide("Reproduce every number on these slides",
                    kicker="Try it")
    say(fig, L, 0.740, "git clone https://" + REPO, size=16, family=MONO,
        color=ACCENT, role="command")
    say(fig, L, 0.685, "cd ibm-bob-2-hackathon && pip install -e .", size=16,
        family=MONO, color=ACCENT, role="command")
    say(fig, L, 0.630, "vacuity-audit audit --root . --spec vacuity.toml",
        size=16, family=MONO, color=ACCENT, role="command")
    say(fig, L, 0.575,
        "vacuity-audit audit --root examples/demo_project --spec vacuity.toml",
        size=16, family=MONO, color=ACCENT, role="command")

    panel(fig, (L, 0.230, R - L, 0.250))
    say(fig, L + 0.022, 0.440, "THE REPOSITORY, MEASURED FROM OUTSIDE",
        size=11.5, color=ACCENT, weight="bold", role="kicker")
    flow(fig, L + 0.022, 0.390, claim_text(F, "repo_state"), size=15.5,
         maxw=R - L - 0.044, role="claim")
    flow(fig, L + 0.022, 0.315, claim_text(F, "sole_author"), size=15.5,
         maxw=R - L - 0.044, role="claim")
    flow(fig, L + 0.022, 0.263,
         "Counted in a fresh anonymous clone by collect_repo_state.py, not read "
         "off the README.", size=13.5, maxw=R - L - 0.044, color=MUTED)
    say(fig, L, 0.160, "Wang Jian - solo entry - " + EVENT, size=14, color=MUTED,
        role="entrant")
    return fig


BUILDERS = [slide_title, slide_problem, slide_gap, slide_how, slide_verdicts,
            slide_self, slide_budget, slide_competition, slide_value,
            slide_market, slide_future, slide_absences, slide_close]


# --------------------------------------------------------------------- build
def build(pdf_path=PDF, sidecar_path=SIDECAR):
    recorded.clear()
    tracked.clear()
    panels.clear()
    extra_violations.clear()
    _page["n"] = 0
    e = load()
    F = facts(e)
    violations = []
    with PdfPages(pdf_path) as pdf:
        for builder in BUILDERS:
            fig = builder(F)
            violations += layout_violations(fig)
            pdf.savefig(fig, facecolor=BG)
            plt.close(fig)
        d = pdf.infodict()
        d["Title"] = TITLE
        d["Subject"] = ("Per-claim vacuity auditing for AI-assisted code review "
                        "- IBM Bob 2.0 Hackathon entry")
        d["Keywords"] = ("mutation testing, test quality, vacuous assertions, "
                         "AI code review, pytest")
    digest = hashlib.sha256(pathlib.Path(pdf_path).read_bytes()).hexdigest()
    sidecar = {
        "schema": "slides_presentation/v1",
        "pdf": "submission/slides/evidence/slides_presentation.pdf",
        "sha256": digest,
        "bytes": pathlib.Path(pdf_path).stat().st_size,
        "pages": len(BUILDERS),
        "page_size_inches": list(FIGSIZE),
        "aspect_ratio": "16:9",
        "requirement": ('lablab Hackathon Rule Book, "Cover Image and '
                        'Presentation": "Video and Slide Presentation: MP4 and '
                        'PDF formats are mandatory."'),
        "title": TITLE,
        "event": EVENT,
        "repo": REPO,
        "built_by": "submission/slides/make_slides.py",
        "built_from_head": F["head"],
        "source_date_epoch": os.environ["SOURCE_DATE_EPOCH"],
        "deterministic": ("SOURCE_DATE_EPOCH is pinned, so two builds from the "
                          "same evidence produce byte-identical PDFs."),
        "layout_violations": violations,
        "layout_check": ("every string is measured with the real font metrics; "
                         "off-page, text-on-text and text-straddling-a-panel "
                         "all fail the build"),
        "figures_derived_from": sorted(p.name for p in EV.glob("*.json")
                                       if p.name != SIDECAR.name),
        "claims": [{"label": lab, "text": s} for lab, s in claim_strings(F)],
        "absences": [{"label": lab, "text": s} for lab, s in absence_strings(F)],
        "text": list(recorded),
        "facts": {k: v for k, v in F.items() if not isinstance(v, (list, dict))},
        "not_claimed": (
            "The deck states that IBM Bob 2.0 has not been used, that "
            f"{F['self_weak']} of {F['self_total']} of the project's own claims "
            "are WEAK and none is DISCRIMINATING, that oracle sensitivity is "
            "unimplemented, that the tool is Python-only, that the verdict "
            "moves with the mutant budget, that there is no revenue, no "
            "customer and no market study, and that no hosted demo URL "
            "exists. It claims no measured market size and no measured "
            "saving."),
    }
    pathlib.Path(sidecar_path).write_text(
        json.dumps(sidecar, indent=1) + "\n", encoding="utf-8")
    return sidecar


def main():
    s = build()
    print(f"wrote {PDF} ({s['bytes']:,} bytes, {s['pages']} pages)")
    print(f"sha256 {s['sha256']}")
    print(f"wrote {SIDECAR} ({len(s['text'])} recorded strings)")
    if s["layout_violations"]:
        print(f"\nLAYOUT FAILED: {len(s['layout_violations'])} violation(s)")
        for v in s["layout_violations"][:30]:
            print("  ", json.dumps(v))
        return 1
    print("layout: 0 violations (off-page, text-on-text, text-on-panel-edge)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
