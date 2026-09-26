from django.apps import AppConfig


class TikTokPixelAppConfig(AppConfig):
    name = "freedom_ls.tiktok_pixel"
    label = "freedom_ls_tiktok_pixel"
    verbose_name = "TikTok pixel"

    def ready(self) -> None:
        from freedom_ls.tiktok_pixel import checks  # noqa: F401
