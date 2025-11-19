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

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from ninja import NinjaAPI

api = NinjaAPI()

# api.add_router("xapi/", "xapi_learning_record_store.api.router")
# api.add_router("student/", "student_interface.apis.router")


urlpatterns = [
    path("admin/", admin.site.urls),
    # path("api/", api.urls),
    # path("api/xapi/", include("xapi_learning_record_store.api_urls")),
    # path("api/", api.urls),
    path("__reload__/", include("django_browser_reload.urls")),
    # path("content_preview/", include("content_engine.preview_urls")),
    path("educator/", include("educator_interface.urls")),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),
    path("__/si/", include("student_interface.urls")),
    # path("_allauth/", include("allauth.headless.urls")),
]

# Serve media files during development
if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += debug_toolbar_urls()
