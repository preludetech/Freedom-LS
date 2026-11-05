from drf_spectacular.utils import extend_schema_field

from django.db.models import Prefetch, QuerySet
from rest_framework import serializers

from freedom_ls.api.filters import UpdatedSinceFilterSet
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.exports import answer_value
from freedom_ls.form_engine.models import QuestionAnswer, QuestionOption

from .models import CourseApplication

# OpenAPI 3.0 reads nullable only beside a type, so each branch carries it.
ANSWER_VALUE_SCHEMA: dict[str, object] = {
    "oneOf": [
        {"type": "string", "nullable": True},
        {"type": "array", "items": {"type": "string"}, "nullable": True},
    ],
}


class QuestionAnswerApiSerializer(serializers.Serializer):
    question_id = serializers.UUIDField(read_only=True)
    question_text = serializers.CharField(source="question.question", read_only=True)
    question_type = serializers.ChoiceField(
        source="question.type", choices=QuestionType.choices, read_only=True
    )
    value = serializers.SerializerMethodField()

    @extend_schema_field(ANSWER_VALUE_SCHEMA)
    def get_value(self, answer: QuestionAnswer) -> str | list[str] | None:
        return answer_value(answer)


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

    @extend_schema_field(QuestionAnswerApiSerializer(many=True))
    def get_answers(self, application: CourseApplication) -> list[dict[str, object]]:
        if application.form_progress is None:
            return []
        # .all() reads the prefetched rows in their prefetched order.
        answers = application.form_progress.answers.all()
        return list(QuestionAnswerApiSerializer(answers, many=True).data)


def answers_prefetch() -> Prefetch:
    """The answers of a page of applications, complete whatever host the request is on.

    A related manager is built on the site-filtered default manager, so a
    string prefetch would drop another host's rows; the base managers do not.
    The Prefetch is a function because it holds a queryset, which is built per
    request rather than at import.
    """
    options = Prefetch("selected_options", queryset=QuestionOption._base_manager.all())
    answers = (
        QuestionAnswer._base_manager.select_related("question__form_page")
        .prefetch_related(options, "answer_file")
        .order_by("question__form_page__order", "question__order", "question_id")
    )
    return Prefetch("form_progress__answers", queryset=answers)


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
        ).prefetch_related(answers_prefetch())


router.register(
    "course-applications", CourseApplicationApiViewSet, basename="course_application"
)
