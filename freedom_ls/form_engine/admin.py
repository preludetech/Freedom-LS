from unfold.contrib.filters.admin import AutocompleteSelectFilter

from django.contrib import admin
from django.contrib.sites.models import Site
from django.http import HttpRequest
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


class SuperuserOnlyAdmin:
    """Restricts a whole admin class to superusers.

    An applicant's sitting, their answers and the documents they attached are
    their own words and papers. Rights over course content are not rights over
    those, and Django's per-model permissions cannot express the difference --
    so the gate is here rather than in a permission grant.
    """

    def has_view_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_superuser


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


class QuestionAnswerInline(admin.TabularInline):
    """Inline for question answers."""

    model = QuestionAnswer
    extra = 0
    fields = ("question", "selected_options", "text_answer", "updated_at")
    readonly_fields = ("updated_at",)


class FormProgressCompletionFilter(CompletionListFilter):
    completion_field = "completed_time"


@admin.register(FormProgress)
class FormProgressAdmin(SuperuserOnlyAdmin, SiteAwareModelAdmin):
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
    readonly_fields = ("start_time", "last_updated_time", "completed_time", "scores")
    inlines = [QuestionAnswerInline]

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
                )
            },
        ),
    )

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
class QuestionAnswerAdmin(SuperuserOnlyAdmin, SiteAwareModelAdmin):
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

    fieldsets = (
        (None, {"fields": ("form_progress", "question")}),
        ("Answer", {"fields": ("selected_options", "text_answer")}),
        ("Metadata", {"fields": ("updated_at",)}),
    )

    @admin.display(description="Answer")
    def answer_preview(self, obj):
        if obj.text_answer:
            return obj.text_answer[:50]
        elif obj.selected_options.exists():
            options = ", ".join([opt.text for opt in obj.selected_options.all()])
            return options[:50]
        return "-"


@admin.register(QuestionAnswerFile)
class QuestionAnswerFileAdmin(SuperuserOnlyAdmin, SiteAwareModelAdmin):
    """The reviewer's view of the documents applicants attached.

    The file itself is reachable only through the superuser-only download route
    below, never from a link on the page.
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
    # superuser check.
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
