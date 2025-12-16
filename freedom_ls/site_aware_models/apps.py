from django.apps import AppConfig


class SiteAwareModelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.site_aware_models"
    label = "freedom_ls_site_aware_models"
