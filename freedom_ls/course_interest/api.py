from django.db.models import QuerySet
from rest_framework import serializers

from freedom_ls.accounts.api import user_fields
from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import CourseInterest


class CourseInterestApiSerializer(serializers.ModelSerializer):
    # Declared with their types so the OpenAPI schema types them.
    course_id = serializers.UUIDField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    user_id, user_email, user_first_name, user_last_name = user_fields("user")

    class Meta:
        model = CourseInterest
        fields = (
            "id",
            "course_id",
            "course_title",
            "user_id",
            "user_email",
            "user_first_name",
            "user_last_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CourseInterestFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = CourseInterest
        fields: list[str] = []


class CourseInterestApiViewSet(ReadOnlyApiViewSet):
    filterset_class = CourseInterestFilterSet
    required_scope = ApiScope.REGISTRATIONS_AND_PROGRESS
    serializer_class = CourseInterestApiSerializer

    def get_queryset(self) -> QuerySet[CourseInterest]:
        # The base manager crosses sites; the base viewset's filter_queryset
        # narrows every lookup to the key's site.
        return CourseInterest._base_manager.select_related("course", "user")


router.register(
    "course-interests", CourseInterestApiViewSet, basename="course_interest"
)
