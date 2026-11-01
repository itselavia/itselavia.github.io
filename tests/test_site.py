"""Unit tests for site validation, CSS token checks, unused dependency detection, and log scrubbing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import tempfile
import unittest

from scripts.code_quality import check_or_format_files, check_python_code_quality
from scripts.logger import JsonScrubbingFormatter, scrub_mapping, scrub_sensitive_text
from scripts.validate_site import (
    check_config_and_gems,
    check_css,
    check_templates_and_pages,
    collect_and_validate_posts,
    parse_frontmatter,
    parse_simple_yaml_lists,
)


class TestFrontmatterAndConfigParsers(unittest.TestCase):
    """Unit tests for YAML frontmatter and _config.yml parsing."""

    def test_parse_frontmatter_extracts_metadata_and_body(self) -> None:
        raw = (
            "---\n"
            "layout: post\n"
            'title: "Test Post"\n'
            "date: 2026-03-01 12:00:00\n"
            "---\n"
            "<p>Body content here.</p>\n"
        )
        metadata, body = parse_frontmatter(raw)
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata["layout"], "post")
        self.assertEqual(metadata["title"], "Test Post")
        self.assertEqual(metadata["date"], "2026-03-01 12:00:00")
        self.assertEqual(body.strip(), "<p>Body content here.</p>")

    def test_parse_frontmatter_returns_none_when_missing_delimiters(self) -> None:
        metadata, body = parse_frontmatter("<h1>No frontmatter</h1>")
        self.assertIsNone(metadata)
        self.assertEqual(body, "<h1>No frontmatter</h1>")

    def test_parse_simple_yaml_lists_handles_inline_and_block_lists(self) -> None:
        yaml_text = (
            "title: Agentic\n"
            "plugins: [jekyll-paginate, jekyll-feed]\n"
            "exclude:\n"
            '  - "README.md"\n'
            '  - "tests"\n'
        )
        scalars, lists = parse_simple_yaml_lists(yaml_text)
        self.assertEqual(scalars["title"], "Agentic")
        self.assertEqual(lists["plugins"], ["jekyll-paginate", "jekyll-feed"])
        self.assertEqual(lists["exclude"], ["README.md", "tests"])


class TestAdversarialValidators(unittest.TestCase):
    """Adversarial unit tests verifying validator catches broken posts, CSS, and unused gems."""

    def test_check_css_detects_undefined_custom_property_and_unbalanced_braces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            css_dir = root / "css"
            css_dir.mkdir()
            (css_dir / "style.css").write_text(
                ":root { --accent: #b45309; }\n"
                "a { color: var(--accent); background: var(--undefined-token); }\n",
                encoding="utf-8",
            )
            (css_dir / "syntax.css").write_text(".highlight { color: #fff;\n", encoding="utf-8")

            errors = check_css(root)
            self.assertTrue(
                any("--undefined-token" in err for err in errors),
                f"Expected undefined CSS token error, got: {errors}",
            )
            self.assertTrue(
                any("unbalanced curly braces" in err for err in errors),
                f"Expected unbalanced braces error, got: {errors}",
            )

    def test_check_config_and_gems_detects_unused_gem_and_missing_excludes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_config.yml").write_text(
                "title: Test\n"
                "url: https://example.com\n"
                "markdown: kramdown\n"
                "highlighter: rouge\n"
                "permalink: pretty\n"
                "paginate: 3\n"
                "exclude: [README.md]\n"
                "plugins: [jekyll-feed]\n",
                encoding="utf-8",
            )
            (root / "Gemfile").write_text(
                'source "https://rubygems.org"\n'
                'gem "jekyll", "~> 4.3"\n'
                "group :jekyll_plugins do\n"
                '  gem "jekyll-feed"\n'
                '  gem "jekyll-UnusedPlugin"\n'
                "end\n",
                encoding="utf-8",
            )

            errors = check_config_and_gems(root)
            self.assertTrue(
                any("jekyll-UnusedPlugin" in err for err in errors),
                f"Expected unused plugin gem error, got: {errors}",
            )
            self.assertTrue(
                any("AGENTS.md" in err for err in errors),
                f"Expected missing exclude error, got: {errors}",
            )

    def test_collect_and_validate_posts_detects_missing_image_and_bad_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts_dir = root / "_posts"
            posts_dir.mkdir()
            (posts_dir / "2026-03-01-broken-post.markdown").write_text(
                "---\n"
                "layout: post\n"
                'title: "Broken Post"\n'
                'subtitle: "Subtitle"\n'
                "date: 2025-01-01 12:00:00\n"
                'author: "Author"\n'
                'header-img: "img/missing.jpg"\n'
                "---\n"
                + ("<p>Valid length body content for testing.</p>\n" * 4),
                encoding="utf-8",
            )

            _, errors = collect_and_validate_posts(root)
            self.assertTrue(
                any("does not match filename prefix" in err for err in errors),
                f"Expected date mismatch error, got: {errors}",
            )
            self.assertTrue(
                any("img/missing.jpg" in err for err in errors),
                f"Expected missing header-img error, got: {errors}",
            )

    def test_formatter_detects_and_fixes_trailing_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.md"
            sample.write_text("# Heading with trailing spaces   \nLine two\n", encoding="utf-8")

            check_errors = check_or_format_files(root, fix=False)
            self.assertEqual(len(check_errors), 1)

            fix_errors = check_or_format_files(root, fix=True)
            self.assertEqual(fix_errors, [])
            self.assertEqual(
                sample.read_text(encoding="utf-8"),
                "# Heading with trailing spaces\nLine two\n",
            )

    def test_check_python_code_quality_detects_untyped_and_badly_named_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_py = root / "bad_module.py"
            bad_py.write_text(
                "class bad_class_name:\n"
                "    pass\n\n"
                "def BadFunc(x):\n"
                "    return x\n",
                encoding="utf-8",
            )
            errors = check_python_code_quality(root)
            self.assertTrue(any("PascalCase" in e for e in errors))
            self.assertTrue(any("snake_case" in e for e in errors))
            self.assertTrue(any("missing return type annotation" in e for e in errors))
            self.assertTrue(any("missing type annotation" in e for e in errors))

    def test_check_templates_detects_unused_include_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layouts = root / "_layouts"
            includes = root / "_includes"
            layouts.mkdir()
            includes.mkdir()
            (layouts / "default.html").write_text(
                "{% include head.html %}{{ content }}", encoding="utf-8"
            )
            (includes / "head.html").write_text("<head></head>", encoding="utf-8")
            (includes / "orphan.html").write_text("<div>unused</div>", encoding="utf-8")
            (root / "index.html").write_text("---\nlayout: default\n---\n", encoding="utf-8")
            (root / "about.html").write_text("---\nlayout: default\n---\n", encoding="utf-8")
            (root / "health.json").write_text("---\nlayout: null\n---\n{}", encoding="utf-8")

            errors = check_templates_and_pages(root)
            self.assertTrue(
                any("Unused partial '_includes/orphan.html'" in e for e in errors),
                f"Expected unused partial error, got: {errors}",
            )


class TestLogScrubbing(unittest.TestCase):
    """Unit tests verifying sensitive tokens, keys, and emails are scrubbed from logs."""

    def test_scrub_sensitive_text_redacts_tokens_keys_and_emails(self) -> None:
        raw = (
            "header=ghu_1234567890abcdef AWS=AKIAIOSFODNN7EXAMPLE "
            "password: superSecretValue user=akshay.elavia@gmail.com"
        )
        scrubbed = scrub_sensitive_text(raw)
        self.assertNotIn("ghu_1234567890abcdef", scrubbed)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", scrubbed)
        self.assertNotIn("superSecretValue", scrubbed)
        self.assertNotIn("akshay.elavia@", scrubbed)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", scrubbed)
        self.assertIn("[REDACTED_AWS_KEY]", scrubbed)
        self.assertIn("[REDACTED_EMAIL]@gmail.com", scrubbed)

    def test_json_formatter_scrubs_context_dictionary(self) -> None:
        formatter = JsonScrubbingFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Checking api_key=my_secret_123",
            args=(),
            exc_info=None,
        )
        record.context = scrub_mapping(
            {"api_key": "raw_secret", "note": "contact test@example.com"}
        )
        formatted = json.loads(formatter.format(record))
        self.assertEqual(formatted["context"]["api_key"], "[REDACTED]")
        self.assertIn("[REDACTED_EMAIL]@example.com", formatted["context"]["note"])
        self.assertIn("[REDACTED]", formatted["message"])


if __name__ == "__main__":
    unittest.main()
