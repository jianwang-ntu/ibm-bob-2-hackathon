# demo_project

A four-line pricing function and two test files that claim to verify it.

`tests/test_pricing_real.py` checks values. `tests/test_pricing_vacuous.py`
checks that a value came back. Both are green. Only one is evidence.

Run the auditor from this directory:

```
vacuity-audit audit --root . --spec vacuity.toml
```
