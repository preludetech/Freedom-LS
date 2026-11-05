from rest_framework import serializers

from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import User
from .resources import USER_EXPORT_FIELDS, annotate_email_verified


class UserApiSerializer(serializers.ModelSerializer):
    # An annotation, not a column.
    email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (*USER_EXPORT_FIELDS, "updated_at")
        read_only_fields = fields


class UserFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = User
        fields: list[str] = []


class UserApiViewSet(ReadOnlyApiViewSet):
    # The base manager crosses sites; the base viewset's filter_queryset
    # narrows every lookup to the key's site.
    queryset = annotate_email_verified(User._base_manager.all())
    filterset_class = UserFilterSet
    required_scope = ApiScope.USERS
    serializer_class = UserApiSerializer


router.register("users", UserApiViewSet, basename="user")
