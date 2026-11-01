from django.db.models import QuerySet
from rest_framework import serializers

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


class UserApiViewSet(ReadOnlyApiViewSet):
    required_scope = ApiScope.USERS
    serializer_class = UserApiSerializer

    def get_queryset(self) -> QuerySet[User]:
        # The base manager crosses sites; site_queryset narrows to the key's site.
        return self.site_queryset(annotate_email_verified(User._base_manager.all()))


router.register("users", UserApiViewSet, basename="user")
