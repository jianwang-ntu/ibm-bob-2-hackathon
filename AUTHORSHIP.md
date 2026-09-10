# Authorship and provenance

This file exists because a hackathon entry makes an implicit claim about who
made it, and that claim should be checkable rather than assumed.

## The entry

A **solo** entry to the [IBM Bob 2.0 hackathon](https://lablab.ai/ai-hackathons/ibm-bob-2-hackathon)
by [**@jianwang-ntu**](https://github.com/jianwang-ntu). One entrant. There is
no team, and no second person has contributed to this repository.

## Who wrote the code

**Every line of code in this repository was written by an autonomous AI coding
agent** (Anthropic's Claude, driven by Claude Code) running unattended on the
entrant's behalf. It was not typed by a human, and this repository does not
claim otherwise anywhere.

The disclosure is also machine-readable: the commit that landed the codebase
carries a `Co-Authored-By:` trailer naming the model. `git log` shows it.

This is stated up front for two reasons:

1. It is a hackathon about AI-assisted development. How the code was produced
   is part of the entry, not a footnote to it.
2. Judging criterion *Application of Technology* asks for "a clear application
   of IBM Bob 2.0". **IBM Bob 2.0 has not been used here** — access arrives at
   the start of the event. See [`ENTRY_STATUS.md`](ENTRY_STATUS.md). An agent
   having written the code is not a substitute for that, and is not offered as
   one.

## What is not in the repository

- No vendored third-party source. All 29 tracked files are first-party.
- No runtime dependencies (`pyproject.toml`: `dependencies = []`). `pytest` is
  a development extra and is not shipped as part of the tool.
- No code carried over from another project.

## Correction, 2026-09-10 — commit author metadata

Recorded rather than quietly overwritten, which is the convention this
repository already uses in [`ENTRY_STATUS.md`](ENTRY_STATUS.md).

When the codebase commit was first pushed, its git author and committer fields
had been set to a personal name and email address that resolve to **a GitHub
account other than the entrant's**. GitHub therefore displayed the entry's
whole codebase as the work of a second, differently-named individual, on an
entry declared solo. Nothing about the code was wrong; the metadata was.

It was corrected the same day: the commit was re-authored to the entrant's own
account — the identity the repository's three earlier commits already used —
and `main` was force-updated. The commit's **tree is byte-identical** across
the correction (`ebc79c2d8f33e79dd5cf3156ff5931567e17287f` before and after),
as is the commit message, so no content changed and the AI co-author trailer is
intact.

The personal email address that had been published in that commit object is
not reproduced here, and the repository now uses a no-reply address throughout.
