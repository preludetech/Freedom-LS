"""Collection guard for the course_interest tests."""

from freedom_ls.tests.app_guards import ignore_tests_unless_installed

collect_ignore_glob = ignore_tests_unless_installed("freedom_ls.course_interest")
