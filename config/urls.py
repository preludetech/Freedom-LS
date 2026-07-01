"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import JsonResponse
from django.urls import include, path

from freedom_ls.base.sitemaps import StaticViewSitemap
from freedom_ls.base.views import robots_txt
from freedom_ls.content_engine.sitemaps import CourseSitemap

# from ninja import NinjaAPI

ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "admin/")


def health_check(request):
    """Simple health check endpoint for Docker and load balancers."""
    return JsonResponse({"status": "healthy"})


# api = NinjaAPI()

# api.add_router("xapi/", "xapi_learning_record_store.api.router")
# api.add_router("student/", "student_interface.apis.router")


_sitemaps = {
    "static": StaticViewSitemap,
    "courses": CourseSitemap,
}

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path(ADMIN_URL, admin.site.urls),
    # Robots and sitemap — registered before the student_interface catch-all
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": _sitemaps},
        name="sitemap",
    ),
    # path("api/", api.urls),
    # path("api/xapi/", include("xapi_learning_record_store.api_urls")),
    # path("api/", api.urls),
    # path("content_preview/", include("content_engine.preview_urls")),
    path("educator/", include("freedom_ls.educator_interface.urls")),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("freedom_ls.accounts.urls")),
    path("", include("freedom_ls.student_interface.urls")),
    path("applications/", include("freedom_ls.course_applications.urls")),
    # path("_allauth/", include("allauth.headless.urls")),
]

# Serve media files during development
if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
        # QA-TEMP: toast playground (removed once toast spec QA is complete)
        path("qa/", include("freedom_ls.qa_helpers.urls")),
    ]

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += debug_toolbar_urls()
