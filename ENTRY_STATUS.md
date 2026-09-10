# Hackathon entry status

Public repository for a **solo** entry to the
[IBM Bob 2.0 hackathon](https://lablab.ai/ai-hackathons/ibm-bob-2-hackathon)
on lablab.ai, by [Jian Wang](https://github.com/jianwang-ntu).
Build window: **2026-09-25T19:00Z → 2026-09-27T15:00Z**.
The project itself is documented in [`README.md`](README.md).

---

## Correction, 2026-09-10T13:00Z — "it cannot honestly be pre-built" was too strong

This file supersedes the status section of the README as it stood at commit
`6fc4b00`. The correction is recorded rather than quietly overwritten, which is
the convention the previous commit set.

**What the earlier text said.** That the entry "must be built **with** Bob
2.0 — the event's Important Requirements ask for the code Bob assisted with and
for screenshots of Bob task session summaries — so it cannot honestly be
pre-built", and that "project code will land here during that window, and not
before".

**Why that was stronger than the published rules support.** Three measurements
against the canonical corpus snapshotted at `rules_canonical_20260909T2300Z`
(event page, Rule Book, Submission Guidelines, Terms of Use):

1. The Important Requirement reads *"Include **any** code or files where IBM
   Bob 2.0 assisted in the development."* It requires that Bob-assisted work be
   disclosed. It does not require that all work be Bob-assisted, and it does not
   bar work that predates the window.
2. No clause in any of the four canonical surfaces requires the project to have
   been built during the event. A search for "during the hackathon / must be
   built / from scratch / pre-existing / prior work" returns one hit, and it is
   advisory: *"…that you can prototype quickly during the hackathon."*
3. The event page's own Hackathon Details section says the opposite of a bar:
   *"🧠 Get prepared — … **Get a head start on your project using the resources
   on lablab.ai!**"*

**What is unchanged.** Everything the earlier text said about Bob 2.0 access is
still true and still binding on this entry:

- Access to IBM Bob 2.0 arrives at the start of the hackathon (*"Access details
  TBA"*). **Bob 2.0 has not been used on this repository.**
- `req_bob_assisted_code` and `req_bob_session_screenshots` are therefore
  unsatisfied, and are not claimed anywhere in this repository.
- The judging criterion *Application of Technology* asks for "a clear
  application of IBM Bob 2.0", and nothing here addresses it yet.

**What changed in practice.** The head start is a working, tested tool with its
own honest audit of itself. The Bob 2.0 work — applying Agent mode, parallel
tasks, subagents and document understanding to this codebase, and disclosing
exactly which files it touched — happens in the window, on top of it.

## What is in this repository as of 2026-09-10

| Path | What it is | Built with Bob 2.0? |
|---|---|---|
| `vacuity_auditor/` | the tool: 9 modules | no |
| `tests/` | 64 tests, all passing | no |
| `examples/demo_project/` | worked example: two green suites, one of them not evidence | no |
| `evidence/self_audit.json` | the tool's audit of its own test suite | no |
| `vacuity.toml` | the self-audit claim spec | no |
| `LICENSE` | the MIT License | — |

## Licence

MIT — see [`LICENSE`](LICENSE).

This is not a preference. lablab.ai's Terms of Use, §16 Participation Terms,
requires it:

> All submissions by participants must be original work, open source, and
> compliant with the MIT License unless specified otherwise.

and the lablab.ai Rule Book requires the repository itself:

> Public GitHub Repository: Mandatory for storing your code.
