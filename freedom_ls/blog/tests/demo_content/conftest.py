from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.demo_content_fixtures import *  # noqa: F403

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.blog"):
    collect_ignore_glob = ["test_*.py"]
