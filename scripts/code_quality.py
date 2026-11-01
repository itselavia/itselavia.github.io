"""AST static analysis, strict typing, complexity, secret scanning, and version drift checks."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re

SNAKE_CASE_RE: re.Pattern[str] = re.compile(r"^_?[a-z][a-z0-9_]*$|^__[a-z0-9_]+__$")
PASCAL_CASE_RE: re.Pattern[str] = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
UNTRACKED_DEBT_RE: re.Pattern[str] = re.compile(
    r"(?:#|<!--|/\*)\s*(TODO|FIXME|HACK|XXX)(?!\(#\d+\))\b"
)
LEAKED_SECRET_RE: re.Pattern[str] = re.compile(
    r"(?:gh[pousr]_\w{12,}|github_pat_\w{12,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
FORBIDDEN_FRAMEWORK_RE: re.Pattern[str] = re.compile(
    r"(?i)\b(?:bootstrap(?:\.min)?\.(?:css|js)|jquery(?:-[0-9.]+)?(?:\.min)?\.js)\b"
)

MAX_SOURCE_LINES: int = 600
MAX_CYCLOMATIC_COMPLEXITY: int = 10
MAX_ASSET_BYTES: int = 1_048_576

FORMATTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {".html", ".css", ".md", ".yml", ".yaml", ".json", ".py", ".toml"}
)
SECRET_SCAN_EXEMPT: frozenset[str] = frozenset(
    {"tests/test_site.py", "scripts/logger.py", "scripts/code_quality.py"}
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
    """Check or normalize one file for line limit, secrets, tech debt, and whitespace."""
    errors: list[str] = []
    raw_text = path.read_text(encoding="utf-8")
    raw_lines = raw_text.splitlines()
    if len(raw_lines) > MAX_SOURCE_LINES:
        errors.append(
            f"{rel}: file has {len(raw_lines)} lines (exceeds limit of {MAX_SOURCE_LINES})"
        )

    scan_secrets = str(rel) not in SECRET_SCAN_EXEMPT
    for idx, line in enumerate(raw_lines, start=1):
        if UNTRACKED_DEBT_RE.search(line):
            errors.append(
                f"{rel}:{idx}: untracked tech debt marker must cite an issue like TODO(#123)"
            )
        if scan_secrets and LEAKED_SECRET_RE.search(line):
            errors.append(f"{rel}:{idx}: potential leaked secret or token detected")

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
    """Check or normalize formatting, file length limits, secrets, and untracked tech debt."""
    errors: list[str] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file() or path.suffix not in FORMATTABLE_EXTENSIONS:
            continue
        rel = path.relative_to(repo_root)
        if any(part in EXCLUDED_WALK_DIRS for part in rel.parts):
            continue
        errors.extend(_check_single_file_hygiene(path, rel, fix))
    return errors


def _check_image_sizes(repo_root: Path) -> list[str]:
    """Verify all image assets under img/ stay within MAX_ASSET_BYTES."""
    img_dir = repo_root / "img"
    if not img_dir.is_dir():
        return []
    return [
        f"img/{asset.name}: asset size {asset.stat().st_size} bytes exceeds {MAX_ASSET_BYTES} bytes"
        for asset in sorted(img_dir.iterdir())
        if asset.is_file() and asset.stat().st_size > MAX_ASSET_BYTES
    ]


def _check_forbidden_frameworks(repo_root: Path) -> list[str]:
    """Verify templates and stylesheets do not reference heavy frontend frameworks."""
    errors: list[str] = []
    for folder in ("_layouts", "_includes", "css"):
        target_dir = repo_root / folder
        if not target_dir.is_dir():
            continue
        for path in sorted(target_dir.iterdir()):
            if path.is_file() and FORBIDDEN_FRAMEWORK_RE.search(
                path.read_text(encoding="utf-8")
            ):
                errors.append(
                    f"{path.relative_to(repo_root)}: forbidden heavy framework reference (Bootstrap/jQuery)"
                )
    return errors


def check_heavy_dependencies_and_assets(repo_root: Path) -> list[str]:
    """Detect forbidden heavy frontend frameworks and oversized image assets."""
    return _check_image_sizes(repo_root) + _check_forbidden_frameworks(repo_root)


def check_version_drift(repo_root: Path) -> list[str]:
    """Verify Ruby and Python versions stay synchronized across config, devcontainer, and CI."""
    ruby_ver_path = repo_root / ".ruby-version"
    pyproject_path = repo_root / "pyproject.toml"
    dev_path = repo_root / ".devcontainer" / "devcontainer.json"
    ci_path = repo_root / ".github" / "workflows" / "deploy.yml"
    if not all(p.is_file() for p in (ruby_ver_path, pyproject_path, dev_path, ci_path)):
        return []

    errors: list[str] = []
    ruby_ver = ruby_ver_path.read_text(encoding="utf-8").strip()
    ruby_major_minor = ".".join(ruby_ver.split(".")[:2])
    py_match = re.search(
        r'python_version\s*=\s*"([^"]+)"', pyproject_path.read_text(encoding="utf-8")
    )
    py_ver = py_match.group(1) if py_match else "3.12"

    dev_text = dev_path.read_text(encoding="utf-8")
    ci_text = ci_path.read_text(encoding="utf-8")
    if ruby_major_minor not in dev_text or f"'{ruby_major_minor}'" not in ci_text:
        errors.append(
            f"Ruby version drift detected: .ruby-version is '{ruby_ver}' ({ruby_major_minor}) but devcontainer or CI differs"
        )
    if py_ver not in dev_text or f"'{py_ver}'" not in ci_text:
        errors.append(
            f"Python version drift detected: pyproject.toml is '{py_ver}' but devcontainer or CI differs"
        )
    return errors


def check_governance_configs(repo_root: Path) -> list[str]:
    """Validate JSON governance, devcontainer, and health schema files."""
    errors: list[str] = []
    required_json = (
        ".devcontainer/devcontainer.json",
        ".github/labels.json",
        ".github/branch-protection.json",
        "docs/health.schema.json",
        "renovate.json",
    )
    for rel_path in required_json:
        full_path = repo_root / rel_path
        if not full_path.is_file():
            errors.append(f"Missing required configuration file '{rel_path}'")
            continue
        try:
            json.loads(full_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel_path}: invalid JSON ({exc})")
    return errors
