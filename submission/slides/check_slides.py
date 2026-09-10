#!/usr/bin/env python3
"""Controls for evidence/slides_presentation.pdf -- the mandatory slide deck.

A deck is a submission's most quotable artifact and its least checked one: the
numbers on it are read by a judge and by nobody else.  So this suite treats the
SHIPPED PDF BYTES as the thing under test, not the script that made them.

  claims     ACCEPT every figure on the slides is re-derived HERE from
             evidence/*.json and found in the text extracted from the PDF;
             REJECT a corrupted figure, and REJECT the deck going stale when
             the EVIDENCE moves underneath it
  honesty    ACCEPT the deck states every absence the entry is required to
             state -- no IBM Bob 2.0, nothing DISCRIMINATING, no oracle
             sensitivity, Python only, the budget caveat, no revenue, no market
             study, no demo URL; REJECT an inflated verdict count and REJECT
             the ledger being deleted
  bytes      ACCEPT the shipped PDF is exactly what make_slides.py produces
             from today's evidence, is 16:9 and has the page count the sidecar
             claims; REJECT a sidecar sha256 that does not match the file
  layout     ACCEPT the build's own layout check found nothing; REJECT a
             deliberately broken layout going unreported

The claim strings are RE-DERIVED in this file rather than imported from the
builder: two implementations that have to agree.  The corruptions are derived
from the artifact rather than pinned to literals, so they keep corrupting after
the measurements move -- a corruption that changes nothing is reported BAD, not
credited.

  python3 check_slides.py

Needs pypdf (to read the shipped bytes) and matplotlib (to rebuild).  A missing
one is a FAILURE, not a skip: a control that quietly does not run is worse than
no control.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
EV = HERE / "evidence"
PDF = EV / "slides_presentation.pdf"
SIDECAR = EV / "slides_presentation.json"

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

    Re-derived here on purpose.  `mutants_applied` counts runs where the check
    never executed, and printing the kill count over THAT denominator is the
    exact defect the audited project documents having made once.
    """
    return c["mutants_applied"] - c["mutants_did_not_run"]


def claims_from_evidence(e: dict) -> list[tuple[str, str]]:
    """Every figure the deck is allowed to print, rendered as it must appear."""
    s, d12, d4, repo = e["self"], e["demo12"], e["demo4"], e["repo"]
    real12 = pick(d12, "real_suite_verifies_pricing")
    vac12 = pick(d12, "vacuous_suite_verifies_pricing")
    real4 = pick(d4, "real_suite_verifies_pricing")
    worst = min(s["claims"], key=lambda c: c["mutants_killed"] / evidential(c))
    static_n = len(s["claims"][0]["static_findings"])
    no_assert = sum(1 for f in s["claims"][0]["static_findings"]
                    if f["pattern"] == "no_assertion")
    demo_static = len(d12["claims"][0]["static_findings"])
    return [
        ("headline_self",
         f"{s['summary']['weak']} of {s['summary']['total']} claims come back "
         f"WEAK, {s['summary']['discriminating']} DISCRIMINATING."),
        ("worst_self",
         f"The worst is {worst['claim_id']} at {worst['mutants_killed']} / "
         f"{evidential(worst)}."),
        ("demo_split",
         f"{real12['mutants_killed']} / {evidential(real12)} against "
         f"{vac12['mutants_killed']} / {evidential(vac12)}, and pytest calls "
         f"both green."),
        ("budget_flip",
         f"At a budget of 4 the same suite reports {real4['verdict']} "
         f"{real4['mutants_killed']} / {evidential(real4)}; at 12 it reports "
         f"{real12['verdict']} {real12['mutants_killed']} / "
         f"{evidential(real12)}."),
        ("repo_state",
         f"{repo['tracked_files']} tracked files, {repo['module_count']} "
         f"modules, {repo['test_file_count']} test files, "
         f"{repo['tests_passed_in_clone']} tests passing in a clean anonymous "
         f"clone at {repo['head'][:8]}."),
        ("sole_author",
         f"{repo['commit_count']} commits, "
         f"{len(repo['distinct_commit_authors'])} commit author, "
         f"{repo['licence']} licensed."),
        ("demo_static_scan",
         f"The static scan flags {demo_static} vacuity candidates in the "
         f"worked example before anything is executed."),
        ("self_static_scan",
         f"In this repository's own tests it flags {static_n} candidates, of "
         f"which {no_assert} is a no_assertion true positive."),
        # Table cells: the per-claim rows on slides 3 and 6, checked as pairs so
        # a row cannot be silently dropped or re-scored.
        *[(f"self_row_{c['claim_id']}",
           f"{c['claim_id']} {c['verdict']} {c['mutants_killed']} / "
           f"{evidential(c)}") for c in s["claims"]],
    ]


def absences_from_evidence(e: dict) -> list[tuple[str, str]]:
    """The absences the deck is required to state. Checked, so they cannot be cut."""
    s = e["self"]
    return [
        ("no_bob",
         "IBM Bob 2.0 has not been used on this project. Access opens at "
         "kickoff and nothing here claims otherwise."),
        ("no_discriminating",
         f"Nothing in this repository's own audit is DISCRIMINATING: "
         f"{s['summary']['weak']} of {s['summary']['total']} claims are WEAK."),
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


# ----------------------------------------------------------------- the bytes
def normalise(s: str) -> str:
    """Strip ALL whitespace before comparing.

    A PDF text stream breaks on kerning pairs, so pypdf returns "T ask success"
    for a line reading "Task success", and a wrapped claim arrives split across
    lines.  Neither is a defect in the deck, and collapsing runs of whitespace
    does not fix the first.  Comparing whitespace-free strings does, and still
    catches every changed character and digit.
    """
    return re.sub(r"\s+", "", s)


def pdf_text(path: pathlib.Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return normalise("\n".join(p.extract_text() or "" for p in reader.pages))


def missing(text: str, claims) -> list[str]:
    return [label for label, s in claims if normalise(s) not in text]


def corrupt(claim: str) -> str:
    """Break a claim the way a stale deck breaks: bump its first number.

    Derived from the claim, not pinned to a literal, so it keeps corrupting
    after the measurements move.  A claim with no number has two adjacent
    differing characters transposed -- dropping its last word was tried on an
    earlier deck and was useless, because a prefix of a true sentence is still
    in the document.
    """
    m = re.search(r"\d+", claim)
    if m:
        return claim[:m.start()] + str(int(m.group()) + 1) + claim[m.end():]
    body = claim.rstrip()
    for i in range(len(body) - 1, 0, -1):
        if body[i] != body[i - 1] and not body[i].isspace() and not body[i - 1].isspace():
            return body[:i - 1] + body[i] + body[i - 1] + body[i + 1:]
    return body + "X"


def main() -> int:
    for mod in ("pypdf", "matplotlib"):
        try:
            __import__(mod)
        except ImportError as exc:
            check(f"dependency_{mod}", False, f"{exc} -- controls cannot run")
            return 1

    if not PDF.exists() or not SIDECAR.exists():
        check("artifacts_exist", False, f"missing {PDF.name} or {SIDECAR.name}")
        return 1

    e = load_evidence(EV)
    claims = claims_from_evidence(e)
    absences = absences_from_evidence(e)
    text = pdf_text(PDF)
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    ok = True

    # ---------------------------------------------------------------- claims
    gaps = missing(text, claims)
    ok &= check("accept_every_figure_is_in_the_pdf", not gaps,
                f"{len(claims) - len(gaps)} / {len(claims)} figures found in "
                f"the shipped bytes" + (f"; missing {gaps}" if gaps else ""))

    # A corruption that changes nothing would be scored against an artifact it
    # never touched.  Guard it explicitly rather than trusting the operator.
    noop = [lab for lab, s in claims if corrupt(s) == s]
    ok &= check("reject_a_noop_corruption", not noop,
                "every corruption changes its claim"
                if not noop else f"corruption is a no-op for {noop}")

    broken = [(f"{lab}_corrupt", corrupt(s)) for lab, s in claims]
    survived = [b[0] for b in broken if b[0] not in missing(text, broken)]
    ok &= check("reject_a_corrupted_figure", not survived,
                f"{len(broken)} corrupted figures, "
                f"{len(broken) - len(survived)} correctly absent"
                + (f"; still found {survived}" if survived else ""))

    # The deck must go stale when the EVIDENCE moves, not only when the deck does.
    moved = json.loads(json.dumps(e))
    moved["self"]["claims"][0]["mutants_killed"] += 1
    moved["repo"]["tests_passed_in_clone"] += 1
    stale = missing(text, claims_from_evidence(moved))
    ok &= check("reject_the_pdf_when_the_evidence_moves", bool(stale),
                f"one extra kill and one extra passing test in the evidence "
                f"make {len(stale)} figure(s) stop matching: {stale[:4]}")

    # -------------------------------------------------------------- honesty
    hgaps = missing(text, absences)
    ok &= check("accept_every_absence_is_stated", not hgaps,
                f"{len(absences) - len(hgaps)} / {len(absences)} absences "
                f"stated on the slides"
                + (f"; missing {hgaps}" if hgaps else ""))

    total = e["self"]["summary"]["total"]
    inflated = [(f"inflated_{n}", f"{n} of {total} claims come back "
                                  f"DISCRIMINATING")
                for n in range(1, total + 1)]
    inflated += [(f"inflated_disc_{n}",
                  f"{e['self']['summary']['weak']} of {total} claims come back "
                  f"WEAK, {n} DISCRIMINATING.") for n in range(1, total + 1)]
    found = [lab for lab, s in inflated if normalise(s) in text]
    ok &= check("reject_an_inflated_verdict_count", not found,
                f"none of {len(inflated)} inflated verdict strings appears"
                if not found else f"deck claims {found}")

    scrubbed = text
    for _, s in absences:
        scrubbed = scrubbed.replace(normalise(s), "")
    ok &= check("reject_a_deck_with_the_absences_deleted",
                len(missing(scrubbed, absences)) == len(absences),
                f"with the ledger removed all {len(absences)} absence controls "
                f"report missing")

    # ---------------------------------------------------------------- bytes
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    ok &= check("accept_sidecar_matches_the_file", digest == side["sha256"],
                f"sha256 {digest[:16]} == sidecar {side['sha256'][:16]}"
                if digest == side["sha256"] else
                f"sha256 {digest[:16]} != sidecar {side['sha256'][:16]}")
    ok &= check("reject_a_sidecar_sha_that_does_not_match",
                corrupt(side["sha256"]) != digest,
                "a one-character change to the recorded sha256 stops matching")

    from pypdf import PdfReader
    reader = PdfReader(str(PDF))
    box = reader.pages[0].mediabox
    ratio = float(box.width) / float(box.height)
    ok &= check("accept_pages_and_aspect_ratio",
                len(reader.pages) == side["pages"] and abs(ratio - 16 / 9) < 0.01,
                f"{len(reader.pages)} pages (sidecar says {side['pages']}), "
                f"{float(box.width):.0f}x{float(box.height):.0f} pt, "
                f"ratio {ratio:.4f}")
    ok &= check("accept_pdf_is_the_format_the_rules_name",
                PDF.read_bytes()[:5] == b"%PDF-",
                'the Rule Book requires PDF; the file starts with the PDF magic')

    # the strongest link: the shipped bytes ARE this builder's output today
    sys.path.insert(0, str(HERE))
    import make_slides                                          # noqa: E402
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = pathlib.Path(tmp) / "rebuild.pdf"
        side2 = make_slides.build(rebuilt, pathlib.Path(tmp) / "rebuild.json")
        same = hashlib.sha256(rebuilt.read_bytes()).hexdigest() == digest
        ok &= check("accept_shipped_bytes_are_the_builder_output_today", same,
                    "a fresh build from today's evidence is byte-identical"
                    if same else
                    "a fresh build DIFFERS from the shipped PDF -- the deck is "
                    "stale or was hand-edited")
        ok &= check("accept_layout_check_is_clean",
                    not side2["layout_violations"],
                    f"{len(side2['layout_violations'])} layout violations on "
                    f"the rebuild")

        # ...and the layout check itself has to be able to fail
        import matplotlib.pyplot as plt
        probe = plt.figure(figsize=make_slides.FIGSIZE)
        overlong = ("A deliberately overlong slide title used only as a "
                    "negative control for the layout checker")
        fired = len(make_slides.wrap(probe, overlong, 27,
                                     make_slides.R - make_slides.L,
                                     weight="bold")) > 1
        shortest = min((s for s in (side2["text"]) if s["role"] == "title"),
                       key=lambda s: len(s["text"]))["text"]
        quiet = len(make_slides.wrap(probe, shortest, 27,
                                     make_slides.R - make_slides.L,
                                     weight="bold")) == 1
        plt.close(probe)
        ok &= check("reject_a_title_that_would_collide_with_the_rule",
                    fired and quiet,
                    f"the title-wrap detector fires on an overlong title and "
                    f"stays quiet on the deck's own shortest title "
                    f"({shortest[:40]!r})")

    (EV / "slides_controls.json").write_text(json.dumps({
        "schema": "slides_controls/v1",
        "artifact": "submission/slides/evidence/slides_presentation.pdf",
        "sha256": digest,
        "figures_checked": len(claims),
        "absences_checked": len(absences),
        "all_pass": bool(ok),
        "controls": results,
    }, indent=1) + "\n", encoding="utf-8")

    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{len(results)} controls pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
