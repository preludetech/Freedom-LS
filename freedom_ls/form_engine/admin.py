from unfold.contrib.filters.admin import RelatedDropdownFilter

from django.apps import apps
from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from freedom_ls.site_aware_models.admin import (
    ReadOnlyAdminMixin,
    ReadOnlyInline,
    SiteAwareModelAdmin,
    admin_change_link,
)
from freedom_ls.site_aware_models.admin_filters import (
    CompletionListFilter,
    InclusiveRangeDateTimeFilter,
)

from .models import (
    FormDeclaration,
    FormProgress,
    QuestionAnswer,
    QuestionAnswerFile,
)
from .permissions import can_download_answer_files
from .queries import answer_groups
from .typed_answers import format_answer


def _with_applicant_select_related(
    list_select_related: tuple[str, ...] | list[str], sitting_path: str
) -> list[str]:
    """The changelist's select_related, plus the sitting's applicant when the
    app that owns applications is installed.

    A string path, because that app sits above this one and may be absent.
    `sitting_path` is the lookup from the admin's model to the FormProgress,
    "" when the model is the sitting itself.
    """
    related = list(list_select_related)
    if apps.is_installed("freedom_ls.course_applications"):
        related.append(f"{sitting_path}course_application__anonymous_applicant")
    return related


def answers_context(
    request: HttpRequest, form_progress: FormProgress
) -> dict[str, object]:
    """What the answers document needs: the groups, and whether this reader may
    follow a file's download link."""
    return {
        "answer_groups": answer_groups(form_progress),
        "can_download_answer_files": can_download_answer_files(request.user),
    }


def applicant_label(form_progress: FormProgress) -> str:
    """Who sat this form: the user, or the unverified email its application holds.

    The application is reached only through its reverse accessor; the app that
    owns it sits above this one and may not be installed.
    """
    if form_progress.user is not None:
        return str(form_progress.user)
    # hasattr, because a missing reverse one-to-one raises rather than returning None.
    if not hasattr(form_progress, "course_application"):
        return "Unverified"
    applicant = form_progress.course_application.anonymous_applicant
    return "Unverified" if applicant is None else f"Unverified: {applicant.email}"


class FormProgressCompletionFilter(CompletionListFilter):
    completion_field = "completed_time"


class FormDeclarationInline(ReadOnlyInline):
    """Read-only display of the declaration signed for a sitting.

    The declaration has no admin of its own, so deleting a sitting or its user
    cascades to it without Django's permission check listing it.
    """

    model = FormDeclaration
    _DECLARATION_FIELDS = ("declaration_text", "typed_name", "signed_at", "ip_address")
    fields = _DECLARATION_FIELDS
    readonly_fields = _DECLARATION_FIELDS


@admin.register(FormProgress)
class FormProgressAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    inlines = [FormDeclarationInline]
    list_display = [
        "applicant",
        "form",
        "in_course",
        "start_time",
        "last_updated_time",
        "completed_time",
        "is_complete",
    ]
    list_filter = [
        FormProgressCompletionFilter,
        ("form", RelatedDropdownFilter),
        ("completed_time", InclusiveRangeDateTimeFilter),
        ("start_time", InclusiveRangeDateTimeFilter),
    ]
    # The range filters only narrow anything once they are applied.
    list_filter_submit = True
    date_hierarchy = "completed_time"
    search_fields = ("user__email", "form__title")
    ordering = ("-start_time",)
    # The user and the form render on every row. `course_attempt` is a reverse
    # one-to-one and only `in_course` reads it, so it is fetched for the
    # changelist and nowhere else.
    list_select_related = (
        "user",
        "form",
        "course_attempt__course_progress__course",
    )
    # completed_time is read-only because only FormProgress.complete() may finish an
    # attempt: it scores the attempt and sends form_attempt_completed, which is what
    # keeps CourseProgress.progress_percentage up to date. Stamping the field
    # directly would leave both stale.
    readonly_fields = (
        "start_time",
        "last_updated_time",
        "completed_time",
        "scores",
        "asked",
        "served_paper",
        "furthest_page",
    )
    change_form_template = "admin/form_engine/answers_change_form.html"

    def get_list_select_related(self, request: HttpRequest) -> list[str]:
        return _with_applicant_select_related(self.list_select_related, "")

    fieldsets = (
        (None, {"fields": ("user", "form")}),
        (
            "Progress",
            {
                "fields": (
                    "start_time",
                    "last_updated_time",
                    "completed_time",
                    "scores",
                    "asked",
                    "served_paper",
                    "furthest_page",
                )
            },
        ),
    )

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, object],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: FormProgress | None = None,
    ) -> HttpResponse:
        if obj is not None:
            context.update(answers_context(request, obj))
            # The application is reached only through its reverse accessor: the
            # app that owns it sits above this one and may not be installed, so
            # there is no model to import and no select_related path to name.
            # Two queries on a single change page is the price.
            if hasattr(obj, "course_application"):
                application = obj.course_application
                summary_rows: list[tuple[str, str | SafeString]] = [
                    (
                        "Application",
                        admin_change_link(
                            request,
                            application,
                            label=f"Application for {application.course.title}",
                        ),
                    )
                ]
                if obj.user is None and application.anonymous_applicant is not None:
                    summary_rows.insert(
                        0, ("Unverified email", application.anonymous_applicant.email)
                    )
                context["summary_rows"] = summary_rows
        response: HttpResponse = super().render_change_form(
            request, context, add, change, form_url, obj
        )
        return response

    @admin.display(description="Applicant", ordering="user__email")
    def applicant(self, obj: FormProgress) -> str:
        return applicant_label(obj)

    @admin.display(description="In course")
    def in_course(self, obj: FormProgress) -> str | None:
        """The course this attempt was sat inside, or None when it was not.

        A form can be sat outside any course, and the absence of the reverse
        one-to-one is exactly what records that -- so the empty-value dash here
        means "sat on its own", not "unknown".
        """
        if not hasattr(obj, "course_attempt"):
            return None
        return str(obj.course_attempt.course_progress.course)

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj):
        return obj.completed_time is not None


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    list_display = [
        "form_progress",
        "question",
        "answer_preview",
        "updated_at",
    ]
    list_filter = ("question__form_page__form", "updated_at")
    search_fields = (
        "form_progress__user__email",
        "question__question",
        "text_answer",
    )
    ordering = ("-updated_at",)
    readonly_fields = ("updated_at",)
    list_select_related = ("form_progress", "question")

    fieldsets = (
        (None, {"fields": ("form_progress", "question")}),
        ("Answer", {"fields": ("selected_options", "text_answer")}),
        ("Metadata", {"fields": ("updated_at",)}),
    )

    @admin.display(description="Answer")
    def answer_preview(self, obj):
        if obj.text_answer:
            return format_answer(obj.question.type, obj.text_answer)[:50]
        elif obj.selected_options.exists():
            options = ", ".join([opt.text for opt in obj.selected_options.all()])
            return options[:50]
        return "-"


@admin.register(QuestionAnswerFile)
class QuestionAnswerFileAdmin(ReadOnlyAdminMixin, SiteAwareModelAdmin):
    """The documents applicants attached.

    The file itself is reachable only through the permission-checked download
    route below, never from a link on the page.
    """

    list_display = [
        "applicant",
        "question",
        "original_filename",
        "created_at",
        "download",
    ]
    list_select_related = ["answer__form_progress__user", "answer__question"]
    list_filter = ["created_at"]

    def get_list_select_related(self, request: HttpRequest) -> list[str]:
        return _with_applicant_select_related(
            self.list_select_related, "answer__form_progress__"
        )

    readonly_fields = [
        "answer",
        "original_filename",
        "created_at",
        "updated_at",
    ]
    # `file` is excluded rather than read-only: rendering the field would put a
    # storage URL on the page, reachable without passing the download route's
    # permission check.
    exclude = ["site", "file"]

    @admin.display(description="Applicant", ordering="answer__form_progress__user")
    def applicant(self, obj: QuestionAnswerFile) -> str:
        return applicant_label(obj.answer.form_progress)

    @admin.display(description="Question", ordering="answer__question")
    def question(self, obj: QuestionAnswerFile) -> str:
        return obj.answer.question.question[:50]

    @admin.display(description="Download")
    def download(self, obj: QuestionAnswerFile) -> str:
        url = reverse(
            "admin:freedom_ls_form_engine_questionanswerfile_download", args=[obj.pk]
        )
        return format_html('<a href="{}">Download</a>', url)

    def get_urls(self) -> list[URLPattern]:
        from freedom_ls.form_engine.views import question_answer_file_download_view

        custom = [
            path(
                "<path:object_id>/download/",
                self.admin_site.admin_view(question_answer_file_download_view),
                name="freedom_ls_form_engine_questionanswerfile_download",
            )
        ]
        return custom + list(super().get_urls())
