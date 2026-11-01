from drf_spectacular.renderers import OpenApiJsonRenderer
from drf_spectacular.views import SpectacularAPIView

from django.urls import path
from django.utils.module_loading import autodiscover_modules

from .authentication import ApiKeyAuthentication
from .permissions import HasApiKey
from .routers import router

app_name = "api"

# Each app's api.py registers its viewsets when imported; discovering them by
# name keeps this app free of an import of any endpoint app.
autodiscover_modules("api")

urlpatterns = [
    *router.urls,
    path(
        "schema/",
        SpectacularAPIView.as_view(
            # Keeps the schema view out of its own document.
            schema=None,
            authentication_classes=[ApiKeyAuthentication],
            permission_classes=[HasApiKey],
            renderer_classes=[OpenApiJsonRenderer],
            custom_settings={"TITLE": "Freedom Learning System API", "VERSION": "v1"},
        ),
        name="schema",
    ),
]
