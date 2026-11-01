"""Integration tests verifying the live repository structure, templates, and docs."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.validate_site import (
    collect_and_validate_posts,
    parse_frontmatter,
    validate_repository,
)

REPO_ROOT: Path = Path(__file__).resolve().parents[2]


class TestRepositoryBuildContract(unittest.TestCase):
    """End-to-end validation of the Jekyll repository, templates, and documentation."""

    def test_full_repository_passes_validation_and_doc_sync(self) -> None:
        errors = validate_repository(
            repo_root=REPO_ROOT,
            check_format=True,
            fix_format=False,
            check_docs=True,
            generate_docs=False,
        )
        self.assertEqual(errors, [], f"Repository validation failed: {errors}")

    def test_all_published_posts_have_valid_metadata_and_permalinks(self) -> None:
        posts, errors = collect_and_validate_posts(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(posts), 3)
        permalinks = [post.permalink for post in posts]
        self.assertIn("/2021/02/09/dynamic-update-env-vars/", permalinks)
        self.assertIn("/2021/01/02/deploy-kubeedge-gcp/", permalinks)
        self.assertIn("/2019/12/01/automated-mongodb-deployment/", permalinks)

    def test_health_endpoint_template_is_valid(self) -> None:
        health_path = REPO_ROOT / "health.json"
        self.assertTrue(health_path.is_file())
        frontmatter, body = parse_frontmatter(health_path.read_text(encoding="utf-8"))
        self.assertIsNotNone(frontmatter)
        assert frontmatter is not None
        self.assertEqual(frontmatter.get("layout"), "null")
        self.assertEqual(frontmatter.get("permalink"), "/health.json")
        rendered_sample = (
            body.replace("{{ site.title | jsonify }}", '"Agentic"')
            .replace("{{ site.url | jsonify }}", '"https://itselavia.github.io"')
            .replace("{{ jekyll.environment | jsonify }}", '"production"')
            .replace("{{ site.posts | size }}", "3")
        )
        parsed = json.loads(rendered_sample)
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual(parsed["site"], "Agentic")
        self.assertEqual(parsed["posts_count"], 3)

    def test_renovate_enforces_minimum_release_age(self) -> None:
        renovate_path = REPO_ROOT / "renovate.json"
        self.assertTrue(renovate_path.is_file())
        config = json.loads(renovate_path.read_text(encoding="utf-8"))
        self.assertEqual(config.get("minimumReleaseAge"), "7 days")


if __name__ == "__main__":
    unittest.main()
