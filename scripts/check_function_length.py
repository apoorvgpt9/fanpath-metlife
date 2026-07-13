"""AST-based function-length check for the fanpath-metlife codebase.

Walks every ``.py`` file under ``app/`` and flags any function whose line span
exceeds :data:`MAX_FUNCTION_LINES`. Uses ``ast`` (not grep) so decorators and
formatting quirks cannot fool it.

Exit code 1 if any violations, 0 otherwise. Also exits 0 (with a message) if
``app/`` does not exist yet — expected during early phases of the build.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_FUNCTION_LINES = 80

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"


def _iter_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _check_file(path: Path) -> list[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: unreadable ({exc})"]
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: syntax error ({exc.msg})"]

    violations: list[str] = []
    for node in _iter_functions(tree):
        end = getattr(node, "end_lineno", None)
        if end is None:
            continue
        length = end - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            rel = path.relative_to(REPO_ROOT)
            violations.append(
                f"{rel}:{node.lineno} {node.name}() is {length} lines "
                f"(max {MAX_FUNCTION_LINES})"
            )
    return violations


def main() -> int:
    if not APP_DIR.exists():
        print(f"no violations (app/ not present yet — max {MAX_FUNCTION_LINES})")
        return 0

    py_files = sorted(APP_DIR.rglob("*.py"))
    if not py_files:
        print(f"no violations (no .py files in app/ — max {MAX_FUNCTION_LINES})")
        return 0

    all_violations: list[str] = []
    for path in py_files:
        all_violations.extend(_check_file(path))

    if not all_violations:
        print(f"no violations ({len(py_files)} file(s) checked, max {MAX_FUNCTION_LINES})")
        return 0

    for line in all_violations:
        print(line)
    print(f"\n{len(all_violations)} function(s) exceed {MAX_FUNCTION_LINES} lines")
    return 1


if __name__ == "__main__":
    sys.exit(main())
