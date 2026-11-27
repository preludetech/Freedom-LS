from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.core.validators import MinValueValidator
from django.db import connection, models, transaction
from django.utils import timezone
from django.utils.safestring import SafeString
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from freedom_ls.base.storage import storage_for_alias
from freedom_ls.content_base.models import (
    BaseContent,
    MarkdownContent,
    RetirableManager,
    TitledContent,
)
from freedom_ls.content_base.schema import ContentType as SchemaContentTypes
from freedom_ls.form_engine.config import config as form_engine_config
from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.site_aware_models.models import (
    SiteAwareManager,
    SiteAwareModel,
    TimestampedModel,
)

from .enums import (
    FREE_TEXT_QUESTION_TYPES,
    CompletionReason,
    FormStrategy,
    QuestionType,
)
from .live_tree import live_pages
from .phone_numbers import e164_phone_answer
from .scoring import is_quiz_answer_correct
from .signals import form_attempt_completed
from .submissions import (
    has_submitted_answer,
    submitted_option_ids,
    submitted_phone_country,
    submitted_text_answer,
)
from .typed_answers import RejectedAnswer, answer_error, question_bounds_error
from .units import shuffle_units, unit_question_counts

if TYPE_CHECKING:
    from django.http import QueryDict

    from .conditions import SittingPath

# Re-exported so `from freedom_ls.form_engine.models import FormStrategy` keeps
# resolving now that the enums live in their own module.
__all__ = [
    "FREE_TEXT_QUESTION_TYPES",
    "CompletionReason",
    "Form",
    "FormPage",
    "FormProgress",
    "FormQuestion",
    "FormStrategy",
    "QuestionAnswer",
    "QuestionAnswerFile",
    "QuestionOption",
    "QuestionType",
]


class Form(TitledContent, MarkdownContent):
    """Form content with scoring strategy."""

    CONTENT_TYPE = SchemaContentTypes.FORM

    strategy = models.CharField(
        max_length=50,
        choices=FormStrategy.choices,
    )

    quiz_show_incorrect = models.BooleanField(
        blank=True, null=True
    )  # Should we show the answers after the user finishes the form?

    quiz_pass_percentage = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text=_("Percentage (0-100) required to pass the quiz"),
    )

    time_limit_minutes = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=_(
            "Minutes a learner has to finish a quiz sitting, counted from when it "
            "starts. If empty (default), the quiz has no time limit."
        ),
    )

    submit_on_exit = models.BooleanField(
        default=False,
        help_text=_(
            "If True, leaving the test mid-attempt finalises and scores it. "
            "If False (default), the attempt is saved and can be resumed."
        ),
    )
    shuffle_pages = models.BooleanField(
        default=False,
        help_text=_(
            "If True, each sitting of a quiz serves the pages in a random order. "
            "If False (default), pages are served in authored order."
        ),
    )
    shuffle_questions = models.BooleanField(
        default=False,
        help_text=_(
            "If True, each sitting of a quiz serves each page's questions in a random order. "
            "If False (default), questions are served in authored order."
        ),
    )
    shuffle_options = models.BooleanField(
        default=False,
        help_text=_(
            "If True, each sitting of a quiz serves each question's options in a random order. "
            "If False (default), options are served in authored order."
        ),
    )
    requires_declaration = models.BooleanField(
        default=False,
        help_text=_(
            "If True, the learner signs a declaration before every attempt of a quiz. "
            "If False (default), the quiz starts without one."
        ),
    )
    declaration_text = models.TextField(
        blank=True,
        default="",
        help_text=_(
            "The declaration the learner signs. "
            "If empty (default), the site's default declaration text is used."
        ),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_form_slug_per_site"
            )
        ]

    def __str__(self):
        return self.title

    def effective_declaration_text(self) -> str:
        """The author's own declaration when set, else the site-wide default."""
        return self.declaration_text or form_engine_config.FORM_DECLARATION_DEFAULT_TEXT


class FormPage(TitledContent):
    """A page within a form."""

    CONTENT_TYPE = SchemaContentTypes.FORM_PAGE

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="pages")
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=200, blank=True, default="")
    # RESTRICT, not PROTECT: an option deleted on its own would leave a gate
    # that can never open, but deleting the whole form collects the gated rows
    # alongside the option and goes through.
    condition_option = models.ForeignKey(
        "QuestionOption",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="gated_pages",
    )
    draw = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text=_(
            "If set, each sitting of a quiz serves this many of the page's questions or "
            "groups, drawn at random. If empty (default), every one is served."
        ),
    )

    def children(self):
        """
        return an ordered list of FormContent and FormQuestion instances
        """
        text_items = list(self.text_items.all())
        questions = list(self.questions.all())

        # Combine and sort by order field
        all_children = text_items + questions
        all_children.sort(key=lambda item: item.order)

        return all_children

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.form.title} - {self.title}"


class FormContent(MarkdownContent):
    """Text content within a form page."""

    CONTENT_TYPE = SchemaContentTypes.FORM_CONTENT

    content = models.TextField()
    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="text_items"
    )
    order = models.PositiveIntegerField(default=0)
    group = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "Keep-together group: children of one page sharing this name stay "
            "together, in authored order, when the page's questions shuffle."
        ),
    )
    # RESTRICT, not PROTECT: an option deleted on its own would leave a gate
    # that can never open, but deleting the whole form collects the gated rows
    # alongside the option and goes through.
    condition_option = models.ForeignKey(
        "QuestionOption",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="gated_content",
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.content[:50]

    def clean(self) -> None:
        error = drawing_page_unit_error(self)
        if error is not None:
            raise ValidationError(error)


class FormQuestion(BaseContent):
    """A question within a form page."""

    CONTENT_TYPE = SchemaContentTypes.FORM_QUESTION

    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=200, blank=True, default="")
    group = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "Keep-together group: children of one page sharing this name stay "
            "together, in authored order, when the page's questions shuffle."
        ),
    )
    slug = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "The author's reference name for this question, unique within its form"
        ),
    )
    # RESTRICT, not PROTECT: an option deleted on its own would leave a gate
    # that can never open, but deleting the whole form collects the gated rows
    # alongside the option and goes through.
    condition_option = models.ForeignKey(
        "QuestionOption",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="gated_questions",
    )

    # Set by the content loader when the question's file no longer holds it. The
    # row stays because quiz answers protect it.
    dropped_from_source_at = models.DateTimeField(null=True, blank=True)

    question = models.TextField()
    explanation = models.TextField(
        blank=True,
        default="",
        help_text=_(
            "Markdown shown after the question is answered in revision: why the "
            "correct answer is correct."
        ),
    )
    type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    required = models.BooleanField(default=True)
    # Holds an ISO date, an HH:MM time, or a plain number depending on
    # `type`, and renders straight into the matching HTML attribute. Both
    # bounds are inclusive, matching what the HTML attributes themselves mean.
    min = models.CharField(max_length=20, blank=True, default="")
    max = models.CharField(max_length=20, blank=True, default="")
    # How many decimal places a `number` answer may be written to. 0 is whole
    # numbers only, which is what `<input type="number">` enforces on its own
    # with its default `step` of 1.
    decimal_places = models.PositiveSmallIntegerField(default=0)

    def clean(self) -> None:
        """Refuse a bound the page could only render as an inert attribute, or
        an edit that leaves a drawing page's units uneven.

        The pydantic schema runs this same rule over authored YAML, but nothing
        ran it over a question edited by hand -- so `max = "31/12/2010"` saved
        silently and then did nothing at all, in the browser or on the server.
        """
        error = question_bounds_error(
            self.type, self.min, self.max, self.decimal_places
        ) or drawing_page_unit_error(self)
        if error is not None:
            raise ValidationError(error)

    @property
    def number_step(self) -> str:
        """The `step` attribute for this question's input, or "" for no step.

        Without it the browser's default step of 1 would refuse the very
        decimals `decimal_places` was set to allow.
        """
        if self.type != QuestionType.NUMBER:
            return ""
        if self.decimal_places == 0:
            return "1"
        return f"0.{'0' * (self.decimal_places - 1)}1"

    def rendered_question(self):
        # No request: cotton components embedded in question markdown render
        # without request context, so none of them may depend on it.
        return render_markdown(self.question, None)

    def rendered_explanation(self) -> SafeString:
        # No request, for the reason rendered_question gives.
        return render_markdown(self.explanation, None)

    def question_number(self) -> int | None:
        """
        Return 1 for the first question in the Form, 2 for the second etc. Note that this might not be the same as the order attribute because form pages contain more than just questions.
        A live question is numbered among the live ones, retired questions and pages
        not counted, matching what a new sitting is served. A retired question,
        still shown to a sitting served it and in the educator preview, is
        numbered among every question the form holds, so it always has a number.
        """
        form = self.form_page.form
        # A question on a retired page is no more served than a retired one.
        whole_tree = self.is_retired or self.form_page.is_retired
        pages = list(form.pages.all()) if whole_tree else live_pages(form)
        question_count = 0

        # Iterate through all pages in order
        for page in pages:
            # Get all questions on this page in order
            for question in page.questions.all():
                if question.is_retired and not whole_tree:
                    continue
                question_count += 1
                if question.pk == self.pk:
                    return question_count

        return None

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.question[:50]


def drawing_page_unit_error(edited: FormContent | FormQuestion) -> str | None:
    """Why saving this child would break its drawing page, or None.

    A sitting draws whole units, so the count a learner is told up front only
    holds while every unit carries the same number of questions. The content
    validator checks authored files; this checks a child edited by hand. The
    page is laid out as it would be after the save: the stored row is swapped
    for the edited one, then children are re-sorted by order.
    """
    if not edited.form_page_id:
        return None
    page = edited.form_page
    if page.draw is None:
        return None
    children = [
        child
        for child in page.children()
        if not (type(child) is type(edited) and child.pk == edited.pk)
    ]
    children.append(edited)
    children.sort(key=lambda child: child.order)
    counts = unit_question_counts(
        shuffle_units(children), lambda child: isinstance(child, FormQuestion)
    )
    if 0 in counts:
        return gettext(
            "Every content block on a drawing page must share a group with a "
            "question it introduces."
        )
    if len(set(counts)) > 1:
        return gettext(
            "Every question or group on a drawing page must hold the same number "
            "of questions, so each sitting is worth the same."
        )
    return None


class QuestionOption(SiteAwareModel, TimestampedModel):
    """An option for a form question."""

    question = models.ForeignKey(
        FormQuestion, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=500)
    value = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    correct = models.BooleanField(null=True, blank=True)
    locked = models.BooleanField(default=False)

    retired_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When a content save found this row missing from the source"),
    )

    objects = RetirableManager()

    class Meta:
        ordering = ["order"]

    @property
    def is_retired(self) -> bool:
        return self.retired_at is not None

    def __str__(self):
        return self.text


class QuestionVersionOption(BaseModel):
    """One option as a version holds it."""

    model_config = ConfigDict(extra="forbid")
    id: str
    text: str
    value: str
    order: int
    correct: bool | None


def version_options(options: Iterable[QuestionOption]) -> list[dict[str, object]]:
    """The options as a version stores them: ordered by order then id, validated."""
    rows = sorted(options, key=lambda o: (o.order, str(o.id)))
    return [
        QuestionVersionOption(
            id=str(o.id),
            text=o.text,
            value=str(o.value),
            order=o.order,
            correct=o.correct,
        ).model_dump()
        for o in rows
    ]


_IMMUTABLE_MESSAGE = "FormQuestionVersion is immutable: a saved version cannot change"


class FormQuestionVersionQuerySet(models.QuerySet["FormQuestionVersion"]):
    """Every call that would change or remove a stored version raises."""

    def update(self, **kwargs: object) -> int:
        raise ValueError(_IMMUTABLE_MESSAGE)

    def bulk_update(self, *args: object, **kwargs: object) -> int:
        raise ValueError(_IMMUTABLE_MESSAGE)

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValueError(_IMMUTABLE_MESSAGE)


class FormQuestionVersion(SiteAwareModel):
    """An immutable snapshot of a question's wording, settings and options."""

    question = models.ForeignKey(
        FormQuestion, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()
    question_text = models.TextField()
    explanation = models.TextField(blank=True, default="")
    type = models.CharField(max_length=20, choices=QuestionType.choices)
    required = models.BooleanField(default=True)
    min = models.CharField(max_length=20, blank=True, default="")
    max = models.CharField(max_length=20, blank=True, default="")
    decimal_places = models.PositiveSmallIntegerField(default=0)
    options = models.JSONField(default=list)
    saved_at = models.DateTimeField(auto_now_add=True)
    source_commit = models.CharField(max_length=64, blank=True)
    from_migration = models.BooleanField(default=False)

    objects = SiteAwareManager.from_queryset(FormQuestionVersionQuerySet)()
    # Serves related lookups such as answer.question_version, which must not
    # depend on the site of the request that makes them.
    unfiltered = models.Manager.from_queryset(FormQuestionVersionQuerySet)()

    class Meta:
        base_manager_name = "unfiltered"
        ordering = ["question", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "number"], name="one_number_per_question_version"
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        # The UUID pk is set before the first save, so `_state.adding` is what
        # tells a first save from a later one.
        if self._state.adding is False:
            raise ValueError(_IMMUTABLE_MESSAGE)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValueError(_IMMUTABLE_MESSAGE)

    def option_rows(self) -> list[QuestionVersionOption]:
        """The stored options, validated on read."""
        return [QuestionVersionOption.model_validate(row) for row in self.options]

    def differs_from(
        self, question: FormQuestion, options: Sequence[QuestionOption]
    ) -> list[str]:
        """The names of the versioned parts that differ from the question as it
        stands, in a fixed order. Empty when the question matches this version."""
        compared = [
            ("question", self.question_text, question.question),
            ("type", self.type, question.type),
            ("required", self.required, question.required),
            ("min", self.min, question.min),
            ("max", self.max, question.max),
            ("decimal_places", self.decimal_places, question.decimal_places),
            ("explanation", self.explanation, question.explanation),
            ("options", self.options, version_options(options)),
        ]
        return [name for name, held, current in compared if held != current]

    def __str__(self) -> str:
        return f"{self.question_id} v{self.number}"


@dataclass(frozen=True)
class SavedQuestionVersion:
    version: FormQuestionVersion | None  # None when nothing differed
    previous_number: int | None
    changed: list[str]


def save_question_version(
    question: FormQuestion, options: Sequence[QuestionOption], source_commit: str
) -> SavedQuestionVersion:
    """Save a new version of the question when it differs from its latest one."""
    with transaction.atomic():
        # Locks the live row so two saves of one question cannot take the same number.
        FormQuestion._base_manager.select_for_update().get(pk=question.pk)
        latest = (
            FormQuestionVersion.unfiltered.filter(question_id=question.pk)
            .order_by("-number")
            .first()
        )
        changed = latest.differs_from(question, options) if latest else []
        if latest is not None and not changed:
            return SavedQuestionVersion(None, latest.number, [])
        version = FormQuestionVersion.objects.create(
            site_id=question.site_id,
            question=question,
            number=latest.number + 1 if latest else 1,
            question_text=question.question,
            type=question.type,
            required=question.required,
            min=question.min,
            max=question.max,
            decimal_places=question.decimal_places,
            explanation=question.explanation,
            options=version_options(options),
            source_commit=source_commit,
        )
        return SavedQuestionVersion(version, latest.number if latest else None, changed)


def delete_question_versions(questions: Iterable[FormQuestion]) -> None:
    """Remove every version of these questions. For development commands only; callers
    delete the answers pinned to the versions first, or the PROTECT foreign key refuses."""
    ids = [str(question.pk) for question in questions]
    if not ids:
        return
    table = connection.ops.quote_name(FormQuestionVersion._meta.db_table)
    with transaction.atomic(), connection.cursor() as cursor:
        # The queryset guard refuses an ORM delete.
        # The table name is quoted from the model's own db_table and the ids are a
        # bound parameter, so nothing user-supplied reaches the SQL string.
        cursor.execute(
            f"DELETE FROM {table} WHERE question_id = ANY(%s::uuid[])",  # noqa: S608  # nosec B608
            [ids],
        )


User = get_user_model()


def _offered_options(
    question: FormQuestion, served: SittingPath | None
) -> list[QuestionOption]:
    """The options a sitting was offered for the question: the served paper's when it
    has one, every option the question has, retired ones included, when it does not.

    Only a quiz sitting completed before served papers existed has none, and it
    was offered the whole question, so its stored history is never re-marked
    against what is live today."""
    if served is not None:
        return served.options_of(question)
    return list(question.options.all())


def marking_options(
    question: FormQuestion, served: SittingPath | None
) -> list[QuestionOption]:
    """The options a stored score is checked against: those the sitting was
    offered, plus any live option added since, so a correct option added after
    submission shows the stored score as outdated."""
    offered = _offered_options(question, served)
    offered_ids = {option.id for option in offered}
    added = [
        option
        for option in question.options.all()
        if option.id not in offered_ids and not option.is_retired
    ]
    return [*offered, *added]


# A time-up post is honoured from this long before the sitting expiry: the
# countdown works from a remaining time floored to whole seconds, so its zero
# can land just ahead of the server's.
TIME_UP_LEAD = timedelta(seconds=5)
# A page post still saves this long after the sitting expiry, to cover the
# network round trip of a post sent at zero.
EXPIRY_GRACE = timedelta(seconds=10)


class FormProgress(SiteAwareModel):
    """Tracks a learner's progress through a form.

    A sitting with no user is an anonymous visitor's. form_engine does not know
    what that visitor is doing; the app above it does.
    """

    # PROTECT: an attempt is the audit record of a sitting, so deleting the form
    # out from under it would erase what was answered.
    form = models.ForeignKey(
        Form, on_delete=models.PROTECT, related_name="progress_records"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="form_progress",
        null=True,
        blank=True,
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_updated_time = models.DateTimeField(auto_now=True)
    completed_time = models.DateTimeField(blank=True, null=True)
    scores = models.JSONField(
        blank=True, null=True, help_text="Calculated scores by category"
    )
    # A page with only optional questions leaves no answer rows behind, so the
    # answers alone cannot say how far a sitting got. The page itself, not its
    # number: an author adding or removing a page renumbers the ones after it.
    # Null until a page is shown, and again if that page is deleted.
    furthest_page = models.ForeignKey(
        "FormPage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=_("The page furthest along this sitting has been shown"),
    )
    completion_reason = models.CharField(
        max_length=20,
        choices=CompletionReason.choices,
        default=CompletionReason.LEARNER_SUBMITTED,
        help_text=_("Why this sitting was completed"),
    )
    time_limit_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("The quiz time limit in force when this sitting completed"),
    )
    asked = models.JSONField(
        null=True,
        blank=True,
        help_text=_(
            "The pages, questions and content this sitting was asked, "
            "recorded when it completed"
        ),
    )
    served_paper = models.JSONField(
        null=True,
        blank=True,
        help_text=_(
            "The pages, children and option order this sitting was served. "
            "Written once, before the first page is shown."
        ),
    )

    class Meta:
        verbose_name_plural = "Form progress records"

    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.form.title}"

    def quiz_percentage(self) -> int:
        if self.form.strategy != FormStrategy.QUIZ:
            raise ValueError("This method should only work for quiz models")
        if not self.scores:
            raise ValueError("Need to score the quiz before calling this method")
        # An attempt whose scores were written under another strategy — a form
        # switched to QUIZ after it was sat, or a row written by hand — carries
        # no quiz score to read. ValueError, not the natural KeyError, because
        # that is what every caller's guard already catches.
        if "score" not in self.scores or "max_score" not in self.scores:
            raise ValueError("This attempt was not scored as a quiz")

        score: int = self.scores["score"]
        max_score: int = self.scores["max_score"]
        # A quiz whose questions were added after a learner sat it scores
        # max_score 0. ValueError, not the natural ZeroDivisionError, because
        # that is what every caller's guard already catches.
        if not max_score:
            raise ValueError("A quiz with no questions has no percentage to report")

        return round((score / max_score) * 100)

    def passed(self) -> bool:
        if self.form.quiz_pass_percentage is None:
            raise ValueError(
                f"Quiz '{self.form.title}' (ID: {self.form.id}) does not have a pass percentage configured. "
                "Set quiz_pass_percentage on the Form to use this method."
            )
        return self.quiz_percentage() >= self.form.quiz_pass_percentage

    def record_page_reached(self, page_number: int, path: SittingPath) -> None:
        """Remember that this sitting has been shown `page_number`.

        Only ever moves forward along the path: stepping back to an earlier
        page does not forget the later one.
        """
        if path.reached_position(page_number) <= path.reached_position(
            self.furthest_page_number(path)
        ):
            return
        self.furthest_page = path.all_pages[page_number - 1]
        self.save(update_fields=["furthest_page", "last_updated_time"])

    def furthest_page_number(self, path: SittingPath) -> int:
        """The authored number the furthest page shown has now; 0 when no page
        has been shown or the form no longer has that page."""
        return path.page_number_of(self.furthest_page_id) or 0

    def get_current_page_number(
        self, path: SittingPath, answered_ids: set[UUID]
    ) -> int:
        """The first on-path page with an on-path question that has no answer,
        else the last on-path page (1 when the form has no pages)."""
        for number, page in path.numbered_pages():
            if any(q.id not in answered_ids for q in path.questions_of(page)):
                return number
        return path.last_page_number() or 1

    def existing_answers_dict(self, questions):
        """
        Get a dictionary of existing answers for the given questions.
        Returns a dict with question.id as keys and QuestionAnswer objects as values.

        Reads the whole answer set once and filters in Python, so a caller that
        has already prefetched `answers` -- the check-your-answers page does --
        pays no query at all.
        """
        wanted_ids = {question.id for question in questions}
        return {
            answer.question_id: answer
            for answer in self.answers.all()
            if answer.question_id in wanted_ids
        }

    def save_answers(
        self, questions: Iterable[FormQuestion], post_data: QueryDict
    ) -> dict[UUID, RejectedAnswer]:
        """Persist the answers in `post_data` for `questions`.

        A question submitted with no answer stores no row, and loses any row from
        an earlier visit: a blank row would count toward the runner's answered
        tally and hide which questions are still outstanding.

        An answer whose content is not valid for the question's type is neither
        written nor deleted: the row from an earlier visit, if there is one, is
        left exactly as it was. Storing it would leave a rejected value counting
        as an answer, which would satisfy the required-question check and let an
        application through. It comes back in the return value instead, keyed by
        question id, so the page that re-renders can show the person what they
        typed.
        """
        rejected: dict[UUID, RejectedAnswer] = {}
        for question in questions:
            if question.type == QuestionType.FILE_UPLOAD:
                # A file never rides the page POST, so a page submission carries
                # nothing for a file question. Treating that as "removed" would
                # throw away the row holding the file.
                continue

            if not has_submitted_answer(question, post_data):
                self.answers.filter(question=question).delete()
                continue

            text: str | None = None
            if question.type in FREE_TEXT_QUESTION_TYPES:
                text = submitted_text_answer(question, post_data)
                # "" for every type but phone, which is the only one that posts a country.
                country = submitted_phone_country(question, post_data)
                message = answer_error(question, text, country)
                if message is not None:
                    rejected[question.id] = RejectedAnswer(
                        text=text, message=message, country=country
                    )
                    continue
                if question.type == QuestionType.PHONE:
                    text = e164_phone_answer(text, country)

            answer, _created = QuestionAnswer.objects.get_or_create(
                form_progress=self, question=question, site=self.site
            )
            if text is not None:
                answer.text_answer = text
            else:
                answer.selected_options.set(submitted_option_ids(question, post_data))
            answer.save()
        return rejected

    def expires_at(self) -> datetime | None:
        """When the quiz time limit runs out for this sitting, by the form's
        limit as it is now, so a changed limit moves an open sitting's expiry
        and a removed one makes it untimed."""
        limit = self.form.time_limit_minutes
        return None if limit is None else self.start_time + timedelta(minutes=limit)

    def _open_expiry(self) -> datetime | None:
        """The sitting expiry of an open, timed sitting; None for any other."""
        return None if self.completed_time else self.expires_at()

    def is_expired(self, now: datetime) -> bool:
        expiry = self._open_expiry()
        # Strict, as closing instants are elsewhere: the expiry itself is still in time.
        return expiry is not None and now > expiry

    def in_grace(self, now: datetime) -> bool:
        """Whether a page post arriving now still saves, though the sitting has expired."""
        expiry = self._open_expiry()
        return expiry is not None and expiry < now <= expiry + EXPIRY_GRACE

    def accepts_time_up(self, now: datetime) -> bool:
        """Whether a time-up post arriving now is believed: from just before the
        expiry, to cover the countdown's rounding, to the end of the grace window."""
        expiry = self._open_expiry()
        return (
            expiry is not None and expiry - TIME_UP_LEAD <= now <= expiry + EXPIRY_GRACE
        )

    def complete(
        self,
        reason: CompletionReason = CompletionReason.LEARNER_SUBMITTED,
        *,
        time_up_lead: timedelta = timedelta(0),
    ) -> None:
        """Finish the sitting: keep only the answers it was asked, record what it
        was asked, score it, record why it ended, then tell the apps above.

        Idempotent and safe under concurrency: the first completion wins and a
        later one changes nothing and sends no signal.

        A `time_expired` completion is refused, and the sitting stays open, unless
        its time has run out by the form's limit as it is now. `time_up_lead` is
        how far ahead of the expiry a time-up post is still believed.
        """
        # Local import: conditions imports this module.
        from .conditions import current_path
        from .served_paper import ensure_served_paper

        with transaction.atomic():
            # Callers hold copies read before another request may have completed the
            # sitting, and save() writes every field, so work from the locked row.
            # _base_manager, because a sweep completes sittings with no request site.
            # Reloading also drops the cached form, so the limit read below is current.
            self.refresh_from_db(
                from_queryset=FormProgress._base_manager.select_for_update(of=("self",))
            )
            if self.completed_time:
                return
            now = timezone.now()
            expiry = self.expires_at()
            if reason == CompletionReason.LEARNER_SUBMITTED and self.is_expired(now):
                # A manual submit that lost the race to the clock.
                reason = CompletionReason.TIME_EXPIRED
            if reason == CompletionReason.TIME_EXPIRED and (
                expiry is None or now < expiry - time_up_lead
            ):
                # The caller judged a copy read before the lock. The limit has
                # since been removed or raised, so the sitting stays open.
                return
            ensure_served_paper(self)
            path = current_path(self)
            # Only this form's own off-path questions: an answer whose question
            # has since moved to another form is still an answer, and the admin
            # and the export list it. Deleting cascades to any attached file
            # row; its receiver removes the stored object only once this block
            # commits.
            self.answers.filter(question__form_page__form_id=self.form_id).exclude(
                question_id__in=path.question_ids
            ).delete()
            self.asked = path.as_asked()
            # The expiry instant, not now, when the sitting lapsed earlier: a late
            # request or sweep must not read as overtime. Never a future time.
            self.completed_time = (
                min(expiry, now)
                if reason == CompletionReason.TIME_EXPIRED and expiry is not None
                else now
            )
            self.completion_reason = reason
            self.time_limit_minutes = self.form.time_limit_minutes
            self.score(path)
            self.save()
        # Sent once the block has committed or released its savepoint, not through
        # on_commit: the receivers that update course progress and webhooks read
        # the row this block wrote.
        form_attempt_completed.send(
            sender=type(self), user=self.user, form=self.form, attempt=self
        )

    def complete_if_expired(self, now: datetime) -> bool:
        """Complete the sitting as time-expired if its time has run out, saving
        nothing posted. True when the sitting is now completed for that reason."""
        if not self.is_expired(now):
            return False
        self.complete(CompletionReason.TIME_EXPIRED)
        return (
            self.completed_time is not None
            and self.completion_reason == CompletionReason.TIME_EXPIRED
        )

    def score_category_value_sum(self, path: SittingPath) -> None:
        """
        Use the CATEGORY_VALUE_SUM scoring strategy:

        Each form page can have a category. This is the parent category
        Each question has a category. This is the child category

        Each question answer has a numerical value
        """
        # Note this only works with multiple_choice questions for now

        # 1. Get all questions from the form and create a data structure
        answer_data = []

        # Only the questions the sitting was asked count toward its scores.
        for page in path.pages:
            for question in path.questions_of(page):
                # multiple_choice and dropdown both carry QuestionOption rows
                # with a numeric value; every other type has no value to sum.
                if question.type not in ("multiple_choice", "dropdown"):
                    continue

                # Get the maximum value among all options for this question
                max_value = 0
                for option in path.options_of(question):
                    try:
                        opt_value = int(option.value)
                        if opt_value > max_value:
                            max_value = opt_value
                    except (ValueError, TypeError):
                        continue

                # Check if this question has been answered
                value = 0  # Default to 0 if not answered
                try:
                    answer = self.answers.get(question=question)
                    selected_options = answer.selected_options.all()
                    if selected_options.exists():
                        selected_option = selected_options.first()
                        if selected_option is not None:
                            value = int(selected_option.value)
                except (QuestionAnswer.DoesNotExist, ValueError, TypeError):
                    # Question not answered or invalid value, keep value as 0
                    pass

                # Get categories
                page_category = page.category
                question_category = question.category

                answer_data.append(
                    {
                        "page_category": page_category,
                        "question_category": question_category,
                        "value": value,
                        "max_value": max_value,
                    }
                )

        # 2. Calculate the final scores for each category and subcategory
        scores: dict[str, dict] = {}

        def parse_categories(page_category, question_category):
            """Parse category strings into a list of category levels."""
            categories = []

            # Parse page category (may have pipe separators for nested levels)
            if page_category:
                # Split on | and strip whitespace from each part
                page_cats = [c.strip() for c in page_category.split("|")]
                categories.extend(page_cats)

            # Add question category as the final level if it exists
            if question_category:
                categories.append(question_category)

            # Return at least "Uncategorized" if no categories
            return categories if categories else ["Uncategorized"]

        def add_score_to_nested_categories(scores_dict, categories, value, max_value):
            """Recursively add score and max_score to nested category structure."""
            if not categories:
                return

            # Get the top-level category for this recursion level
            top_cat = categories[0]

            # Initialize if doesn't exist
            if top_cat not in scores_dict:
                scores_dict[top_cat] = {
                    "score": 0,
                    "max_score": 0,
                    "sub_categories": {},
                }

            # Add to this level
            scores_dict[top_cat]["score"] += value
            scores_dict[top_cat]["max_score"] += max_value

            # Recursively handle remaining categories (if any)
            if len(categories) > 1:
                add_score_to_nested_categories(
                    scores_dict[top_cat]["sub_categories"],
                    categories[1:],
                    value,
                    max_value,
                )

        for item in answer_data:
            page_cat = item["page_category"]
            question_cat = item["question_category"]

            # Parse categories into hierarchical levels
            categories = parse_categories(page_cat, question_cat)

            # Add scores to the nested structure
            add_score_to_nested_categories(
                scores, categories, item["value"], item["max_value"]
            )

        # 3. Save to JSON field
        self.scores = scores
        self.save()

    def _served_path(self, path: SittingPath | None) -> SittingPath | None:
        """The sitting's path when it has a served paper, built only when not given; else None."""
        if self.served_paper is None:
            return None
        if path is None:
            # Local import: conditions imports this module.
            from .conditions import sitting_path

            path = sitting_path(self)
        return path

    def _quiz_questions(self, path: SittingPath | None) -> list[FormQuestion]:
        """The questions this quiz sitting is marked on.

        A sitting with a served paper is marked on the questions it was served.
        One without, a quiz sitting completed before served papers existed, is
        marked on every question the form has, retired ones included.
        """
        served = self._served_path(path)
        if served is None:
            return [
                child
                for page in self.form.pages.all()
                for child in page.children()
                if isinstance(child, FormQuestion)
            ]
        return served.questions()

    def compute_quiz_scores(
        self,
        path: SittingPath | None = None,
        answers: Mapping[UUID, QuestionAnswer] | None = None,
    ) -> dict[str, int]:
        """Score this attempt against the current marking rules, storing nothing.

        Scores are frozen at submission and never rescored, so a stored score can
        disagree with what the same answers would earn today. The results page
        re-derives a score to detect that, which it can only do without writing.

        `path` is read only when the sitting has a served paper; pass one the
        caller already built to save rebuilding it. `answers` maps question id to
        the sitting's answer with selected options loaded; it is read once when
        not given.
        """
        if answers is None:
            # Local import: conditions imports this module.
            from .conditions import answers_by_question

            answers = answers_by_question(self)

        score = 0
        max_score = 0

        served = self._served_path(path)
        for question in self._quiz_questions(served):
            max_score += 1

            # A question with no answer contributes 0 to the score.
            answer = answers.get(question.id)
            if answer is None:
                continue
            selected_option_ids = {o.id for o in answer.selected_options.all()}
            if is_quiz_answer_correct(
                selected_option_ids, marking_options(question, served)
            ):
                score += 1

        return {"score": score, "max_score": max_score}

    def score_quiz(self, path: SittingPath | None = None) -> None:
        """
        Calculate quiz score by counting correct answers.

        `path` is read only when the sitting has a served paper; pass one the
        caller already built to save rebuilding it.
        """
        self.scores = self.compute_quiz_scores(path)
        self.save()

    def score(self, path: SittingPath) -> None:
        """calculate the final score for the form"""
        if self.form.strategy == FormStrategy.CATEGORY_VALUE_SUM:
            self.score_category_value_sum(path)
        elif self.form.strategy == FormStrategy.QUIZ:
            self.score_quiz(path)
        elif self.form.strategy == FormStrategy.UNSCORED:
            # An unscored form awards no marks at all, so there is nothing to
            # write. Completing one still stamps completed_time.
            return

        else:
            raise Exception(f"Unhandled Strategy: {self.form.strategy}")

    def get_incorrect_quiz_answers(self, path: SittingPath | None = None) -> list[dict]:
        """
        Get a list of incorrect answers for a completed quiz.

        Returns a list of dicts with:
        - question: FormQuestion instance
        - number: the question number the learner was shown
        - learner_selected: list of QuestionOption instances the learner selected
        - correct_options: list of QuestionOption instances that are correct

        Only returns results if:
        - form.strategy is QUIZ

        `path` is read only when the sitting has a served paper; pass one the
        caller already built to save rebuilding it.

        We will use this function in multiple places. Sometimes we'll want to show the incorrect answers to the teacher. Even if we dont want to show the answers to the learner, this function should work
        """
        incorrect_answers: list[dict] = []

        if self.form.strategy != FormStrategy.QUIZ:
            return incorrect_answers

        served = self._served_path(path)
        questions = self._quiz_questions(served)
        # A sitting with no served paper was given every question, retired ones
        # included, so it is numbered among all of them, in authored order.
        positions = (
            served.question_positions()
            if served is not None
            else {question.id: n for n, question in enumerate(questions, start=1)}
        )

        for question in questions:
            # A free-text question has no options, so there is nothing to
            # show as either the selected or the correct answer — it would
            # render as an empty review card. Such a question is not meant to
            # appear in a scored quiz in the first place.
            if question.type in FREE_TEXT_QUESTION_TYPES:
                continue

            # A blank question stores no answer row at all, but it still
            # counts toward max_score — so it has to be judged here as an
            # empty selection, or the learner is marked down for a question
            # the review list never names.
            try:
                answer = self.answers.get(question=question)
            except QuestionAnswer.DoesNotExist:
                selected_options = []
            else:
                selected_options = list(answer.selected_options.all())
            selected_option_ids = {o.id for o in selected_options}

            # The same options the score is computed against, so the list
            # explains every mark the score takes off.
            marking = marking_options(question, served)
            is_correct = is_quiz_answer_correct(selected_option_ids, marking)

            if not is_correct:
                correct_options = [option for option in marking if option.correct]
                if served is not None:
                    # Listed in the order this learner was shown them, which on
                    # a shuffled paper is not the authored one.
                    # An option missing from the paper sorts last rather than
                    # dropping out of the review.
                    shown = served.options_of(question)
                    place = {o.id: index for index, o in enumerate(shown)}
                    correct_options = sorted(
                        correct_options, key=lambda o: place.get(o.id, len(place))
                    )
                    selected_options = sorted(
                        selected_options, key=lambda o: place.get(o.id, len(place))
                    )

                incorrect_answers.append(
                    {
                        "question": question,
                        # The number this learner was shown, which on a shuffled
                        # paper is not the authored one.
                        "number": positions[question.id],
                        "learner_selected": selected_options,
                        "correct_options": correct_options,
                    }
                )

        return incorrect_answers


class FormDeclarationQuerySet(models.QuerySet["FormDeclaration"]):
    """`delete()` stays so the cascades from the form progress and the user
    work; every call that would change a stored row raises."""

    def update(self, **kwargs: object) -> int:
        raise ValueError(_APPEND_ONLY_MESSAGE)

    def bulk_update(self, *args: object, **kwargs: object) -> int:
        raise ValueError(_APPEND_ONLY_MESSAGE)


_APPEND_ONLY_MESSAGE = (
    "FormDeclaration is append-only: a signed declaration cannot be changed"
)


class FormDeclaration(SiteAwareModel):
    """The declaration a learner signed before one sitting of a quiz.

    It is attestation evidence, not identity verification: the typed name and IP
    address corroborate who sat the quiz without proving it.
    """

    form_progress = models.OneToOneField(
        FormProgress, on_delete=models.CASCADE, related_name="declaration"
    )
    # The effective declaration text exactly as rendered, so the record holds
    # what the learner read even after the form's text changes.
    declaration_text = models.TextField()
    # As typed, spaces kept: the signature is what the learner entered.
    typed_name = models.CharField(max_length=200)
    signed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    objects = SiteAwareManager.from_queryset(FormDeclarationQuerySet)()

    def save(self, *args: object, **kwargs: object) -> None:
        # The UUID pk is set before the first save, so `_state.adding` is what
        # tells a first save from a second.
        if self.pk is not None and self._state.adding is False:
            raise ValueError(_APPEND_ONLY_MESSAGE)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.typed_name} - {self.form_progress}"


class QuestionAnswer(SiteAwareModel, TimestampedModel):
    """Stores answers to form questions."""

    form_progress = models.ForeignKey(
        FormProgress, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(FormQuestion, on_delete=models.PROTECT)
    selected_options = models.ManyToManyField(
        QuestionOption, blank=True
    )  # For checkbox/multiple choice questions
    text_answer = models.TextField(blank=True, default="")  # For text questions
    question_version = models.ForeignKey(
        FormQuestionVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="answers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form_progress", "question"],
                name="one_answer_per_question_per_form_progress",
            )
        ]

    def __str__(self):
        return f"{self.form_progress.user} - {self.question}"


def get_user_uploads_storage() -> Storage:
    """The fixed `user_uploads` alias; no setting names it, so it names itself."""
    return storage_for_alias("user_uploads", "STORAGES['user_uploads']")


def question_answer_file_upload_to(instance: QuestionAnswerFile, filename: str) -> str:
    """The key an answer file's first upload lands at.

    `filename` is the name FLS chose after sniffing the content, never the
    applicant's own. The applicant prefix is what gives an erasure request a
    single subtree to sweep.

    `user_uploads` never overwrites, so replacing a file at the same extension
    is stored under a storage-suffixed sibling of this key and
    `QuestionAnswerFile.save()` deletes the old one.
    """
    extension = Path(filename).suffix.lower()
    form_progress = instance.answer.form_progress
    # A sitting with no user is an anonymous visitor's. The sitting id is the
    # erasure prefix then, and the key is kept after the visitor claims an
    # account: deletion is row-driven, so erasing the user still removes it.
    if form_progress.user_id is None:
        return f"user_uploads/anonymous/{form_progress.pk}/form_answers/{instance.pk}{extension}"
    return f"user_uploads/{form_progress.user_id}/form_answers/{instance.pk}{extension}"


class QuestionAnswerFile(SiteAwareModel, TimestampedModel):
    """The file an applicant attached to a file-upload question.

    One per answer: attaching a second file replaces the first rather than
    accumulating, which is what keeps the bucket free of objects no row names.
    """

    answer = models.OneToOneField(
        QuestionAnswer, on_delete=models.CASCADE, related_name="answer_file"
    )
    file = models.FileField(
        upload_to=question_answer_file_upload_to, storage=get_user_uploads_storage
    )
    # Kept only to show the applicant what they attached and to name the
    # download. Never used to build a storage key.
    original_filename = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.original_filename

    @property
    def size_or_none(self) -> int | None:
        """The stored file's size in bytes, or None when storage cannot say.

        A page that lists answers must still render when an object has gone
        from the bucket or storage is unreachable, so it shows the file name
        without a size instead of failing.
        """
        try:
            return self.file.size
        except (OSError, ClientError):
            return None

    def save(self, *args: object, **kwargs: object) -> None:
        """Save, then remove the object this save superseded.

        The key carries the extension, and `user_uploads` does not overwrite, so
        a replacement always lands at a different key. Without the sweep the
        previous file -- an applicant's ID scan -- would stay in the bucket with
        no row naming it and nothing to sweep it later.
        """
        superseded = self._stored_file_name()
        super().save(*args, **kwargs)
        if superseded and superseded != self.file.name:
            self.file.storage.delete(superseded)

    def _stored_file_name(self) -> str:
        """The file name the database currently holds, empty for an unsaved row.

        Read through the base manager, because `objects` filters to the current
        request's Site and this has to see the row whatever Site it belongs to.
        Read from the database rather than tracked on the instance, because
        `file.save()` mutates and saves an instance that was never loaded.
        """
        if self._state.adding:
            return ""
        stored = (
            QuestionAnswerFile._base_manager.filter(pk=self.pk)
            .values_list("file", flat=True)
            .first()
        )
        return stored or ""
