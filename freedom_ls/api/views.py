from __future__ import annotations

from drf_spectacular.renderers import OpenApiJsonRenderer
from drf_spectacular.views import SpectacularAPIView

from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response

from .authentication import ApiKeyAuthentication
from .permissions import HasApiKey
from .viewsets import ApiResponseMixin


class ApiSchemaView(ApiResponseMixin, SpectacularAPIView):
    # Keeps the schema view out of its own document.
    schema = None
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiKey]
    renderer_classes = [OpenApiJsonRenderer]
    custom_settings = {"TITLE": "Freedom Learning System API", "VERSION": "v1"}

    def finalize_response(
        self, request: Request, response: Response, *args: object, **kwargs: object
    ) -> Response:
        # An error is not an OpenAPI document, so it renders like every other
        # API error rather than through the document's renderer.
        if response.exception:
            request.accepted_renderer = JSONRenderer()
            request.accepted_media_type = "application/json"
        return super().finalize_response(request, response, *args, **kwargs)
