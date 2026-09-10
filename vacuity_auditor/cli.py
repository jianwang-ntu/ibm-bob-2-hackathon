"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, claims, report, static_scan
from .audit import audit_claim


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vacuity-audit",
        description="Ask of a verification check: can this ever go red?")
    p.add_argument("--version", action="version", version=f"vacuity-auditor {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("audit", help="run the full audit for every claim in a spec")
    a.add_argument("--root", type=Path, default=Path("."), help="repository root")
    a.add_argument("--spec", type=Path, default=Path("vacuity.toml"),
                   help="claim spec (.toml or .json)")
    a.add_argument("--claim", action="append", default=None,
                   help="audit only this claim id (repeatable)")
    a.add_argument("--max-mutants", type=int, default=12)
    a.add_argument("--workers", type=int, default=4)
    a.add_argument("--timeout", type=float, default=600.0)
    a.add_argument("--json", type=Path, default=None, help="also write the report here")
    a.add_argument("--quiet", action="store_true")

    s = sub.add_parser("scan", help="static vacuity candidates only -- no execution")
    s.add_argument("--root", type=Path, default=Path("."))
    s.add_argument("--tests", type=Path, default=None,
                   help="tests directory or file (default: <root>/tests)")
    return p


def _cmd_scan(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    target = (args.tests or root / "tests").resolve()
    if not target.exists():
        print(f"no such path: {target}", file=sys.stderr)
        return 2
    findings = static_scan.scan_path(target, root)
    if not findings:
        print(f"no static vacuity candidates in {target}")
        return 0
    print(f"{len(findings)} static vacuity candidate(s) in {target}:")
    for f in findings:
        print(f"  {f.pattern:<22} {f.relative_path}:{f.lineno}  {f.test_name}  -- {f.detail}")
    print("\nThese locate; they do not decide. Point `audit` at them to get a verdict.")
    return 1


def _cmd_audit(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    spec = args.spec if args.spec.is_absolute() else root / args.spec
    try:
        parsed = claims.load(spec)
    except (OSError, claims.ClaimSpecError) as exc:
        print(f"claim spec error: {exc}", file=sys.stderr)
        return 2
    if args.claim:
        wanted = set(args.claim)
        missing = wanted - {c.id for c in parsed}
        if missing:
            print(f"no such claim(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
        parsed = [c for c in parsed if c.id in wanted]

    progress = None if args.quiet else (lambda m: print(m, file=sys.stderr))
    results = [audit_claim(root, c, max_mutants=args.max_mutants, workers=args.workers,
                           timeout_s=args.timeout, progress=progress) for c in parsed]
    print(report.render(results))
    if args.json:
        args.json.write_text(report.to_json(results), encoding="utf-8")
        print(f"report written to {args.json}")
    return report.exit_code(results)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return {"audit": _cmd_audit, "scan": _cmd_scan}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
