from django.apps import AppConfig


class SystemBaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'system_base'
