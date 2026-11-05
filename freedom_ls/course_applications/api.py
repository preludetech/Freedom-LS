from drf_spectacular.utils import extend_schema_field

from django.db.models import QuerySet
from rest_framework import serializers

from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import CourseApplication


class CourseApplicationApiSerializer(serializers.ModelSerializer):
    # Properties, not columns: read through the model so they follow when
    # application review adds a state.
    applicant_email = serializers.CharField(read_only=True)
    applicant_name = serializers.CharField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    course_id = serializers.UUIDField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    is_submitted = serializers.BooleanField(read_only=True)
    # allow_null marks the OpenAPI schema nullable; a draft has no submitted_time.
    submitted_time = serializers.DateTimeField(read_only=True, allow_null=True)
    answers = serializers.SerializerMethodField()

    class Meta:
        model = CourseApplication
        # The explicit tuple is the whole contract: no anonymous-applicant
        # consent or claim field can leak because nothing reads that model
        # directly.
        fields = (
            "id",
            "applicant_email",
            "applicant_name",
            "is_email_verified",
            "course_id",
            "course_title",
            "is_submitted",
            "submitted_time",
            "created_at",
            "updated_at",
            "answers",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_answers(self, application: CourseApplication) -> list[dict[str, object]]:
        return []


class CourseApplicationFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = CourseApplication
        fields: list[str] = []


class CourseApplicationApiViewSet(ReadOnlyApiViewSet):
    filterset_class = CourseApplicationFilterSet
    required_scope = ApiScope.COURSE_APPLICATIONS
    serializer_class = CourseApplicationApiSerializer

    def get_queryset(self) -> QuerySet[CourseApplication]:
        # The base manager crosses sites; the base viewset's filter_queryset
        # narrows every lookup to the key's site.
        return CourseApplication._base_manager.select_related(
            "user", "anonymous_applicant", "course", "form_progress"
        )


router.register(
    "course-applications", CourseApplicationApiViewSet, basename="course_application"
)
