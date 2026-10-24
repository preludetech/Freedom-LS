"""Collection guard for the course_interest tests."""

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.course_interest"):
    collect_ignore_glob = ["test_*.py"]
