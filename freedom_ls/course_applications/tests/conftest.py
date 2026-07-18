from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.course_applications"):
    collect_ignore_glob = ["test_*.py"]
