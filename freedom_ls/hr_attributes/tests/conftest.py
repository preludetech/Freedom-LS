"""Collection gate for an app a project may leave out of INSTALLED_APPS."""

from freedom_ls.tests.app_guards import ignore_tests_unless_installed

collect_ignore_glob = ignore_tests_unless_installed("freedom_ls.hr_attributes")
