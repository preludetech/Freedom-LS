from django.apps import AppConfig


class MetaPixelAppConfig(AppConfig):
    name = "freedom_ls.meta_pixel"
    label = "freedom_ls_meta_pixel"
    verbose_name = "Meta pixel"

    def ready(self) -> None:
        from freedom_ls.meta_pixel import checks  # noqa: F401
