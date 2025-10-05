from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

demo_sites = [
    {"name": "Wrend", "domain": "127.0.0.1:8000"},
    {"name": "UAVI", "domain": "127.0.0.1:8001"},
]


class Command(BaseCommand):
    help = "Create a superuser and 2 sites for initial setup"

    def handle(self, *args, **options):
        User = get_user_model()

        # Create superuser
        admin_email = "super@email.com"
        admin_user, admin_created = User.objects.get_or_create(
            email=admin_email,
            defaults={"is_staff": True, "is_superuser": True},
        )
        if admin_created:
            admin_user.set_password(admin_email)
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{admin_email}' created successfully")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"Superuser '{admin_email}' already exists")
            )

        # Create sites and users
        for site_data in demo_sites:
            site, created = Site.objects.get_or_create(
                domain=site_data["domain"],
                defaults={"name": site_data["name"]},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Site '{site.name}' created"))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Site '{site.name}' already exists")
                )

            # Add site to superuser
            admin_user.sites.add(site)

            # Create user for this site
            user_email = f"{site_data['name'].lower()}@email.com"
            if not User.objects.filter(email=user_email).exists():
                user = User.objects.create_user(
                    email=user_email,
                    password=user_email,
                    is_staff=True,
                    is_superuser=True,
                )
                user.sites.add(site)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"User '{user_email}' created for site '{site.name}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"User '{user_email}' already exists")
                )

        self.stdout.write(self.style.SUCCESS("\nSetup complete!"))
