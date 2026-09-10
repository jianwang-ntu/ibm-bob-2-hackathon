# Slide presentation

The lablab Hackathon Rule Book, under "Cover Image and Presentation", says:

> Video and Slide Presentation: MP4 and PDF formats are mandatory.

`evidence/slides_presentation.pdf` is that deck — 13 pages, 16:9.

**It is generated, not authored.** `make_slides.py` reads `evidence/*.json` and
prints no figure it did not read there. `check_slides.py` re-derives every figure
independently, extracts the text from the *shipped PDF bytes*, and fails if the
deck stops matching; it also rebuilds the deck in a temporary directory and
requires the result to be byte-identical to the file that ships.

```bash
python3 collect_repo_state.py   # measure the public repo (one anonymous clone)
python3 make_slides.py          # -> evidence/slides_presentation.pdf
python3 check_slides.py         # 14 controls over the shipped bytes
```

The evidence the deck is built from:

| file | what it is |
|---|---|
| `evidence/self_audit.json` | `vacuity-audit audit --root . --spec vacuity.toml --max-mutants 10` |
| `evidence/demo_audit_12.json` | the same, on `examples/demo_project`, budget 12 |
| `evidence/demo_audit_4.json` | the same, budget 4 — the verdict flip the README warns about |
| `evidence/repo_state.json` | a fresh anonymous clone, counted and test-run |
| `evidence/slides_controls.json` | the control run's own output |

Two things are deliberately true of this deck:

- **Slide 12 is an absence ledger** and eight of its lines are asserted by
  `check_slides.py`, so they cannot be quietly dropped. IBM Bob 2.0 has not been
  used on this project; nothing in the repository's own audit is
  `DISCRIMINATING`; there is no revenue, no customer and no market study.
- **No market size or saving is given**, because none was measured. The market
  slide gives the model, the buyer and the two experiments that would test it,
  and leaves the number blank.

The figures about the repository itself are pinned to commit
`2259a4e8316fd4a620780fa6d9ccb7d5b19f95cb` — the head they were measured at,
which is the commit *before* this directory was added. Re-run
`collect_repo_state.py` to measure the current head.
