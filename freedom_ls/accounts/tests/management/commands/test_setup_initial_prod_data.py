"""Tests for the setup_initial_prod_data bootstrap command."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO

import pytest
from click import ClickException

from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.organisations.models import Organisation


@pytest.mark.django_db
def test_first_run_creates_site_with_given_domain_and_name(
    mock_site_context: Site,
) -> None:
    """A fresh domain gets a Site row keyed on that domain and name."""
    _call_setup(
        "admin@example.org", "--domain", "example.org", "--site-name", "Example"
    )

    site = Site.objects.get(domain="example.org")
    assert site.name == "Example"


@pytest.mark.django_db
def test_first_run_creates_active_staff_superuser_on_that_site(
    mock_site_context: Site,
) -> None:
    """The administrative User is staff, superuser, active, and tied to the new Site."""
    _call_setup("admin@example.org", "--domain", "example.org")

    site = Site.objects.get(domain="example.org")
    user = User._base_manager.get(email="admin@example.org")
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True
    assert user.site == site


@pytest.mark.django_db
def test_first_run_creates_verified_primary_email_address(
    mock_site_context: Site,
) -> None:
    """The allauth EmailAddress for the new administrator is verified and primary."""
    from allauth.account.models import EmailAddress

    _call_setup("admin@example.org", "--domain", "example.org")

    user = User._base_manager.get(email="admin@example.org")
    email_address = EmailAddress.objects.get(user=user, email=user.email)
    assert email_address.verified is True
    assert email_address.primary is True


@pytest.mark.django_db
def test_first_run_prints_generated_password(mock_site_context: Site) -> None:
    """First run prints a password to stdout for the operator to record."""
    out = _call_setup("admin@example.org", "--domain", "example.org")

    assert "password" in out.lower()


@pytest.mark.django_db
def test_second_run_leaves_password_hash_unchanged(mock_site_context: Site) -> None:
    """Running the command again against the same domain and email keeps the hash byte-identical."""
    _call_setup("admin@example.org", "--domain", "example.org")
    original_hash = User._base_manager.get(email="admin@example.org").password

    _call_setup("admin@example.org", "--domain", "example.org")

    assert User._base_manager.get(email="admin@example.org").password == original_hash


@pytest.mark.django_db
def test_second_run_prints_no_credential(mock_site_context: Site) -> None:
    """Running the command again does not repeat the generated password."""
    first_out = _call_setup("admin@example.org", "--domain", "example.org")
    generated_password = first_out.rsplit("password: ", 1)[1].splitlines()[0]

    second_out = _call_setup("admin@example.org", "--domain", "example.org")

    assert generated_password not in second_out


@pytest.mark.django_db
def test_existing_site_keeps_its_name_when_domain_matches(
    mock_site_context: Site,
) -> None:
    """A Site already keyed on the resolved domain is looked up by domain, not renamed.

    create_site keyed its lookup on name and reassigned domain without saving. Keying
    on domain instead means a --site-name mismatch never touches the existing row.
    """
    _call_setup(
        "admin@example.org",
        "--domain",
        mock_site_context.domain,
        "--site-name",
        "New Name",
    )

    site = Site.objects.get(domain=mock_site_context.domain)
    assert site.name == mock_site_context.name
    assert site.domain == mock_site_context.domain


@pytest.mark.django_db
def test_missing_site_name_refuses_rather_than_naming_the_site_after_its_domain(
    mock_site_context: Site,
) -> None:
    """Without --site-name the Site would be named after its own domain.

    The display name is what allauth's email subject prefix, the site header and
    the cohort reports all show, so a deployment that skipped the flag branded
    itself "learn.example.com" everywhere the product's name belonged.
    """
    with pytest.raises((ClickException, CommandError, SystemExit)):
        call_command(
            "setup_initial_prod_data", "admin@example.org", "--domain", "example.org"
        )

    assert not Site.objects.filter(domain="example.org").exists()


def test_missing_domain_under_settings_with_no_host_domain_raises_click_exception() -> (
    None
):
    """With no --domain and no HOST_DOMAIN on the active settings module, the command refuses."""
    with pytest.raises(ClickException):
        _call_setup("admin@example.org")


@pytest.mark.django_db
def test_first_run_gives_the_new_site_a_default_organisation(
    mock_site_context: Site,
) -> None:
    """The Site's post_save receiver still fires and creates a default Organisation."""
    _call_setup("admin@example.org", "--domain", "example.org")

    site = Site.objects.get(domain="example.org")
    organisation = Organisation._base_manager.get(site=site, is_default=True)
    assert organisation.site == site


@pytest.mark.django_db
def test_bootstrapped_site_serves_login_signup_and_password_reset_pages(
    mock_site_context: Site,
) -> None:
    """The rows the command writes are sufficient for allauth's auth pages to resolve."""
    _call_setup("admin@example.org", "--domain", mock_site_context.domain)
    client = Client()

    login_response = client.get(reverse("account_login"))
    signup_response = client.get(reverse("account_signup"))
    reset_response = client.get(reverse("account_reset_password"))

    assert login_response.status_code == 200
    assert signup_response.status_code == 200
    assert reset_response.status_code == 200


@pytest.mark.django_db
def test_address_held_by_an_ordinary_account_refuses(mock_site_context: Site) -> None:
    """An address that belongs to a learner is a failure, not a silent no-op.

    Reporting success there would leave the deployment with no administrator.
    """
    UserFactory(email="learner@example.org")

    with pytest.raises(ClickException):
        _call_setup("learner@example.org", "--domain", "example.org")


@pytest.mark.django_db
def test_refusal_leaves_the_ordinary_account_email_unverified(
    mock_site_context: Site,
) -> None:
    """The refusal comes before the EmailAddress write, so nothing is verified in passing."""
    from allauth.account.models import EmailAddress

    UserFactory(email="learner@example.org")

    with pytest.raises(ClickException):
        _call_setup("learner@example.org", "--domain", "example.org")

    assert not EmailAddress.objects.filter(email="learner@example.org").exists()


@pytest.mark.django_db
def test_inactive_administrator_refuses(mock_site_context: Site) -> None:
    """Staff and superuser are not enough on their own; a disabled account cannot log in."""
    UserFactory(email="admin@example.org", superuser=True, is_active=False)

    with pytest.raises(ClickException):
        _call_setup("admin@example.org", "--domain", "example.org")


@pytest.mark.django_db
def test_mixed_case_address_is_stored_normalized(mock_site_context: Site) -> None:
    """normalize_email lowercases the domain part before the row is written."""
    _call_setup("Admin@Example.ORG", "--domain", "example.org")

    assert User._base_manager.get(email="Admin@example.org")


@pytest.mark.django_db
def test_second_run_in_different_case_creates_no_second_row(
    mock_site_context: Site,
) -> None:
    """The column is case-sensitive in Postgres, so the lookup must not be."""
    _call_setup("admin@example.org", "--domain", "example.org")

    _call_setup("ADMIN@example.org", "--domain", "example.org")

    assert User._base_manager.filter(email__iexact="admin@example.org").count() == 1


@pytest.mark.django_db
def test_create_site_command_no_longer_exists() -> None:
    """create_site was deleted; Django reports it as an unknown command."""
    with pytest.raises(CommandError):
        call_command("create_site")


@pytest.mark.django_db
def test_create_site_superuser_command_no_longer_exists() -> None:
    """create_site_superuser was deleted; Django reports it as an unknown command."""
    with pytest.raises(CommandError):
        call_command("create_site_superuser")


def _call_setup(*args: str) -> str:
    """Call setup_initial_prod_data and return stdout.

    --site-name is required by the command, so a caller that does not care about
    the display name gets a placeholder rather than repeating the flag.
    """
    if "--site-name" not in args:
        args = (*args, "--site-name", "Test Site")
    out = StringIO()
    with redirect_stdout(out):
        call_command("setup_initial_prod_data", *args)
    return out.getvalue()


@pytest.mark.django_db
def test_second_run_verifies_an_existing_unverified_email_address(
    mock_site_context: Site,
) -> None:
    """An administrator promoted from an ordinary account can actually log in.

    get_or_create applies its defaults only on the create branch, so an address
    that already existed kept verified=False. With mandatory email verification
    that left the command reporting success while the operator was locked out.
    """
    from allauth.account.models import EmailAddress

    # Arrange
    user = UserFactory(
        email="admin@example.org", is_staff=True, is_superuser=True, is_active=True
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=False, primary=False
    )

    # Act
    _call_setup("admin@example.org", "--domain", "example.org")

    # Assert
    email_address = EmailAddress.objects.get(user=user, email=user.email)
    assert email_address.verified is True


@pytest.mark.django_db
def test_second_run_claims_primacy_when_no_other_address_holds_it(
    mock_site_context: Site,
) -> None:
    from allauth.account.models import EmailAddress

    # Arrange
    user = UserFactory(
        email="admin@example.org", is_staff=True, is_superuser=True, is_active=True
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=False, primary=False
    )

    # Act
    _call_setup("admin@example.org", "--domain", "example.org")

    # Assert
    email_address = EmailAddress.objects.get(user=user, email=user.email)
    assert email_address.primary is True


@pytest.mark.django_db
def test_second_run_leaves_an_already_verified_primary_address_alone(
    mock_site_context: Site,
) -> None:
    from allauth.account.models import EmailAddress

    # Arrange
    user = UserFactory(
        email="admin@example.org", is_staff=True, is_superuser=True, is_active=True
    )
    original = EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )

    # Act
    _call_setup("admin@example.org", "--domain", "example.org")

    # Assert
    original.refresh_from_db()
    assert (original.verified, original.primary) == (True, True)


@pytest.mark.django_db
def test_second_run_does_not_take_primacy_from_another_address(
    mock_site_context: Site,
) -> None:
    """EmailAddress constrains (user, primary) among primary rows.

    A bare primary=True write would raise IntegrityError here. Verification is
    the half that matters anyway: allauth authenticates against any verified
    address, not only the primary one.
    """
    from allauth.account.models import EmailAddress

    # Arrange
    user = UserFactory(
        email="admin@example.org", is_staff=True, is_superuser=True, is_active=True
    )
    other = EmailAddress.objects.create(
        user=user, email="other@example.org", verified=True, primary=True
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=False, primary=False
    )

    # Act
    _call_setup("admin@example.org", "--domain", "example.org")

    # Assert
    other.refresh_from_db()
    admin_address = EmailAddress.objects.get(user=user, email=user.email)
    assert (other.primary, admin_address.verified) == (True, True)
