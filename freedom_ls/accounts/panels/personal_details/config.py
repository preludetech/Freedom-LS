"""The Personal details section of the account area."""

from __future__ import annotations

from django.db.models import Model
from django.http import Http404, HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import get_own_user
from freedom_ls.panel_framework.views import ObjectViewConfig

from .actions import ACCOUNT_CAPABILITIES
from .instance_view import PersonalDetailsInstanceView


class PersonalDetailsConfig(ObjectViewConfig):
    url_name = "personal-details"
    menu_label = "Personal details"
    instance_view = PersonalDetailsInstanceView

    @classmethod
    def get_object(cls, request: HttpRequest) -> Model:
        return get_own_user(request)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        if instance.pk != request.user.pk:
            raise Http404

    @classmethod
    def has_capability(
        cls, request: HttpRequest, capability: str, scope: Model
    ) -> bool:
        return (
            capability in ACCOUNT_CAPABILITIES
            and isinstance(scope, User)
            and scope.pk == request.user.pk
        )

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        return "Personal details"
