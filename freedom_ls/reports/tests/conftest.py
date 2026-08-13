import pytest


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
