from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    name = "freedom_ls.webhooks"
    label = "freedom_ls_webhooks"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Webhooks"
