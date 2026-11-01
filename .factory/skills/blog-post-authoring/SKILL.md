---
name: blog-post-authoring
description: Create, update, and validate blog posts and static assets in the Agentic Jekyll site. Use when adding or editing posts in _posts/, updating layouts or CSS, or running site quality checks.
---

# Blog Post Authoring & Validation Skill

Follow these steps when creating or modifying content in `itselavia.github.io`:

## 1. Post File & Frontmatter Contract

Create new posts in `_posts/YYYY-MM-DD-slug.markdown` with complete YAML frontmatter:

```yaml
---
layout:     post
title:      "Clear Technical Title"
subtitle:   "One-sentence summary shown on homepage cards and post header"
date:       YYYY-MM-DD 12:00:00
author:     "Akshay Elavia"
header-img: "img/post-bg-14.jpg"
---
```

- `header-img` must point to an existing file in `img/`.
- Reference inline images as `{{ site.baseurl }}/img/<file>` and always include a descriptive `alt` attribute.

## 2. Regenerate Documentation & Validate

After editing posts, templates, or CSS:

```bash
# Update docs/post-catalog.md
python3 scripts/validate_site.py --generate-docs

# Normalize trailing whitespace and newlines if needed
python3 scripts/validate_site.py --format

# Run full validation and unit/integration tests
python3 scripts/validate_site.py --check-format --check-docs
python3 -m unittest discover -s tests -p "test_*.py" -v
```

## 3. Local Preview (when Ruby 3.2 is installed)

```bash
bundle exec jekyll serve --watch
```

Verify the post renders on the homepage card grid (`/`) and at its pretty permalink (`/YYYY/MM/DD/slug/`).
