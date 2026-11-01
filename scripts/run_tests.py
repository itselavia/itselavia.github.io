#!/usr/bin/env python3
"""Test runner with per-test performance budgets, flaky-test repetition, and stdlib line coverage."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterator
from pathlib import Path
import sys
import time
import trace
import unittest

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.logger import get_logger

MAX_TEST_DURATION_MS: float = 500.0
MIN_COVERAGE_PERCENT: float = 80.0
COVERED_MODULES: tuple[str, ...] = (
    "scripts/logger.py",
    "scripts/code_quality.py",
    "scripts/validate_site.py",
)


def _iter_test_cases(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    """Yield individual TestCase instances from a nested TestSuite."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_test_cases(item)
        elif isinstance(item, unittest.TestCase):
            yield item


def _executable_lines(py_path: Path) -> set[int]:
    """Identify executable statement line numbers in a Python source file."""
    source = py_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_path))
    stmt_lines: set[int] = set()
    ignored_types = (ast.Import, ast.ImportFrom, ast.Pass)
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.stmt) and not isinstance(node, ignored_types):
            stmt_lines.add(node.lineno)
    lines = source.splitlines()
    return {
        ln
        for ln in stmt_lines
        if not lines[ln - 1].strip().startswith(('if __name__ == "__main__":', "raise SystemExit"))
    }


def compute_module_coverage(
    repo_root: Path, counts: dict[tuple[str, int], int]
) -> tuple[float, dict[str, float]]:
    """Compute overall and per-module line coverage percentages from trace counts."""
    total_exec = 0
    total_hit = 0
    per_module: dict[str, float] = {}

    for rel_mod in COVERED_MODULES:
        mod_path = (repo_root / rel_mod).resolve()
        exec_lines = _executable_lines(mod_path)
        hit_lines = {
            ln for ln in exec_lines if counts.get((str(mod_path), ln), 0) > 0
        }
        total_exec += len(exec_lines)
        total_hit += len(hit_lines)
        pct = (len(hit_lines) / len(exec_lines) * 100.0) if exec_lines else 100.0
        per_module[rel_mod] = round(pct, 1)

    overall = (total_hit / total_exec * 100.0) if total_exec else 100.0
    return round(overall, 1), per_module


def _run_single_pass(repo_root: Path) -> tuple[bool, dict[str, float]]:
    """Discover and execute all tests once, returning success flag and per-test durations."""
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(repo_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )
    result = unittest.TestResult()
    durations: dict[str, float] = {}
    for case in _iter_test_cases(suite):
        started = time.perf_counter()
        case.run(result)
        durations[case.id()] = (time.perf_counter() - started) * 1000.0
    return result.wasSuccessful(), durations


def _record_durations(
    durations: dict[str, float],
    max_durations: dict[str, float],
    slow_tests: list[str],
) -> None:
    """Update peak test durations and record any tests exceeding MAX_TEST_DURATION_MS."""
    for test_id, ms in durations.items():
        max_durations[test_id] = max(max_durations.get(test_id, 0.0), round(ms, 2))
        if ms > MAX_TEST_DURATION_MS:
            slow_tests.append(f"{test_id} ({ms:.1f}ms > {MAX_TEST_DURATION_MS}ms)")


def execute_test_suite(
    repo_root: Path, repeat: int = 1, check_coverage: bool = False
) -> tuple[int, dict[str, object]]:
    """Run test passes with optional coverage and flaky-test detection."""
    tracer = (
        trace.Trace(
            count=True,
            trace=False,
            ignoredirs=[sys.prefix, sys.exec_prefix],
        )
        if check_coverage
        else None
    )
    pass_outcomes: list[bool] = []
    slow_tests: list[str] = []
    max_durations: dict[str, float] = {}

    for pass_idx in range(max(1, repeat)):
        ok, durations = (
            tracer.runfunc(_run_single_pass, repo_root)
            if (tracer is not None and pass_idx == 0)
            else _run_single_pass(repo_root)
        )
        pass_outcomes.append(ok)
        _record_durations(durations, max_durations, slow_tests)

    flaky = len(set(pass_outcomes)) > 1
    all_passed = all(pass_outcomes) and not flaky and not slow_tests
    summary: dict[str, object] = {
        "passes_run": len(pass_outcomes),
        "flaky_detected": flaky,
        "slow_tests": slow_tests,
        "test_count": len(max_durations),
    }

    if tracer is not None:
        overall_cov, module_cov = compute_module_coverage(
            repo_root, tracer.results().counts
        )
        summary["coverage_percent"] = overall_cov
        summary["module_coverage"] = module_cov
        all_passed = all_passed and (overall_cov >= MIN_COVERAGE_PERCENT)

    return (0 if all_passed else 1), summary


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for test execution, flaky detection, and coverage enforcement."""
    parser = argparse.ArgumentParser(
        description="Run unit and integration tests with timing, flaky check, and coverage."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root path",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of test passes to run for flaky test detection",
    )
    parser.add_argument(
        "--check-coverage",
        action="store_true",
        help=f"Enforce >= {MIN_COVERAGE_PERCENT}% line coverage on scripts/",
    )
    args = parser.parse_args(argv)
    logger = get_logger()
    exit_code, summary = execute_test_suite(
        repo_root=args.root.resolve(),
        repeat=args.repeat,
        check_coverage=args.check_coverage,
    )
    if exit_code == 0:
        logger.info("Test suite succeeded", extra={"context": summary})
    else:
        logger.error("Test suite failed thresholds", extra={"context": summary})
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
