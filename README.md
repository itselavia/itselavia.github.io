# Agentic (`itselavia.github.io`)

Personal engineering blog by Akshay Elavia focused on AI, agentic architectures, cloud infrastructure, and software engineering. Built with Jekyll 4 and lean custom CSS (zero JavaScript), deployed to [https://itselavia.github.io](https://itselavia.github.io).

## Quick Start

```bash
# Install Ruby gems (Ruby 3.2 specified in .ruby-version)
bundle install

# Start local preview server with live reload at http://127.0.0.1:4000
bundle exec jekyll serve --watch

# Build production static site into _site/
JEKYLL_ENV=production bundle exec jekyll build --baseurl ""
```

## Validation & Tests

```bash
# Validate frontmatter, assets, CSS tokens, unused deps, formatting, and docs
python3 scripts/validate_site.py --check-format --check-docs

# Run unit and integration test suites
python3 -m unittest discover -s tests -p "test_*.py" -v

# Enable pre-commit hook locally
git config core.hooksPath .githooks
```

## Adding a Blog Post

1. Create `_posts/YYYY-MM-DD-your-slug.markdown` with YAML frontmatter (`layout: post`, `title`, `subtitle`, `date`, `author`, `header-img`).
2. Place any post images in `img/` and reference them with `{{ site.baseurl }}/img/<filename>`.
3. Refresh the post catalog and validate:
   ```bash
   python3 scripts/validate_site.py --generate-docs
   python3 scripts/validate_site.py --check-format --check-docs
   ```
4. Preview with `bundle exec jekyll serve --watch` and open a pull request to `master`.

## Environment Variables

Copy `.env.example` if overriding defaults locally:

- `JEKYLL_ENV` (`development` or `production`)
- `JEKYLL_HOST` (`127.0.0.1`)
- `JEKYLL_PORT` (`4000`)
- `LOG_LEVEL` (`INFO`)

## Documentation

- [`AGENTS.md`](AGENTS.md) — Agent workflow, conventions, and verification commands
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Contribution, naming, and dependency release-age guidelines
- [`docs/architecture.md`](docs/architecture.md) — Site architecture and build/deploy pipeline diagram
- [`docs/runbook.md`](docs/runbook.md) — Deployment observability, health check (`/health.json`), and incident runbook
- [`docs/post-catalog.md`](docs/post-catalog.md) — Automatically generated catalog of published posts
