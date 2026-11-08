from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

from rest_framework import serializers

from freedom_ls.accounts.api import user_fields
from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import CourseProgress


class CourseProgressApiSerializer(serializers.ModelSerializer):
    course_id = serializers.UUIDField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    registration_id = serializers.SerializerMethodField()
    registration_kind = serializers.SerializerMethodField()
    user_id, user_email, user_first_name, user_last_name = user_fields("learner.user")
    organisation_id = serializers.UUIDField(
        source="learner.organisation.id", read_only=True
    )
    organisation_name = serializers.CharField(
        source="learner.organisation.name", read_only=True
    )

    class Meta:
        model = CourseProgress
        fields = (
            "id",
            "course_id",
            "course_title",
            "registration_id",
            "registration_kind",
            "user_id",
            "user_email",
            "user_first_name",
            "user_last_name",
            "organisation_id",
            "organisation_name",
            "progress_percentage",
            "started_at",
            "last_accessed_time",
            "completed_time",
            "updated_at",
        )
        read_only_fields = fields

    # Exactly one of the two registration foreign keys is set; the database
    # check constraint course_progress_has_exactly_one_grant keeps it so.
    @extend_schema_field(OpenApiTypes.UUID)
    def get_registration_id(self, record: CourseProgress) -> UUID | None:
        if record.learner_registration_id is not None:
            return record.learner_registration_id
        return record.cohort_registration_id

    @extend_schema_field({"type": "string", "enum": ["learner", "cohort"]})
    def get_registration_kind(self, record: CourseProgress) -> str:
        if record.learner_registration_id is not None:
            return "learner"
        return "cohort"


class CourseProgressFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = CourseProgress
        fields: list[str] = []


class CourseProgressApiViewSet(ReadOnlyApiViewSet):
    filterset_class = CourseProgressFilterSet
    required_scope = ApiScope.REGISTRATIONS_AND_PROGRESS
    serializer_class = CourseProgressApiSerializer

    # The base manager crosses sites; the base viewset's filter_queryset
    # narrows every lookup to the key's site. The two registrations and
    # last_accessed_item are not joined: the serializer reads only the
    # registration ids, and nothing here reads the item.
    queryset = CourseProgress._base_manager.select_related(
        "course", "learner__user", "learner__organisation"
    )


router.register("course-progress", CourseProgressApiViewSet, basename="course_progress")
