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


@pytest.fixture(autouse=True)
def isolated_reports_storage(tmp_path, settings) -> None:
    """Report files go to tmp_path, never the developer's real media/ directory.

    settings_base / settings_dev declare no STORAGES at all, so
    get_reports_storage() falls through to the default FileSystemStorage rooted
    at MEDIA_ROOT. Without this fixture every test that saves a report file
    would write a real PDF into the developer's live media/ directory on every
    run, permanently.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "reports": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
