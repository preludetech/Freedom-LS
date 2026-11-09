import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.accounts.search import term_condition


@pytest.mark.django_db
def test_every_word_must_match_across_name_and_email(mock_site_context) -> None:
    jane = UserFactory(first_name="Jane", last_name="Smith", email="js@example.com")
    UserFactory(first_name="Jane", last_name="Jones", email="jj@example.com")

    found = User.objects.filter(term_condition("jane smith", include_email=True))

    assert list(found) == [jane]


@pytest.mark.django_db
def test_the_email_is_matched_only_when_asked(mock_site_context) -> None:
    user = UserFactory(first_name="Ada", last_name="Lovelace", email="zed@example.com")

    with_email = User.objects.filter(term_condition("zed", include_email=True))
    without_email = User.objects.filter(term_condition("zed", include_email=False))

    assert list(with_email) == [user]
    assert not without_email.exists()


@pytest.mark.django_db
def test_a_term_with_no_words_does_not_narrow(mock_site_context) -> None:
    UserFactory()

    assert User.objects.filter(term_condition("  ", include_email=True)).count() == 1
