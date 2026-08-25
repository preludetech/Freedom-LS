import pytest

from django.contrib.staticfiles import finders

# `static/vendor/tailwind.output.css` is a build artefact, not a checked-in file:
# extract_theme_tokens() reads it and build_report_html() calls that, so every
# test that renders a whole report needs `npm run tailwind_build` to have run.
# CI builds it before running pytest; a fresh clone has not.
requires_tailwind_bundle = pytest.mark.skipif(
    finders.find("vendor/tailwind.output.css") is None,
    reason="compiled Tailwind bundle missing -- run `npm run tailwind_build`",
)
