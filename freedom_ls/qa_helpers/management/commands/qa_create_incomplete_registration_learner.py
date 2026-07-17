"""Create QA data for the registration-completion middleware exemption test.

Sets up (idempotently) on a single site (default: DemoDev):

1. A ``SiteSignupPolicy`` for the site whose ``additional_registration_forms``
   requires at least one post-verification registration form. The only
   protocol-compliant concrete form class in the repo is the test fixture
   ``PhoneNumberForm`` (there is no production registration form shipped);
   it loads cleanly through ``load_registration_form_classes`` and, for a
   fresh learner, reports ``is_complete() == False`` so the middleware gate
   fires. If the site policy already lists a form, it is left untouched.

2. A login-ready learner whose registration is INCOMPLETE:
   - active + verified/primary EmailAddress (so they can log in),
   - NOT staff / NOT superuser (superusers/staff are exempt from the gate),
   - has NOT completed the required form, so
     ``RegistrationCompletionMiddleware`` redirects them to
     ``accounts:complete_registration`` on any non-exempt page.
   - Login convention in this project is password == email.

All objects are created with site-aware factories and the explicit ``site=``
override (the factories' thread-local site default is None outside a request).
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy, User
from freedom_ls.accounts.registration_forms import get_incomplete_forms

LEARNER_EMAIL = "demodev_incomplete_reg@email.com"

# Only protocol-compliant concrete form in the repo. A fresh learner is not in
# its process-local store, so is_complete() is False -> the gate fires. On a
# server restart the store resets, so the learner stays reliably incomplete.
REGISTRATION_FORM_PATH = (
    "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"
)


def _get_or_create_learner(site: Site) -> User:
    """Create the QA learner (password == email), or return the existing one.

    Guarantees the login-ready + non-privileged preconditions on every run.
    """
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.is_staff = False
        existing.is_superuser = False
        existing.set_password(LEARNER_EMAIL)
        existing.save(
            update_fields=["is_active", "is_staff", "is_superuser", "password"]
        )
        return existing
    return cast(
        User,
        UserFactory(
            email=LEARNER_EMAIL,
            first_name="DemoDev",
            last_name="Incomplete Registration",
            is_active=True,
            is_staff=False,
            password=LEARNER_EMAIL,
            site=site,
        ),
    )


def _ensure_verified_email(user: User) -> None:
    """Ensure a verified, primary EmailAddress exists (allauth login requires it)."""
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _ensure_policy_with_form(site: Site) -> SiteSignupPolicy:
    """Ensure the site policy requires at least one additional registration form.

    Idempotent: if a policy already exists it is preserved; the required form
    is only added when the site currently lists none. A brand-new policy row
    explicitly sets ``require_terms_acceptance=True`` to preserve the dev
    signup behaviour (a fresh row would otherwise reset it to the model
    default of False).
    """
    policy: SiteSignupPolicy | None = SiteSignupPolicy.objects.filter(site=site).first()
    if policy is None:
        return cast(
            SiteSignupPolicy,
            SiteSignupPolicyFactory(
                site=site,
                allow_signups=True,
                require_name=True,
                require_terms_acceptance=True,
                additional_registration_forms=[REGISTRATION_FORM_PATH],
            ),
        )

    if not policy.additional_registration_forms:
        policy.additional_registration_forms = [REGISTRATION_FORM_PATH]
        policy.save(update_fields=["additional_registration_forms"])
    return policy


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create the incomplete-registration learner + gating policy.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    policy = _ensure_policy_with_form(site)
    learner = _get_or_create_learner(site)
    _ensure_verified_email(learner)

    incomplete = get_incomplete_forms(
        learner, list(policy.additional_registration_forms)
    )
    incomplete_names = [cls.__name__ for cls in incomplete]

    click.secho(
        "\n--- Registration-Completion Middleware QA data ---", fg="cyan", bold=True
    )
    click.secho(f"Site: {site.name} (domain: {site.domain})", fg="cyan")
    click.secho(
        f"Policy additional_registration_forms: {policy.additional_registration_forms}",
        fg="green",
    )
    click.secho(
        f"Learner login: {learner.email} / {learner.email} "
        f"(active={learner.is_active}, staff={learner.is_staff}, "
        f"superuser={learner.is_superuser}, verified email present)",
        fg="green",
        bold=True,
    )
    gate_ok = bool(incomplete_names)
    click.secho(
        f"Incomplete forms for learner (gate fires if non-empty): {incomplete_names}",
        fg="green" if gate_ok else "red",
        bold=True,
    )
    if not gate_ok:
        raise click.ClickException(
            "Learner is NOT gated — check policy forms / learner privileges."
        )
