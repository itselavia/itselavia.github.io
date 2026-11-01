"""AST static analysis, strict typing enforcement, complexity checks, and file formatting."""

from __future__ import annotations

import ast
from pathlib import Path
import re

SNAKE_CASE_RE: re.Pattern[str] = re.compile(r"^_?[a-z][a-z0-9_]*$|^__[a-z0-9_]+__$")
PASCAL_CASE_RE: re.Pattern[str] = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
UNTRACKED_DEBT_RE: re.Pattern[str] = re.compile(
    r"(?:#|<!--|/\*)\s*(TODO|FIXME|HACK|XXX)(?!\(#\d+\))\b"
)

MAX_SOURCE_LINES: int = 600
MAX_CYCLOMATIC_COMPLEXITY: int = 10

FORMATTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {".html", ".css", ".md", ".yml", ".yaml", ".json", ".py", ".toml"}
)
EXCLUDED_WALK_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "_site",
        "vendor",
        "node_modules",
        ".bundle",
        ".jekyll-cache",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def compute_cyclomatic_complexity(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    """Compute McCabe cyclomatic complexity for a Python AST function node."""
    complexity = 1
    branch_types = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ExceptHandler,
        ast.IfExp,
        ast.comprehension,
    )
    for node in ast.walk(func_node):
        if isinstance(node, branch_types):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
    return complexity


def _validate_python_function(
    rel: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[str]:
    """Validate naming, strict type annotations, and complexity for one Python function."""
    errors: list[str] = []
    if not SNAKE_CASE_RE.match(node.name):
        errors.append(f"{rel}:{node.lineno}: function '{node.name}' must use snake_case")
    if node.returns is None:
        errors.append(
            f"{rel}:{node.lineno}: function '{node.name}' is missing return type annotation"
        )
    all_args = (
        list(node.args.posonlyargs)
        + list(node.args.args)
        + list(node.args.kwonlyargs)
    )
    for arg in all_args:
        if arg.arg not in ("self", "cls") and arg.annotation is None:
            errors.append(
                f"{rel}:{node.lineno}: parameter '{arg.arg}' in '{node.name}' is missing type annotation"
            )
    complexity = compute_cyclomatic_complexity(node)
    if complexity > MAX_CYCLOMATIC_COMPLEXITY:
        errors.append(
            f"{rel}:{node.lineno}: function '{node.name}' has cyclomatic complexity {complexity} (> {MAX_CYCLOMATIC_COMPLEXITY})"
        )
    return errors


def check_python_code_quality(repo_root: Path) -> list[str]:
    """Enforce strict typing, naming conventions, and cyclomatic complexity across Python files."""
    errors: list[str] = []
    for py_path in sorted(repo_root.rglob("*.py")):
        rel = py_path.relative_to(repo_root)
        if any(part in EXCLUDED_WALK_DIRS for part in rel.parts):
            continue
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(rel))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not PASCAL_CASE_RE.match(node.name):
                errors.append(
                    f"{rel}:{node.lineno}: class '{node.name}' must use PascalCase"
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                errors.extend(_validate_python_function(rel, node))
    return errors


def _check_single_file_hygiene(path: Path, rel: Path, fix: bool) -> list[str]:
    """Check or normalize one file for line limit, untracked tech debt, and whitespace."""
    errors: list[str] = []
    raw_text = path.read_text(encoding="utf-8")
    raw_lines = raw_text.splitlines()
    if len(raw_lines) > MAX_SOURCE_LINES:
        errors.append(
            f"{rel}: file has {len(raw_lines)} lines (exceeds limit of {MAX_SOURCE_LINES})"
        )

    for idx, line in enumerate(raw_lines, start=1):
        if UNTRACKED_DEBT_RE.search(line):
            errors.append(
                f"{rel}:{idx}: untracked tech debt marker must cite an issue like TODO(#123)"
            )

    normalized_lines = [line.rstrip(" \t\r") for line in raw_lines]
    normalized = "\n".join(normalized_lines) + "\n" if normalized_lines else ""
    if raw_text != normalized:
        if fix:
            path.write_text(normalized, encoding="utf-8")
        else:
            errors.append(
                f"{rel}: formatting check failed (trailing whitespace or missing final newline; run 'python3 scripts/validate_site.py --format')"
            )
    return errors


def check_or_format_files(repo_root: Path, fix: bool = False) -> list[str]:
    """Check or normalize formatting, file length limits, and untracked tech debt markers."""
    errors: list[str] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file() or path.suffix not in FORMATTABLE_EXTENSIONS:
            continue
        rel = path.relative_to(repo_root)
        if any(part in EXCLUDED_WALK_DIRS for part in rel.parts):
            continue
        errors.extend(_check_single_file_hygiene(path, rel, fix))
    return errors
