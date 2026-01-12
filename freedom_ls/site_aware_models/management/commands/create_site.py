import djclick as click
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


@click.command()
@click.argument("site_name")
@click.argument("site_domain")
@click.option("--email", default=None, help="Email address for the superuser")
@click.option("--password", default=None, help="Password for the superuser")
def command(site_name, site_domain, email, password):
    site, created = Site.objects.get_or_create(
        name=site_name,
        defaults={"domain": site_domain},
    )

    if site.domain != site_domain:
        site.domain = site_domain

    user_email = email if email else f"{site_name.lower()}@email.com"
    user_password = password if password else user_email

    user, user_created = User.objects.get_or_create(
        email=user_email,
        defaults={
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "site": site,
        }
    )

    if user_created:
        user.set_password(user_password)
        user.save()

    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True}
    )
