# Contributing to Agentic (`itselavia.github.io`)

## Development Setup

1. Clone the repository and configure Git hooks:
   ```bash
   git config core.hooksPath .githooks
   ```
2. Install Ruby 3.2 (`.ruby-version`) and Bundler dependencies:
   ```bash
   bundle install
   ```
3. Run the local preview server:
   ```bash
   bundle exec jekyll serve --watch
   ```

## Validation & Testing

Before opening a pull request, run the site validator and test suite:

```bash
python3 scripts/validate_site.py --check-format --check-docs
python3 -m unittest discover -s tests -p "test_*.py" -v
```

If you added or modified a blog post in `_posts/`, update the generated post catalog:

```bash
python3 scripts/validate_site.py --generate-docs
```

## Conventions

- **Post Naming:** `_posts/YYYY-MM-DD-kebab-case-slug.markdown` with required frontmatter (`layout`, `title`, `subtitle`, `date`, `author`, `header-img`).
- **Test Naming:** Unit tests live in `tests/test_*.py` and integration tests live in `tests/integration/test_*.py`. All tests must be isolated and deterministic.
- **Formatting:** UTF-8 encoding, LF line endings, no trailing whitespace, and a single trailing newline in all source files (`python3 scripts/validate_site.py --format`).
- **Dependency Updates:** New dependency releases must meet a minimum release age of 7 days (`renovate.json` `minimumReleaseAge: "7 days"`) before merging non-emergency updates.
