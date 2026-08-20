from django.apps import AppConfig


class OrganisationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.organisations"
    label = "freedom_ls_organisations"

    def ready(self) -> None:
        from django.db.models.signals import post_migrate

        from . import signals

        # sender=self so this fires once, for this app, rather than once per
        # installed app.
        post_migrate.connect(
            signals.ensure_default_organisations_after_migrate, sender=self
        )
