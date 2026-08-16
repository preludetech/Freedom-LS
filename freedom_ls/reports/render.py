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

from freedom_ls.reports.gather import CohortReportData

if TYPE_CHECKING:
    from collections.abc import Callable

    from weasyprint.urls import URLFetcherResponse


class ReportRenderError(Exception):
    """Raised for every render-time failure in this module.

    The single exception type the Phase 5 task layer needs to catch, covering
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
            "compiled Tailwind bundle."
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


def build_report_html(data: CohortReportData) -> str:
    """Render `data` through the report template tree. No ORM access."""
    print_css = _find_static("reports/print.css").read_text()
    theme_tokens = extract_theme_tokens()
    return render_to_string(
        "reports/report.html",
        {"data": data, "theme_tokens": theme_tokens, "print_css": print_css},
    )


def _restrictive_url_fetcher(trusted_dir: Path) -> Callable[[str], URLFetcherResponse]:
    """Build a URL fetcher confined to this report's own bundled static assets.

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

    The report's own `print.css` references its bundled DejaVu fonts by a
    relative `url()`, which WeasyPrint resolves through this same fetcher --
    so it cannot refuse every URL unconditionally without breaking font
    loading. It allows `file://` reads confined to `trusted_dir` (this
    report's own static directory, holding only developer-authored assets)
    and refuses everything else, including any file path outside that
    directory and any `http(s)` URL that author-supplied text might
    reference.
    """
    trusted_dir = trusted_dir.resolve()

    def fetch(url: str) -> URLFetcherResponse:
        from weasyprint.urls import FatalURLFetchingError, default_url_fetcher

        parsed = urlsplit(url)
        if parsed.scheme == "file":
            path = Path(url2pathname(parsed.path)).resolve()
            if path.is_relative_to(trusted_dir):
                return default_url_fetcher(url)
        raise FatalURLFetchingError(f"External resource fetch refused: {url}")

    return fetch


def render_report_pdf(data: CohortReportData) -> bytes:
    """Render `data` to PDF bytes via WeasyPrint."""
    import weasyprint
    from weasyprint.urls import FatalURLFetchingError

    html = build_report_html(data)
    base_dir = _find_static("reports/print.css").resolve().parent
    url_fetcher = _restrictive_url_fetcher(base_dir)
    try:
        pdf_bytes: bytes = weasyprint.HTML(
            string=html, base_url=str(base_dir), url_fetcher=url_fetcher
        ).write_pdf()
        return pdf_bytes
    except FatalURLFetchingError as exc:
        raise ReportRenderError(str(exc)) from exc
