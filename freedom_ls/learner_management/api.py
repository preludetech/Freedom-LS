from django.db.models import QuerySet
from rest_framework import serializers

from freedom_ls.accounts.api import user_fields
from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import LearnerCourseRegistration


def organisation_fields(
    source: str,
) -> tuple[serializers.UUIDField, serializers.CharField]:
    """The read-only organisation_id and organisation_name fields, in that
    order, read from the organisation at `source` ("learner.organisation").
    Unpacked under those names in a serializer body, as user_fields is.
    """
    return (
        serializers.UUIDField(source=f"{source}.id", read_only=True),
        serializers.CharField(source=f"{source}.name", read_only=True),
    )


class LearnerCourseRegistrationApiSerializer(serializers.ModelSerializer):
    # Declared with their types so the OpenAPI schema types them.
    course_id = serializers.UUIDField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    user_id, user_email, user_first_name, user_last_name = user_fields("learner.user")
    organisation_id, organisation_name = organisation_fields("learner.organisation")

    class Meta:
        model = LearnerCourseRegistration
        fields = (
            "id",
            "course_id",
            "course_title",
            "user_id",
            "user_email",
            "user_first_name",
            "user_last_name",
            "organisation_id",
            "organisation_name",
            "self_registered",
            "is_active",
            "registered_at",
            "updated_at",
        )
        read_only_fields = fields


class LearnerCourseRegistrationFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = LearnerCourseRegistration
        fields: list[str] = []


class LearnerCourseRegistrationApiViewSet(ReadOnlyApiViewSet):
    filterset_class = LearnerCourseRegistrationFilterSet
    required_scope = ApiScope.REGISTRATIONS_AND_PROGRESS
    serializer_class = LearnerCourseRegistrationApiSerializer

    def get_queryset(self) -> QuerySet[LearnerCourseRegistration]:
        # The base manager crosses sites; the base viewset's filter_queryset
        # narrows every lookup to the key's site.
        return LearnerCourseRegistration._base_manager.select_related(
            "course", "learner__user", "learner__organisation"
        )


router.register(
    "learner-course-registrations",
    LearnerCourseRegistrationApiViewSet,
    basename="learner_course_registration",
)
