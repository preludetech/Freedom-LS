from django.apps import AppConfig


class BlogAppConfig(AppConfig):
    name = "freedom_ls.blog"
    label = "freedom_ls_blog"
    verbose_name = "Blog"

    def ready(self) -> None:
        from freedom_ls.blog import checks  # noqa: F401
