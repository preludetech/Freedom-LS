from django.conf import settings

collect_ignore_glob: list[str] = []
if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    collect_ignore_glob = ["test_*.py"]
