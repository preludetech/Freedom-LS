import djclick as click
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model

User = get_user_model()


@click.command()
@click.argument("site_name")
@click.argument("site_domain")
def command(site_name, site_domain):
    site, created = Site.objects.get_or_create(
        domain=site_domain,
        defaults={"name": site_name},
    )

    user_email = f"{site_name.lower()}@email.com"
    if not User.objects.filter(email=user_email).exists():
        user = User(
            email=user_email,
            is_staff=True,
            is_superuser=True,
            is_active=True,
            site=site,
        )
        user.set_password(user_email)
        user.save()
