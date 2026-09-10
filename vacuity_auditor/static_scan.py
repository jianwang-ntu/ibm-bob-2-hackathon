"""Static patterns that make a check unable to go red.

Everything here is a CANDIDATE, never a verdict. A static pattern cannot prove
vacuity -- `assert result is not None` is vacuous when the callee always returns
an object and load-bearing when it can return None, and the difference is not
visible in the test file. Static findings exist to say *where to point the
mutation campaign*, which is the part that actually decides.

The patterns are the ones observed to survive review:

  no_assertion            a test that asserts nothing at all
  constant_assertion      `assert True`, `assert 1`, `assert "text"`
  self_comparison         `assert x == x`
  swallowed_assertion     the assert sits under `except: pass`
  unconditional_skip      the body is skipped before it can fail
  presence_only           the only assertion checks existence or type
  empty_body              the body is `pass` or `...`
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

PRESENCE_ONLY_FUNCS = {"len", "isinstance", "hasattr", "type", "bool", "callable"}


@dataclasses.dataclass
class Finding:
    pattern: str
    relative_path: str
    lineno: int
    test_name: str
    detail: str

    def to_dict(self) -> dict[str, str | int]:
        return dataclasses.asdict(self)


def _is_test(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
        and node.name.startswith("test")


def _asserts(fn: ast.AST) -> list[ast.AST]:
    found: list[ast.AST] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            found.append(node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr.startswith(("assert", "assertRaises")):
            found.append(node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in {"raises", "warns"}:
            found.append(node)
    return found


def _constant_truthy(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and bool(node.value)


def _self_comparison(test: ast.AST) -> bool:
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    try:
        return ast.dump(test.left) == ast.dump(test.comparators[0])
    except Exception:
        return False


def _presence_only(node: ast.Assert) -> str | None:
    """True when the assertion cannot distinguish a right answer from a wrong one."""
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1 \
            and isinstance(test.ops[0], (ast.Is, ast.IsNot)) \
            and isinstance(test.comparators[0], ast.Constant) \
            and test.comparators[0].value is None:
        return "asserts only that a value is (not) None"
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) \
            and test.func.id in PRESENCE_ONLY_FUNCS:
        return f"asserts only `{test.func.id}(...)`, which holds for a wrong value too"
    if isinstance(test, ast.Name):
        return "asserts only that a name is truthy"
    return None


def _has_unconditional_skip(fn: ast.AST) -> str | None:
    for deco in getattr(fn, "decorator_list", []):
        dumped = ast.dump(deco)
        if "'skip'" in dumped or "'xfail'" in dumped:
            return "decorated skip/xfail"
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in {"skip", "xfail"}:
            # only counts when it is not guarded by a condition
            if not _inside_conditional(fn, node):
                return f"unconditional pytest.{node.func.attr}() in the body"
    return None


def _inside_conditional(fn: ast.AST, target: ast.AST) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.Try)):
            for child in ast.walk(node):
                if child is target:
                    return True
    return False


def _swallowed(fn: ast.AST) -> str | None:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        body_has_assert = any(isinstance(n, ast.Assert) for b in node.body for n in ast.walk(b))
        if not body_has_assert:
            continue
        for handler in node.handlers:
            only_pass = all(isinstance(s, ast.Pass) for s in handler.body) or (
                len(handler.body) == 1 and isinstance(handler.body[0], ast.Expr)
                and isinstance(handler.body[0].value, ast.Constant)
                and handler.body[0].value.value is Ellipsis
            )
            if only_pass:
                return "an assertion sits inside try/except that swallows the failure"
    return None


def _empty_body(fn: ast.AST) -> bool:
    body = [s for s in fn.body if not (isinstance(s, ast.Expr)
                                       and isinstance(s.value, ast.Constant)
                                       and isinstance(s.value.value, str))]
    if not body:
        return True
    return all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr)
               and isinstance(s.value, ast.Constant)
               and s.value.value is Ellipsis) for s in body)


def scan_source(source: str, relative_path: str) -> list[Finding]:
    tree = ast.parse(source)
    findings: list[Finding] = []
    for fn in ast.walk(tree):
        if not _is_test(fn):
            continue
        name, line = fn.name, fn.lineno

        skip = _has_unconditional_skip(fn)
        if skip:
            findings.append(Finding("unconditional_skip", relative_path, line, name, skip))

        if _empty_body(fn):
            findings.append(Finding("empty_body", relative_path, line, name,
                                    "body is `pass`/`...` -- nothing can fail"))
            continue

        asserts = _asserts(fn)
        if not asserts:
            findings.append(Finding("no_assertion", relative_path, line, name,
                                    "test body contains no assertion of any kind"))
            continue

        swallow = _swallowed(fn)
        if swallow:
            findings.append(Finding("swallowed_assertion", relative_path, line, name, swallow))

        real_assertions = 0
        for node in asserts:
            if isinstance(node, ast.Assert):
                if _constant_truthy(node.test):
                    findings.append(Finding("constant_assertion", relative_path,
                                            node.lineno, name,
                                            f"asserts the constant {ast.unparse(node.test)}"))
                    continue
                if _self_comparison(node.test):
                    findings.append(Finding("self_comparison", relative_path,
                                            node.lineno, name,
                                            f"asserts `{ast.unparse(node.test)}`"))
                    continue
                weak = _presence_only(node)
                if weak:
                    findings.append(Finding("presence_only", relative_path,
                                            node.lineno, name, weak))
                    continue
            real_assertions += 1
        _ = real_assertions
    return findings


def scan_path(path: Path, root: Path) -> list[Finding]:
    path, root = Path(path), Path(root)
    files = [path] if path.is_file() else sorted(path.rglob("test_*.py")) + sorted(path.rglob("*_test.py"))
    findings: list[Finding] = []
    for f in files:
        try:
            findings.extend(scan_source(f.read_text(encoding="utf-8"),
                                        str(f.relative_to(root))))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
    return findings
