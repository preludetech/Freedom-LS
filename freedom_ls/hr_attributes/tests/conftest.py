"""Collection gate for an app a project may leave out of INSTALLED_APPS."""

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.hr_attributes"):
    collect_ignore_glob = ["test_*.py"]
