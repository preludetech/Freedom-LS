from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import ApiKey
from .scopes import ApiScope


class HasApiScope(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        api_key = request.auth
        if not isinstance(api_key, ApiKey):
            return False
        scope: ApiScope = view.required_scope
        if scope in api_key.scopes:
            return True
        self.message = f"This API key does not have the {scope.value} API scope."
        return False
