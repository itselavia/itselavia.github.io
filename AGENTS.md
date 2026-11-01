# AGENTS.md

Instructions for autonomous coding agents working in `itselavia.github.io` (**Agentic** personal engineering blog).

## Project Overview

- **Stack:** Jekyll 4.3+ (`Gemfile`), Ruby 3.2 (`.ruby-version`), Kramdown + Rouge syntax highlighting, vanilla CSS (`css/style.css`, `css/syntax.css`), zero client-side JavaScript.
- **Deployment:** Automatically built and deployed to GitHub Pages via `.github/workflows/deploy.yml` on pushes to `master`.
- **Verification Tooling:** Zero-dependency Python 3.12 validation and test suite (`scripts/validate_site.py`, `tests/`) that checks frontmatter, templates, CSS custom properties, asset links, unused gems, formatting, and documentation freshness.

## Quick Commands

```bash
# Install Ruby dependencies (requires Ruby 3.2 + Bundler)
bundle install

# Run local development server with live reload on http://127.0.0.1:4000
bundle exec jekyll serve --watch

# Build static site into _site/
JEKYLL_ENV=production bundle exec jekyll build --baseurl ""

# Run static site validator, formatter check, and documentation sync check
python3 scripts/validate_site.py --check-format --check-docs

# Regenerate post catalog documentation after adding or editing a post
python3 scripts/validate_site.py --generate-docs

# Run unit and integration test suites
python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Environment Variables

See `.env.example` for all supported variables:

- `JEKYLL_ENV`: `development` (default locally) or `production` (used in CI builds).
- `JEKYLL_HOST`: Bind address for local server (default `127.0.0.1`).
- `JEKYLL_PORT`: Port for local server (default `4000`).
- `LOG_LEVEL`: Log verbosity for `scripts/validate_site.py` (`INFO` by default).

Never commit `.env` files, API tokens, or credentials. All logs emitted by `scripts/logger.py` automatically scrub sensitive keys, tokens, and email addresses.

## Repository Layout

- `_config.yml` — Jekyll site configuration, pagination, plugins, and build `exclude` list.
- `_layouts/` — Page templates (`default.html`, `page.html`, `post.html`).
- `_includes/` — Shared HTML partials (`head.html`, `nav.html`, `footer.html`, `ga.html`, `youtube.html`).
- `_posts/` — Published blog posts named `YYYY-MM-DD-slug.markdown`.
- `css/` — `style.css` (design tokens and layout) and `syntax.css` (Rouge code highlighting).
- `img/` — Post header backgrounds and technical diagrams.
- `health.json` — Liquid template producing the `/health.json` deployment health check endpoint.
- `scripts/` — `validate_site.py` (site & doc validator) and `logger.py` (structured JSON logger with secret scrubbing).
- `tests/` — Unit (`tests/test_site.py`) and integration (`tests/integration/test_build_contract.py`) test suites.
- `docs/` — Architecture diagrams (`docs/architecture.md`), operational runbook (`docs/runbook.md`), and generated post catalog (`docs/post-catalog.md`).

## Naming & Code Conventions

1. **Blog Posts:**
   - File path must match `_posts/YYYY-MM-DD-short-kebab-slug.markdown`.
   - Required YAML frontmatter keys: `layout: post`, `title`, `subtitle`, `date` (`YYYY-MM-DD HH:MM:SS`), `author`, and `header-img` (relative path under `img/`).
2. **CSS:**
   - Define all color and typography tokens in `:root` inside `css/style.css` using `--kebab-case` custom properties.
   - Do not introduce external CSS frameworks or client-side JavaScript libraries.
3. **Python Scripts & Tests:**
   - Use `snake_case` for functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
   - All functions in `scripts/` must include strict Python type annotations.
   - Test files must be named `tests/test_*.py` or `tests/integration/test_*.py` and be isolated/stateless.
4. **Site Exclusions:**
   - Any repository-only file or directory added at root (docs, scripts, tests, config files) must be listed in `exclude:` inside `_config.yml` so it is not copied into `_site/`.
5. **Dependency Policy:**
   - Wait at least **7 days** (`minimumReleaseAge: "7 days"` in `renovate.json`) after a gem or GitHub Action release before adopting version bumps unless patching an active CVE.
   - Every gem in `Gemfile` `group :jekyll_plugins` must be listed in `plugins:` in `_config.yml`.

## Pre-Commit & CI Workflow

Enable the repository Git hooks locally after cloning:

```bash
git config core.hooksPath .githooks
```

The pre-commit hook (`.githooks/pre-commit`) and CI workflow (`.github/workflows/deploy.yml`) run `python3 scripts/validate_site.py --check-format --check-docs` and the `unittest` suite on every commit and pull request.
