from drf_spectacular.authentication import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema


class ApiKeyAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "freedom_ls.api.authentication.ApiKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer"}
