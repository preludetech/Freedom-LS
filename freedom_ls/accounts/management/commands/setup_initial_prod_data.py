"""First-run bootstrap for a production deployment: the Site, the administrative
User and its verified allauth EmailAddress."""

import djclick as click
from allauth.account.models import EmailAddress

from django.conf import settings
from django.contrib.sites.models import Site
from django.utils.crypto import get_random_string

from freedom_ls.accounts.models import User, UserManager

# 22 characters over get_random_string's 62-character alphabet is ~131 bits.
GENERATED_PASSWORD_LENGTH = 22


@click.command()
@click.argument("admin_email")
@click.option(
    "--domain",
    default=None,
    help="The Site's domain. Defaults to HOST_DOMAIN from the active settings module.",
)
@click.option(
    "--site-name",
    default=None,
    help="The Site's display name. Defaults to the resolved domain.",
)
def command(admin_email: str, domain: str | None, site_name: str | None) -> None:
    """Create the Site, the administrative User and its verified email address."""
    # normalize_email lives on UserManager and is the only thing that lowercases the
    # domain part. User.email is unique and case-sensitive in Postgres, so an address
    # taken verbatim here would let a later signup create a second row for the same
    # mailbox.
    email = UserManager.normalize_email(admin_email)
    resolved_domain = _resolve_domain(domain)
    site = _get_or_create_site(resolved_domain, site_name or resolved_domain)
    password = _get_or_create_admin_user(email, site)
    if password is not None:
        click.echo(f"Created administrator {email} with password: {password}")
        click.echo("This password is shown once and is stored nowhere. Record it now.")
    else:
        click.echo(f"Administrator {email} already exists; password unchanged.")


def _resolve_domain(domain: str | None) -> str:
    if domain:
        return domain
    host_domain = getattr(settings, "HOST_DOMAIN", "")
    if not host_domain:
        raise click.ClickException(
            "No --domain given and HOST_DOMAIN is not set in this settings module."
        )
    return str(host_domain)


def _get_or_create_site(domain: str, name: str) -> Site:
    # Domain is unique; name is not. A lookup keyed on name could match a row
    # whose domain differs from the one just resolved, and writing only the name
    # field would leave that wrong domain in place.
    site, _created = Site.objects.get_or_create(domain=domain, defaults={"name": name})
    return site


def _get_or_create_admin_user(email: str, site: Site) -> str | None:
    """Return the generated password when the User was created, else None.

    set_password is reachable only on the create branch, so a second run never
    resets an existing administrator's credential.

    An address already held by an ordinary account is a hard failure, not a
    no-op: reporting success there would leave the deployment with no
    administrator at all, and promoting the row instead would hand a superuser
    to whoever a mistyped address belongs to. Raised before the EmailAddress
    write, so a stranger's address is never marked verified on the way past.

    _base_manager, not the site-aware `objects`: email is globally unique, and a
    lookup that narrowed to an ambient site would miss an existing administrator
    and try to create a second row with the same address. The lookup is
    case-insensitive because the column is not, so a row that predates
    normalization is found rather than collided with.
    """
    existing = User._base_manager.filter(email__iexact=email).first()
    if existing is not None:
        if not (existing.is_staff and existing.is_superuser and existing.is_active):
            raise click.ClickException(
                f"An account already exists for {email}, but it is not an active "
                f"administrator. Refusing to touch it. Give this command a "
                f"different address, or grant that account staff, superuser and "
                f"active status deliberately."
            )
        _ensure_verified_email(existing)
        return None

    # UserManager.create_user/create_superuser take no site argument, so the row
    # is constructed directly.
    password = get_random_string(GENERATED_PASSWORD_LENGTH)
    user = User(
        email=email, site=site, is_staff=True, is_superuser=True, is_active=True
    )
    user.set_password(password)
    user.save()
    _ensure_verified_email(user)
    return password


def _ensure_verified_email(user: User) -> None:
    EmailAddress.objects.get_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
