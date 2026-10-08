"""Guards the vendored KaTeX CSS against referencing font files that are not
vendored alongside it.

`katex.min.css` ships `@font-face` rules; only the `.woff2` fonts are vendored.
Any `url(fonts/…)` reference to a missing file breaks a production
`collectstatic` under `ManifestStaticFilesStorage`'s strict mode (it hard-fails
on any referenced-but-absent static file), even though `.woff2` alone serves
every current browser.
"""

import re
from pathlib import Path

import freedom_ls.content_engine as content_engine

_KATEX_DIR = (
    Path(content_engine.__file__).parent
    / "static"
    / "content_engine"
    / "vendor"
    / "katex"
)

# Matches the target of every `url(fonts/…)` in the stylesheet (unquoted, as the
# minified file emits them).
_FONT_URL_RE = re.compile(r"url\((fonts/[^)]+)\)")


def test_katex_css_only_references_vendored_fonts() -> None:
    css = (_KATEX_DIR / "katex.min.css").read_text(encoding="utf-8")
    referenced = {match.group(1) for match in _FONT_URL_RE.finditer(css)}
    assert referenced, "expected at least one url(fonts/…) reference in katex.min.css"

    missing = sorted(ref for ref in referenced if not (_KATEX_DIR / ref).is_file())
    assert not missing, (
        "katex.min.css references vendored fonts that are not present: "
        f"{missing}. Vendor them or drop the references so a strict "
        "collectstatic does not fail."
    )
