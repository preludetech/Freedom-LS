from unfold.contrib.filters.admin import AutocompleteSelectFilter

from django.contrib import admin
from django.contrib.sites.models import Site
from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from freedom_ls.content_base.admin_filters import ContentTagListFilter
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from freedom_ls.site_aware_models.admin_filters import (
    CompletionListFilter,
    InclusiveRangeDateTimeFilter,
)
from freedom_ls.site_aware_models.models import get_cached_site
from freedom_ls.site_aware_models.slugs import get_unique_slug, slug_base_for

from .models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionAnswerFile,
    QuestionOption,
)
from .permissions import can_download_answer_files
from .queries import answer_groups
from .typed_answers import format_answer


class QuestionOptionInline(admin.TabularInline):
    """Inline for question options."""

    model = QuestionOption
    extra = 1
    fields = ("text", "value", "order")
    can_delete = False


@admin.register(QuestionOption)
class QuestionOptionAdmin(SiteAwareModelAdmin):
    list_display = ["text", "value", "question", "order"]
    list_filter = ("question__form_page__form",)
    search_fields = ("text", "question__question")
    ordering = ("question", "order")

    def has_delete_permission(
        self, request: HttpRequest, obj: QuestionOption | None = None
    ) -> bool:
        return False


class FormContentInline(admin.StackedInline):
    """Inline for form text items."""

    model = FormContent
    extra = 0
    fields = (
        "content",
        "order",
    )
    can_delete = False


class FormQuestionInline(admin.StackedInline):
    """Inline for form questions."""

    model = FormQuestion
    extra = 0
    fields = ("question", "type", "required", "category", "order")
    show_change_link = True
    can_delete = False


@admin.register(FormContent)
class FormContentAdmin(SiteAwareModelAdmin):
    list_display = [
        "content_preview",
        "form_page",
        "order",
    ]
    list_filter = ("form_page__form",)
    search_fields = ("content", "form_page__title")
    ordering = ("form_page", "order")

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:50]

    def has_delete_permission(
        self, request: HttpRequest, obj: FormContent | None = None
    ) -> bool:
        return False


@admin.register(FormQuestion)
class FormQuestionAdmin(SiteAwareModelAdmin):
    list_display = [
        "question_preview",
        "type",
        "required",
        "category",
        "form_page",
        "order",
    ]
    list_filter = ("type", "required", "category", "form_page__form")
    search_fields = ("question", "category", "form_page__title")
    ordering = ("form_page", "order")
    inlines = [QuestionOptionInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "question",
                    "type",
                    "required",
                    "form_page",
                    "category",
                    "order",
                )
            },
        ),
        (
            "Answer format",
            {
                "fields": ("min", "max", "decimal_places"),
                "description": (
                    "min and max apply to date, time and number questions only, "
                    "and are inclusive. decimal_places applies to number "
                    "questions; 0 is whole numbers only."
                ),
            },
        ),
        (
            "Metadata",
            {"fields": ("file_path", "meta", "tags"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Question")
    def question_preview(self, obj):
        return obj.question[:50]

    def has_delete_permission(
        self, request: HttpRequest, obj: FormQuestion | None = None
    ) -> bool:
        return False


class FormPageInline(admin.StackedInline):
    """Inline for form pages."""

    model = FormPage
    extra = 0
    fields = ("title", "subtitle", "description", "order")
    show_change_link = True
    can_delete = False


@admin.register(FormPage)
class FormPageAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "form", "order"]
    list_filter = ("form",)
    search_fields = ("title", "subtitle", "description", "form__title")
    ordering = ("form", "order")
    readonly_fields = ("slug",)
    inlines = [FormContentInline, FormQuestionInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "slug",
                    "form",
                    "category",
                    "order",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )

    def has_delete_permission(
        self, request: HttpRequest, obj: FormPage | None = None
    ) -> bool:
        return False


@admin.register(Form)
class FormAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "strategy"]
    list_filter = ("strategy", ContentTagListFilter)
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug",)
    inlines = [FormPageInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "content",
                    "strategy",
                    "slug",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )

    def has_delete_permission(
        self, request: HttpRequest, obj: Form | None = None
    ) -> bool:
        return False

    def save_model(
        self, request: HttpRequest, obj: Form, form: object, change: bool
    ) -> None:
        """Mint a slug for a form added through the admin.

        `slug` is read-only here, so nothing on the add form can supply one and
        a second form of the same title would collide without this.
        """
        if not obj.slug:
            # get_cached_site can return a RequestSite fallback, but only when
            # django.contrib.sites is uninstalled, which never happens here.
            site = get_cached_site(request)
            if isinstance(site, Site):
                obj.slug = get_unique_slug(
                    Form, site, slug_base_for(obj.title), existing_uuid=str(obj.pk)
                )
        super().save_model(request, obj, form, change)


def answers_context(
    request: HttpRequest, form_progress: FormProgress
) -> dict[str, object]:
    """What the answers document needs: the groups, and whether this reader may
    follow a file's download link."""
    return {
        "answer_groups": answer_groups(form_progress),
        "can_download_answer_files": can_download_answer_files(request.user),
    }


class FormProgressCompletionFilter(CompletionListFilter):
    completion_field = "completed_time"


@admin.register(FormProgress)
class FormProgressAdmin(SiteAwareModelAdmin):
    list_display = [
        "user",
        "form",
        "in_course",
        "start_time",
        "last_updated_time",
        "completed_time",
        "is_complete",
    ]
    list_filter = [
        FormProgressCompletionFilter,
        ("form", AutocompleteSelectFilter),
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
        "furthest_page_reached",
    )
    change_form_template = "admin/form_engine/answers_change_form.html"

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
                    "furthest_page_reached",
                )
            },
        ),
    )

    def get_readonly_fields(
        self, request: HttpRequest, obj: FormProgress | None = None
    ) -> list[str]:
        # The sitting is the record of what one person was asked; its owner and
        # form never change after the fact. The add page still needs both.
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly += ["user", "form"]
        return readonly

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
        response: HttpResponse = super().render_change_form(
            request, context, add, change, form_url, obj
        )
        return response

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
class QuestionAnswerAdmin(SiteAwareModelAdmin):
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
class QuestionAnswerFileAdmin(SiteAwareModelAdmin):
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

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @admin.display(description="Applicant", ordering="answer__form_progress__user")
    def applicant(self, obj: QuestionAnswerFile) -> str:
        return str(obj.answer.form_progress.user)

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
