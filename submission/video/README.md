# Video presentation

The video the lablab submission form asks for.

> **Video and Slide Presentation:** MP4 and PDF formats are mandatory.
> — lablab.ai Hackathon Rule Book, *Cover Image and Presentation*

> Provide a link to your video presentation (ensure it's under 300MB and within
> 5 minutes duration).
> — lablab.ai Submission Guidelines

| | |
|---|---|
| file | `evidence/video_presentation.mp4` |
| length | 3:24.7, inside the window `[3:00, 5:00)` |
| size | 2.79 MB against a 300 MB cap |
| frame | 1920 × 1080 (`1920 × 9 == 1080 × 16`) |
| audio | **none — the video is silent, and nothing here implies narration** |
| build | `python3 make_video.py` |
| controls | `python3 check_video.py` |
| mutants | `python3 mutate_video.py` |

The Rule Book's criterion 1 band 2 penalises a presentation under three
minutes, and the Guidelines cap it at five. `make_video.py` **refuses to write
the file** outside `[180, 300)` seconds rather than leaving that to review.

## It shows the thing running, not slides of it running

Every terminal frame is a byte-for-byte replay of stdout captured from a **real
run**, in a credential-free clone of this repository, on the machine that built
it. The captures ship in `evidence/captures/` with their return codes:

| capture | command | exit |
|---|---|---|
| `repo_tests` | `python3 -m pytest -q` | 0 — 64 passed |
| `demo_pytest` | `python3 -m pytest tests -q` in `examples/demo_project` | 0 — 8 passed |
| `demo_audit` | `vacuity_auditor audit --root . --spec vacuity.toml` | 3 — WEAK, 8/9 against 2/9 |
| `self_scan` | `vacuity_auditor scan --root .` | 1 — 5 candidates in its own tests |

`check_video.py` does not take those files on trust. It clones this repository
again, re-runs all four commands, and compares the return code and the output.

## A video has no text stream

A PDF can be checked by extracting its text. A PNG has none, but it has one
frame. An MP4 has none and has five thousand — so a figure shown in one would
normally be read by a judge and by nothing else. On an entry whose whole subject
is checks that cannot go red, that would be the exact defect the tool exists to
find.

So every string sits at an **integer pixel origin**, the sidecar records the
frame each checkable string is fully drawn on, and `check_video.py` decodes that
frame out of the shipped MP4 and finds the string in its pixels by zero-mean
normalised cross-correlation. Measured on the shipped file: true lines score
**0.999572** at worst; a one-character corruption of a true line scores
**0.608**; unrelated strings score **0.16–0.38**. The bar is exactness.

## Known, and stated rather than fixed away

- **It is silent.** There is no narration. `check_video.py` asserts both that
  the file has no audio stream and that the sidecar says so, so no downstream
  text can imply one.
- **The survivor order is not stable.** `demo_audit` fans its mutants across
  four workers and prints survivors in completion order, so re-running it gives
  the same survivors in a different order. Measured over three runs on
  2026-09-10. The live control therefore compares the return code and the
  **multiset** of output lines, and reports separately whether the order also
  matched — demanding byte-identical output would be a control that goes red for
  something that is not a defect, and relaxing it to a substring match would be
  one that cannot go red at all.
- **IBM Bob 2.0 has not been used.** The video says so on its own title card and
  again in its ledger, and a control refuses any affirmative claim that it was.

## The campaign found a control that could not fail

The first version of `reject_a_terminal_line_that_is_not_in_its_capture`
asserted only that a *corrupted* line fails to join its capture. No corruption
of the artifact can falsify that — a refusal arm with no accept arm is precisely
the thing this project exists to detect, and `mutate_video.py` reported it as an
unfalsified control rather than counting a clean sweep. It now also requires the
uncorrupted line to join, and is killed by an existing mutant.

`mutate_video.py`: 13 mutants, **13 killed on their named control**, 14 of 17
controls driven red by at least one mutant. The remaining three are named in
`evidence/video_mutants.json` with the reason each is not mutated.
