"""Render a `CohortReportData` tree to HTML, and HTML to a PDF.

`weasyprint` is imported lazily, inside `render_report_pdf()` only, and never
at module level. Importing it eagerly would run its own import chain --
Pango, cairo, gdk-pixbuf, HarfBuzz -- at Django startup, which takes the
whole site down in any project missing those system libraries, even one that
never generates a report. Every other function in this module works without
weasyprint installed at all.

No ORM access happens anywhere in this module -- `build_report_html()` takes
the already-gathered `CohortReportData` tree and only renders it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from urllib.request import url2pathname

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string

from freedom_ls.reports.config import config
from freedom_ls.reports.gather import CohortReportData
from freedom_ls.site_aware_models.config import config as site_config

if TYPE_CHECKING:
    from collections.abc import Callable

    from weasyprint.urls import URLFetcherResponse


class ReportRenderError(Exception):
    """Raised for every render-time failure in this module.

    The single exception type the task layer needs to catch, covering
    a missing/unresolvable static asset, a malformed theme bundle, and a
    document that reached outside its own trusted static assets.
    """


def _find_static(relative_path: str) -> Path:
    """Resolve `relative_path` through the staticfiles finders.

    Never `settings.STATIC_ROOT`: that setting exists only in
    `config/settings_prod.py`, while the test suite runs on
    `config.settings_dev`, so a `STATIC_ROOT`-keyed lookup would pass in
    production and fail in CI. The finders search `STATICFILES_DIRS` and app
    static directories in development and fall through to collected storage
    in production -- one code path, every environment.
    """
    resolved = finders.find(relative_path)
    if resolved is None:
        raise ReportRenderError(
            f"Static asset {relative_path!r} could not be resolved through the "
            "staticfiles finders. Run `npm run tailwind_build` if this is the "
            "compiled Tailwind bundle; otherwise check the path against the "
            "setting that names it."
        )
    return Path(resolved)


def _extract_theme_tokens_from_css(css: str) -> str:
    """Pull the leading `:root`/`:host` custom-property block out of `css`.

    A narrow read of one declaration block -- not "feed WeasyPrint the whole
    compiled Tailwind bundle", which would drag in preflight and utilities
    that WeasyPrint mis-parses.

    The real bundle nests the block inside `@layer theme { :root, :host {
    ... } }`, and further nests `@supports` blocks for its `color-mix()`
    fallbacks, so the closing brace is found by walking brace depth rather
    than by the first `}` -- a `split("}")[0]` or a regex to the first `}`
    would terminate on the `@layer` block's own opening brace and return a
    truncated or empty token set. Filtering the captured lines to those
    starting with `--` is what then drops the `@supports` wrapper lines
    (and any other nested at-rule a future Tailwind version might add)
    while keeping the custom-property declarations nested inside them.
    """
    try:
        start = css.index("{", css.index(":root"))
    except ValueError as exc:
        raise ReportRenderError(
            "No :root declaration block found in the theme bundle."
        ) from exc

    depth = 0
    end: int | None = None
    for index, char in enumerate(css[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end is None:
        raise ReportRenderError("Unbalanced braces in the theme bundle.")

    declarations = [
        line.strip()
        for line in css[start + 1 : end].splitlines()
        if line.strip().startswith("--")
    ]
    return ":root {\n" + "\n".join(declarations) + "\n}"


def extract_theme_tokens() -> str:
    """Return the compiled Tailwind bundle's role-token block as a `:root { ... }` rule.

    The theme source declares these custom properties inside a Tailwind v4
    `@theme { }` at-rule, which WeasyPrint cannot parse -- the compiled
    bundle's custom properties are the only WeasyPrint-readable source of
    them.
    """
    path = _find_static("vendor/tailwind.output.css")
    return _extract_theme_tokens_from_css(path.read_text())


def build_font_css() -> tuple[str, set[Path]]:
    """Build the report's `@font-face` rules, and the font files they name.

    The report embeds its own fonts rather than naming system families:
    WeasyPrint substitutes silently for a family it cannot find and draws a
    `.notdef` box for a code point a family lacks, and neither shows up until
    somebody reads a printed report.

    Which faces those are is a setting, not a constant, for the same reason
    colours are a theme's to supply: a project on its own brand overrides
    `REPORTS_FONT_FACES` and the three stacks, and `print.css` -- which names
    no font family, only `var(--report-font-*)` -- does not change.

    The `src` URLs are absolute `file://` URLs, so font loading does not depend
    on the document's base URL and the URL fetcher can hold an exact-file
    allowlist rather than trusting a whole directory. Returns those resolved
    paths alongside the CSS for exactly that purpose.
    """
    rules: list[str] = []
    font_paths: set[Path] = set()
    for face in config.REPORTS_FONT_FACES:
        path = _find_static(face["static_path"]).resolve()
        font_paths.add(path)
        rules.append(
            "@font-face {\n"
            f'  font-family: "{face["family"]}";\n'
            f"  font-weight: {face['weight']};\n"
            f"  font-style: {face['style']};\n"
            f'  src: url("{path.as_uri()}") format("truetype");\n'
            "}"
        )
    stacks = (
        ":root {\n"
        f"  --report-font-display: {config.REPORTS_FONT_DISPLAY};\n"
        f"  --report-font-body: {config.REPORTS_FONT_BODY};\n"
        f"  --report-font-mono: {config.REPORTS_FONT_MONO};\n"
        "}"
    )
    return "\n".join([*rules, stacks]), font_paths


def _resolve_logo(static_path: str | None) -> tuple[str | None, Path | None]:
    """Resolve an optional logo static path to a `file://` URL and its file.

    An unset path is not a problem -- a fresh FLS install configures no logo,
    and the report is designed to read as complete without one. A path that is
    set but cannot be resolved is a misconfiguration, and raises rather than
    rendering a report with a hole where somebody expected their logo.
    """
    if not static_path:
        return None, None
    path = _find_static(static_path).resolve()
    return path.as_uri(), path


def _build_document(data: CohortReportData) -> tuple[str, set[Path]]:
    """Render the report to HTML, and collect every local file it may read."""
    print_css = _find_static("reports/print.css").read_text()
    theme_tokens = extract_theme_tokens()
    font_css, allowed_paths = build_font_css()
    site_logo_url, site_logo_path = _resolve_logo(site_config.HEADER_LOGO_STATIC_PATH)
    if site_logo_path:
        allowed_paths.add(site_logo_path)
    html = render_to_string(
        "reports/report.html",
        {
            "data": data,
            "theme_tokens": theme_tokens,
            "font_css": font_css,
            "print_css": print_css,
            "site_logo_url": site_logo_url,
        },
    )
    return html, allowed_paths


def build_report_html(data: CohortReportData) -> str:
    """Render `data` through the report template tree. No ORM access."""
    html, _ = _build_document(data)
    return html


def _restrictive_url_fetcher(
    allowed_paths: set[Path],
) -> Callable[[str], URLFetcherResponse]:
    """Build a URL fetcher confined to an exact set of local files.

    The report renders author-supplied question and option text, so
    WeasyPrint's default fetcher -- which follows any `http(s)://` or
    `file://` URL it is given -- is an SSRF and local-file-read surface.

    WeasyPrint 69.0 ships `weasyprint.urls.URLFetcher` with the
    `allowed_protocols` / `allow_redirects` constructor arguments the plan
    named, but verified empirically against the installed version: raising
    from inside a fetcher -- whether that class or a plain callable -- is
    caught and only logged by `weasyprint.urls.fetch()`, never propagated,
    unless the exception is a `weasyprint.urls.FatalURLFetchingError` (a
    `BaseException` subclass, deliberately not caught by that wrapper's
    `except Exception`). `URLFetcher(allowed_protocols=[], ...)` alone
    renders a document missing its external resources without raising
    anything at all -- a silent degrade, not the loud failure required here.
    So this fetcher raises `FatalURLFetchingError` directly, and
    `render_report_pdf()` re-raises it as `ReportRenderError`.

    The document does legitimately reference a few local files -- the
    configured font faces and, when a project sets them, the site and
    "powered by" logos -- so the fetcher cannot refuse every URL
    unconditionally. It allows exactly those files, named up front by
    `_build_document()`, and refuses everything else: any other file path,
    and any `http(s)` URL that author-supplied text might carry.

    An exact-file allowlist rather than a trusted directory, because every
    file the document may read is known before rendering starts. Nothing in
    the report resolves a file path at render time.
    """

    def fetch(url: str) -> URLFetcherResponse:
        from weasyprint.urls import FatalURLFetchingError, default_url_fetcher

        parsed = urlsplit(url)
        if parsed.scheme == "file":
            path = Path(url2pathname(parsed.path)).resolve()
            if path in allowed_paths:
                return default_url_fetcher(url)
        raise FatalURLFetchingError(f"External resource fetch refused: {url}")

    return fetch


def render_report_pdf(data: CohortReportData) -> bytes:
    """Render `data` to PDF bytes via WeasyPrint."""
    import weasyprint
    from weasyprint.urls import FatalURLFetchingError

    html, allowed_paths = _build_document(data)
    base_dir = _find_static("reports/print.css").resolve().parent
    url_fetcher = _restrictive_url_fetcher(allowed_paths)
    try:
        pdf_bytes: bytes = weasyprint.HTML(
            string=html, base_url=str(base_dir), url_fetcher=url_fetcher
        ).write_pdf()
        return pdf_bytes
    except FatalURLFetchingError as exc:
        raise ReportRenderError(str(exc)) from exc
