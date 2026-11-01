#!/usr/bin/env python3
"""Static validator, dependency checker, and doc generator for itselavia.github.io."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.code_quality import check_or_format_files, check_python_code_quality
from scripts.logger import get_logger

POST_FILENAME_RE: re.Pattern[str] = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>[a-z0-9-]+)\.(?:markdown|md)$"
)
INCLUDE_TAG_RE: re.Pattern[str] = re.compile(r"\{%\s*include\s+([a-zA-Z0-9_.-]+)")
SITE_IMG_RE: re.Pattern[str] = re.compile(
    r"\{\{\s*site\.baseurl\s*\}\}/(img/[A-Za-z0-9_./-]+)"
)
CSS_VAR_DEF_RE: re.Pattern[str] = re.compile(r"(--[a-z0-9-]+)\s*:")
CSS_VAR_USE_RE: re.Pattern[str] = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")
GEM_DECL_RE: re.Pattern[str] = re.compile(r'^\s*gem\s+["\']([a-zA-Z0-9_-]+)["\']')
DOC_PATH_RE: re.Pattern[str] = re.compile(
    r"`((?:\.[a-zA-Z0-9_.-]+|[a-zA-Z0-9_-]+)(?:/[a-zA-Z0-9_.*-]*)+"
    r"|\.[a-zA-Z0-9_.-]+"
    r"|(?:_config\.yml|Gemfile(?:\.lock)?|README\.md|AGENTS\.md|CONTRIBUTING\.md"
    r"|pyproject\.toml|renovate\.json|health\.json|index\.html|about\.html|contact\.html|feed\.xml))`"
)

REQUIRED_POST_FRONTMATTER: tuple[str, ...] = (
    "layout",
    "title",
    "subtitle",
    "date",
    "author",
    "header-img",
)
REQUIRED_CONFIG_EXCLUDES: tuple[str, ...] = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "Gemfile",
    "Gemfile.lock",
    "pyproject.toml",
    "renovate.json",
    "docs",
    "scripts",
    "tests",
    "vendor",
)


@dataclass(frozen=True)
class PostMetadata:
    """Parsed metadata for a Jekyll blog post."""

    filename: str
    date_prefix: str
    slug: str
    title: str
    subtitle: str
    author: str
    header_img: str

    @property
    def permalink(self) -> str:
        year, month, day = self.date_prefix.split("-")
        return f"/{year}/{month}/{day}/{self.slug}/"


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    """Extract simple YAML frontmatter key-value pairs and body content."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end_idx = next(
        (idx for idx in range(1, len(lines)) if lines[idx].strip() == "---"), None
    )
    if end_idx is None:
        return None, text

    data: dict[str, str] = {}
    for raw_line in lines[1:end_idx]:
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and ":" in stripped:
            key, raw_val = stripped.split(":", 1)
            data[key.strip()] = raw_val.strip().strip('"').strip("'")
    return data, "\n".join(lines[end_idx + 1 :])


def _strip_yaml_comment(raw_line: str) -> str:
    """Remove inline YAML comments outside of quotes."""
    if "#" not in raw_line:
        return raw_line.rstrip()
    in_quote = False
    for idx, ch in enumerate(raw_line):
        if ch in ('"', "'"):
            in_quote = not in_quote
        elif ch == "#" and not in_quote:
            return raw_line[:idx].rstrip()
    return raw_line.rstrip()


def _parse_inline_yaml_list(val: str) -> list[str]:
    """Parse an inline YAML list like [a, b, c]."""
    inner = val[1:-1].strip()
    return [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]


def _parse_yaml_key_value(
    key: str, val: str, scalars: dict[str, str], lists: dict[str, list[str]]
) -> str | None:
    """Process a key: value YAML line and return active list key if starting a block list."""
    if not val:
        lists.setdefault(key, [])
        return key
    if val.startswith("[") and val.endswith("]"):
        lists[key] = _parse_inline_yaml_list(val)
    else:
        scalars[key] = val.strip('"').strip("'")
    return None


def parse_simple_yaml_lists(text: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Parse scalar keys and list keys from _config.yml without external dependencies."""
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}
    current_list_key: str | None = None

    for raw_line in text.splitlines():
        cleaned = _strip_yaml_comment(raw_line).strip()
        if cleaned.startswith("- ") and current_list_key is not None:
            lists[current_list_key].append(cleaned[2:].strip().strip('"').strip("'"))
        elif ":" in cleaned:
            key, val = [part.strip() for part in cleaned.split(":", 1)]
            current_list_key = _parse_yaml_key_value(key, val, scalars, lists)
    return scalars, lists


def _extract_gemfile_plugins(gemfile_text: str) -> list[str]:
    """Extract Jekyll plugin gems declared in Gemfile."""
    gemfile_plugins: list[str] = []
    in_plugin_group = False
    for line in gemfile_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("group :jekyll_plugins"):
            in_plugin_group = True
        elif in_plugin_group and stripped == "end":
            in_plugin_group = False
        else:
            match = GEM_DECL_RE.match(line)
            if match and (in_plugin_group or match.group(1).startswith("jekyll-")):
                gemfile_plugins.append(match.group(1))
    return gemfile_plugins


def check_config_and_gems(repo_root: Path) -> list[str]:
    """Validate _config.yml settings, required exclusions, and unused Gemfile plugins."""
    config_path = repo_root / "_config.yml"
    gemfile_path = repo_root / "Gemfile"
    if not config_path.is_file():
        return ["Missing _config.yml at repository root"]
    if not gemfile_path.is_file():
        return ["Missing Gemfile at repository root"]

    errors: list[str] = []
    scalars, lists = parse_simple_yaml_lists(config_path.read_text(encoding="utf-8"))
    for req_key in ("title", "url", "markdown", "highlighter", "permalink", "paginate"):
        if not scalars.get(req_key):
            errors.append(f"_config.yml is missing required scalar setting '{req_key}'")

    configured_excludes = set(lists.get("exclude", []))
    for req_exclude in REQUIRED_CONFIG_EXCLUDES:
        if req_exclude not in configured_excludes:
            errors.append(
                f"_config.yml 'exclude' must include '{req_exclude}' to prevent publishing repo tooling"
            )

    configured_plugins = set(lists.get("plugins", []))
    for plugin_gem in _extract_gemfile_plugins(gemfile_path.read_text(encoding="utf-8")):
        if plugin_gem not in configured_plugins:
            errors.append(
                f"Unused plugin gem '{plugin_gem}' in Gemfile is not enabled in _config.yml plugins"
            )
    return errors


def _check_post_assets_and_dates(
    repo_root: Path, rel: Path, date_prefix: str, frontmatter: dict[str, str], body: str
) -> list[str]:
    """Check frontmatter layout, date prefix match, image assets, and body length."""
    errors: list[str] = []
    if frontmatter.get("layout") != "post":
        errors.append(f"{rel}: expected layout 'post', got '{frontmatter.get('layout')}'")
    fm_date = frontmatter.get("date", "")
    if fm_date and not fm_date.startswith(date_prefix):
        errors.append(
            f"{rel}: frontmatter date '{fm_date}' does not match filename prefix '{date_prefix}'"
        )
    header_img = frontmatter.get("header-img", "")
    if header_img and not (repo_root / header_img).is_file():
        errors.append(f"{rel}: header-img '{header_img}' does not exist")
    for img_rel in SITE_IMG_RE.findall(body):
        if not (repo_root / img_rel).is_file():
            errors.append(f"{rel}: referenced image '{img_rel}' does not exist")
    if len(body.strip()) < 100:
        errors.append(f"{rel}: post body is unexpectedly short (<100 chars)")
    return errors


def _validate_single_post(
    repo_root: Path, post_file: Path
) -> tuple[PostMetadata | None, list[str]]:
    """Validate a single post file and return its metadata and any errors."""
    name_match = POST_FILENAME_RE.match(post_file.name)
    if not name_match:
        return None, [f"Post filename '{post_file.name}' must match YYYY-MM-DD-slug.markdown"]

    frontmatter, body = parse_frontmatter(post_file.read_text(encoding="utf-8"))
    rel = post_file.relative_to(repo_root)
    if frontmatter is None:
        return None, [f"{rel}: missing YAML frontmatter"]

    missing_keys = [k for k in REQUIRED_POST_FRONTMATTER if not frontmatter.get(k)]
    errors = [f"{rel}: missing frontmatter key '{k}'" for k in missing_keys]
    date_prefix = name_match.group("date")
    errors.extend(
        _check_post_assets_and_dates(repo_root, rel, date_prefix, frontmatter, body)
    )
    if missing_keys:
        return None, errors

    return (
        PostMetadata(
            filename=post_file.name,
            date_prefix=date_prefix,
            slug=name_match.group("slug"),
            title=frontmatter["title"],
            subtitle=frontmatter["subtitle"],
            author=frontmatter["author"],
            header_img=frontmatter["header-img"],
        ),
        errors,
    )


def collect_and_validate_posts(repo_root: Path) -> tuple[list[PostMetadata], list[str]]:
    """Validate all posts in _posts/, including duplicate title/permalink detection."""
    posts_dir = repo_root / "_posts"
    if not posts_dir.is_dir():
        return [], ["Missing _posts/ directory"]

    post_files = sorted(
        p for p in posts_dir.iterdir() if p.is_file() and not p.name.startswith(".")
    )
    errors: list[str] = [] if post_files else ["No blog posts found in _posts/"]
    posts: list[PostMetadata] = []
    seen_titles: set[str] = set()
    seen_permalinks: set[str] = set()

    for post_file in post_files:
        meta, post_errors = _validate_single_post(repo_root, post_file)
        errors.extend(post_errors)
        if meta is not None:
            if meta.title in seen_titles:
                errors.append(f"Duplicate post title '{meta.title}' in {meta.filename}")
            if meta.permalink in seen_permalinks:
                errors.append(f"Duplicate post permalink '{meta.permalink}' in {meta.filename}")
            seen_titles.add(meta.title)
            seen_permalinks.add(meta.permalink)
            posts.append(meta)

    posts.sort(key=lambda p: (p.date_prefix, p.filename), reverse=True)
    return posts, errors


def _validate_template_file(
    repo_root: Path, layouts_dir: Path, includes_dir: Path, tpl_path: Path
) -> tuple[set[str], list[str]]:
    """Validate a single template/page file and return referenced includes and errors."""
    if not tpl_path.is_file():
        return set(), [f"Missing required template or page '{tpl_path.name}'"]

    errors: list[str] = []
    content = tpl_path.read_text(encoding="utf-8")
    frontmatter, _ = parse_frontmatter(content)
    rel = tpl_path.relative_to(repo_root)
    if frontmatter is not None:
        layout_name = frontmatter.get("layout")
        if layout_name and layout_name != "null" and not (layouts_dir / f"{layout_name}.html").is_file():
            errors.append(f"{rel}: layout '{layout_name}' not found in _layouts/")
        header_img = frontmatter.get("header-img")
        if header_img and not (repo_root / header_img).is_file():
            errors.append(f"{rel}: header-img '{header_img}' does not exist")

    referenced_includes = set(INCLUDE_TAG_RE.findall(content))
    for inc_name in sorted(referenced_includes):
        if not (includes_dir / inc_name).is_file():
            errors.append(f"{rel}: included file '_includes/{inc_name}' does not exist")
    return referenced_includes, errors


def check_templates_and_pages(repo_root: Path) -> list[str]:
    """Validate layouts, includes, top-level pages, and dead/unused _includes partials."""
    layouts_dir = repo_root / "_layouts"
    includes_dir = repo_root / "_includes"
    if not layouts_dir.is_dir() or not includes_dir.is_dir():
        return ["Missing _layouts/ or _includes/ directory"]

    errors: list[str] = []
    used_includes: set[str] = set()
    template_files = list(layouts_dir.glob("*.html")) + [
        repo_root / "index.html",
        repo_root / "about.html",
        repo_root / "health.json",
    ]
    for tpl_path in template_files:
        refs, tpl_errors = _validate_template_file(
            repo_root, layouts_dir, includes_dir, tpl_path
        )
        used_includes.update(refs)
        errors.extend(tpl_errors)

    for inc_file in sorted(includes_dir.glob("*.html")):
        inc_text = inc_file.read_text(encoding="utf-8")
        used_includes.update(INCLUDE_TAG_RE.findall(inc_text))
        if inc_file.name not in used_includes:
            errors.append(
                f"Unused partial '_includes/{inc_file.name}' is not referenced by any layout or post"
            )
    return errors


def check_css(repo_root: Path) -> list[str]:
    """Verify CSS files have balanced braces and all var(--token) usages are defined."""
    errors: list[str] = []
    for css_rel in ("css/style.css", "css/syntax.css"):
        css_path = repo_root / css_rel
        if not css_path.is_file():
            errors.append(f"Missing stylesheet '{css_rel}'")
            continue
        stripped = re.sub(
            r"/\*.*?\*/", "", css_path.read_text(encoding="utf-8"), flags=re.DOTALL
        )
        if stripped.count("{") != stripped.count("}"):
            errors.append(f"{css_rel}: unbalanced curly braces")
        if css_rel == "css/style.css":
            defined_vars = set(CSS_VAR_DEF_RE.findall(stripped))
            used_vars = set(CSS_VAR_USE_RE.findall(stripped))
            for var_name in sorted(used_vars - defined_vars):
                errors.append(
                    f"{css_rel}: CSS custom property '{var_name}' is used but not defined in :root"
                )
    return errors


def render_post_catalog(posts: list[PostMetadata]) -> str:
    """Render deterministic Markdown content for docs/post-catalog.md."""
    lines = [
        "# Published Post Catalog",
        "",
        "Automatically generated by `python3 scripts/validate_site.py --generate-docs`. Do not edit by hand.",
        "",
        f"Total published posts: **{len(posts)}**",
        "",
        "| Date | Title | Permalink | Header Image | Source File |",
        "| --- | --- | --- | --- | --- |",
    ]
    for post in posts:
        lines.append(
            f"| `{post.date_prefix}` | {post.title} | `{post.permalink}` | `{post.header_img}` | `_posts/{post.filename}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _check_doc_file_paths(repo_root: Path, doc_name: str) -> list[str]:
    """Verify a Markdown documentation file exists and all backtick paths resolve."""
    doc_path = repo_root / doc_name
    if not doc_path.is_file():
        return [f"Missing required documentation file '{doc_name}'"]
    doc_text = doc_path.read_text(encoding="utf-8")
    errors = (
        [f"{doc_name} must contain at least 100 characters"]
        if len(doc_text.strip()) < 100
        else []
    )
    for match in DOC_PATH_RE.findall(doc_text):
        if "*" in match or "<" in match or "YYYY" in match or match.startswith("/"):
            continue
        if match not in ("_site/", "_site", ".env") and not (repo_root / match.rstrip("/")).exists():
            errors.append(f"{doc_name} references non-existent path '{match}'")
    return errors


def check_documentation_and_agents_md(
    repo_root: Path, posts: list[PostMetadata], generate_docs: bool = False
) -> list[str]:
    """Validate AGENTS.md and README.md references and verify/update docs/post-catalog.md."""
    errors: list[str] = []
    catalog_path = repo_root / "docs" / "post-catalog.md"
    expected_catalog = render_post_catalog(posts)

    if generate_docs:
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(expected_catalog, encoding="utf-8")
    elif not catalog_path.is_file() or catalog_path.read_text(encoding="utf-8") != expected_catalog:
        errors.append(
            "docs/post-catalog.md is missing or out of date (run 'python3 scripts/validate_site.py --generate-docs')"
        )

    for doc_name in ("AGENTS.md", "README.md", "CONTRIBUTING.md"):
        errors.extend(_check_doc_file_paths(repo_root, doc_name))
    return errors


def validate_repository(
    repo_root: Path,
    check_format: bool = False,
    fix_format: bool = False,
    check_docs: bool = False,
    generate_docs: bool = False,
) -> list[str]:
    """Run all site, configuration, AST, documentation, and formatting validations."""
    errors: list[str] = []
    errors.extend(check_config_and_gems(repo_root))
    posts, post_errors = collect_and_validate_posts(repo_root)
    errors.extend(post_errors)
    errors.extend(check_templates_and_pages(repo_root))
    errors.extend(check_css(repo_root))
    errors.extend(check_python_code_quality(repo_root))

    if check_docs or generate_docs:
        errors.extend(
            check_documentation_and_agents_md(
                repo_root, posts, generate_docs=generate_docs
            )
        )
    if fix_format or check_format:
        errors.extend(check_or_format_files(repo_root, fix=fix_format))
    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for site validation and doc generation."""
    parser = argparse.ArgumentParser(
        description="Validate Jekyll site structure, CSS tokens, formatting, and docs."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the repository root",
    )
    parser.add_argument("--check-format", action="store_true")
    parser.add_argument("--format", action="store_true")
    parser.add_argument("--check-docs", action="store_true")
    parser.add_argument("--generate-docs", action="store_true")
    args = parser.parse_args(argv)
    logger = get_logger()
    repo_root = args.root.resolve()

    errors = validate_repository(
        repo_root=repo_root,
        check_format=args.check_format,
        fix_format=args.format,
        check_docs=args.check_docs,
        generate_docs=args.generate_docs,
    )
    if errors:
        for err in errors:
            logger.error(err, extra={"context": {"repo_root": str(repo_root)}})
        return 1

    logger.info(
        "Site validation succeeded",
        extra={
            "context": {
                "repo_root": str(repo_root),
                "check_format": args.check_format,
                "check_docs": args.check_docs,
            }
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
