import pytest

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.blog.checks import check_blog_url_prefix


def test_blog_url_prefix_check_is_registered():
    assert check_blog_url_prefix in registry.registry.get_checks()


@pytest.mark.parametrize("prefix", ["/articles", "articles/", "Art icles", "News"])
def test_malformed_prefix_reports_e001(prefix):
    # Act
    with override_settings(BLOG_URL_PREFIX=prefix):
        errors = check_blog_url_prefix(None)

    # Assert
    assert [error.id for error in errors] == ["freedom_ls_blog.E001"]


@pytest.mark.parametrize("prefix", ["articles", "news/blog"])
def test_well_formed_prefix_reports_nothing(prefix):
    # Act
    with override_settings(BLOG_URL_PREFIX=prefix):
        errors = check_blog_url_prefix(None)

    # Assert
    assert errors == []


def test_empty_prefix_falls_back_to_default_and_reports_nothing():
    # Act
    with override_settings(BLOG_URL_PREFIX=""):
        errors = check_blog_url_prefix(None)

    # Assert
    assert errors == []
