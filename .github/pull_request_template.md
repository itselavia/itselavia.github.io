## Summary

<!-- Briefly describe the changes in this pull request (e.g., new blog post, layout adjustment, tooling update). -->

## Related Context / Issue

<!-- Link any related issue or discussion if applicable. -->

## Validation & Testing Done

- [ ] `python3 scripts/validate_site.py --check-format --check-docs` passed
- [ ] `python3 -m unittest discover -s tests -p "test_*.py" -v` passed
- [ ] Verified changes with `bundle exec jekyll build` / `bundle exec jekyll serve --watch` (if modifying templates, CSS, or posts)
- [ ] Updated `docs/post-catalog.md` via `python3 scripts/validate_site.py --generate-docs` (if adding or editing a blog post)
