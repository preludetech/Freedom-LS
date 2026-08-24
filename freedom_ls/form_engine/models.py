from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from freedom_ls.content_base.models import BaseContent, MarkdownContent, TitledContent
from freedom_ls.content_base.schema import ContentType as SchemaContentTypes
from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.site_aware_models.models import SiteAwareModel

from .enums import FREE_TEXT_QUESTION_TYPES, FormStrategy, QuestionType
from .scoring import is_quiz_answer_correct
from .signals import form_attempt_completed
from .submissions import (
    has_submitted_answer,
    submitted_option_ids,
    submitted_text_answer,
)

if TYPE_CHECKING:
    from django.http import QueryDict

# Re-exported so `from freedom_ls.form_engine.models import FormStrategy` keeps
# resolving now that the enums live in their own module.
__all__ = [
    "FREE_TEXT_QUESTION_TYPES",
    "Form",
    "FormPage",
    "FormProgress",
    "FormQuestion",
    "FormStrategy",
    "QuestionAnswer",
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

    submit_on_exit = models.BooleanField(
        default=False,
        help_text=_(
            "If True, leaving the test mid-attempt finalises and scores it. "
            "If False (default), the attempt is saved and can be resumed."
        ),
    )

    class Meta:
        unique_together = ["site", "slug"]

    def __str__(self):
        return self.title


class FormPage(TitledContent):
    """A page within a form."""

    CONTENT_TYPE = SchemaContentTypes.FORM_PAGE

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="pages")
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=200, blank=True, default="")

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

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.content[:50]


class FormQuestion(BaseContent):
    """A question within a form page."""

    CONTENT_TYPE = SchemaContentTypes.FORM_QUESTION

    form_page = models.ForeignKey(
        FormPage, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=200, blank=True, default="")

    question = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
    )
    required = models.BooleanField(default=True)

    def rendered_question(self):
        # No request: cotton components embedded in question markdown render
        # without request context, so none of them may depend on it.
        return render_markdown(self.question, None)

    def question_number(self):
        """
        Return 1 for the first question in the Form, 2 for the second etc. Note that this might not be the same as the order attribute because form pages contain more than just questions
        """
        form = self.form_page.form
        question_count = 0

        # Iterate through all pages in order
        for page in form.pages.all():
            # Get all questions on this page in order
            for question in page.questions.all():
                question_count += 1
                if question.pk == self.pk:
                    return question_count

        return None

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.question[:50]


class QuestionOption(SiteAwareModel):
    """An option for a form question."""

    question = models.ForeignKey(
        FormQuestion, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=500)
    value = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    correct = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text


User = get_user_model()


class FormProgress(SiteAwareModel):
    """Tracks a learner's progress through a form."""

    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="progress_records"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="form_progress"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_updated_time = models.DateTimeField(auto_now=True)
    completed_time = models.DateTimeField(blank=True, null=True)
    scores = models.JSONField(
        blank=True, null=True, help_text="Calculated scores by category"
    )

    class Meta:
        verbose_name_plural = "Form progress records"

    def __str__(self):
        return f"{self.user} - {self.form.title}"

    def quiz_percentage(self) -> int:
        if self.form.strategy != FormStrategy.QUIZ:
            raise ValueError("This method should only work for quiz models")
        if not self.scores:
            raise ValueError("Need to score the quiz before calling this method")

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

    @classmethod
    def get_latest_incomplete(cls, user, form):
        return (
            cls.objects.filter(user=user, form=form, completed_time__isnull=True)
            .order_by("-start_time")
            .first()
        )

    @classmethod
    def get_or_create_incomplete(cls, user, form):
        """
        Get the latest incomplete FormProgress for this user and form,
        or create a new one if all existing ones are completed.
        """
        # Try to get the latest incomplete progress
        incomplete = cls.get_latest_incomplete(user, form)

        if incomplete:
            return incomplete

        # No incomplete progress found, create a new one
        return cls.objects.create(user=user, form=form)

    @classmethod
    def finalise_stale_incomplete(cls, user, form) -> FormProgress | None:
        """
        For submit-on-exit forms: if the user has an incomplete attempt, complete it.
        Safe for save-on-exit forms (no-op) and idempotent via complete().
        Returns the finalised FormProgress or None.
        """
        if not form.submit_on_exit:
            return None
        # cast: get_latest_incomplete is untyped (.first() resolves to Any),
        # so without this mypy flags a no-any-return on the return below.
        incomplete = cast("FormProgress | None", cls.get_latest_incomplete(user, form))
        if incomplete is None:
            return None
        incomplete.complete()
        return incomplete

    def get_current_page_number(self):
        """
        Determine which page number the user should be on based on their progress.
        Returns the first page with unanswered questions, or the last page if all answered.
        """
        all_pages = list(self.form.pages.all())

        # Find the first page with unanswered questions
        for idx, page in enumerate(all_pages):
            # Get all questions on this page (filter out text items)
            questions_on_page = [
                child
                for child in page.children()
                if child.content_type == "FORM_QUESTION"
            ]

            for question in questions_on_page:
                if not self.answers.filter(question=question).exists():
                    return idx + 1

        # All questions answered, return last page (or 1 if no pages)
        return len(all_pages) if all_pages else 1

    def existing_answers_dict(self, questions):
        """
        Get a dictionary of existing answers for the given questions.
        Returns a dict with question.id as keys and QuestionAnswer objects as values.
        """
        existing_answers = {}
        for question in questions:
            try:
                answer = QuestionAnswer.objects.get(
                    form_progress=self, question=question
                )
                existing_answers[question.id] = answer
            except QuestionAnswer.DoesNotExist:
                pass
        return existing_answers

    def save_answers(
        self, questions: Iterable[FormQuestion], post_data: QueryDict
    ) -> None:
        """Persist the answers in `post_data` for `questions`.

        A question submitted with no answer stores no row, and loses any row from
        an earlier visit: a blank row would count toward the runner's answered
        tally and hide which questions are still outstanding.
        """
        for question in questions:
            if not has_submitted_answer(question, post_data):
                self.answers.filter(question=question).delete()
                continue

            answer, _created = QuestionAnswer.objects.get_or_create(
                form_progress=self, question=question, site=self.site
            )
            if question.type in FREE_TEXT_QUESTION_TYPES:
                answer.text_answer = submitted_text_answer(question, post_data)
            else:
                answer.selected_options.set(submitted_option_ids(question, post_data))
            answer.save()

    def complete(self):
        """Mark the form as completed and calculate the final score (idempotent)."""
        if self.completed_time:
            return
        self.completed_time = timezone.now()
        self.score()
        self.save()
        form_attempt_completed.send(sender=type(self), user=self.user, form=self.form)

    def score_category_value_sum(self):
        """
        Use the CATEGORY_VALUE_SUM scoring strategy:

        Each form page can have a category. This is the parent category
        Each question has a category. This is the child category

        Each question answer has a numerical value
        """
        # Note this only works with multiple_choice questions for now

        # 1. Get all questions from the form and create a data structure
        answer_data = []

        # Iterate through all pages and all questions
        for page in self.form.pages.all():
            for child in page.children():
                # Only process FormQuestion objects (skip FormContent)
                if child.content_type != "FORM_QUESTION":
                    continue

                question = child

                # Only process multiple choice questions for now
                if question.type != "multiple_choice":
                    continue

                # Get the maximum value among all options for this question
                max_value = 0
                for option in question.options.all():
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

    def compute_quiz_scores(self) -> dict[str, int]:
        """Score this attempt against the current marking rules, storing nothing.

        Scores are frozen at submission and never rescored, so a stored score can
        disagree with what the same answers would earn today. The results page
        re-derives a score to detect that, which it can only do without writing.
        """
        score = 0
        max_score = 0

        for page in self.form.pages.all():
            for child in page.children():
                # Only process FormQuestion objects (skip FormContent)
                if child.content_type != "FORM_QUESTION":
                    continue

                question = child

                # Count this question toward max_score
                max_score += 1

                # Check if user answered this question correctly
                try:
                    answer = self.answers.get(question=question)
                    selected_option_ids = {o.id for o in answer.selected_options.all()}
                    if is_quiz_answer_correct(
                        selected_option_ids, question.options.all()
                    ):
                        score += 1

                except QuestionAnswer.DoesNotExist:
                    # Question not answered, contributes 0 to score
                    pass

        return {"score": score, "max_score": max_score}

    def score_quiz(self):
        """
        Calculate quiz score by counting correct answers.
        """
        self.scores = self.compute_quiz_scores()
        self.save()

    def score(self):
        """calculate the final score for the form"""
        if self.form.strategy == FormStrategy.CATEGORY_VALUE_SUM:
            self.score_category_value_sum()
        elif self.form.strategy == FormStrategy.QUIZ:
            self.score_quiz()

        else:
            raise Exception(f"Unhandled Strategy: {self.form.strategy}")

    def get_incorrect_quiz_answers(self):
        """
        Get a list of incorrect answers for a completed quiz.

        Returns a list of dicts with:
        - question: FormQuestion instance
        - learner_selected: list of QuestionOption instances the learner selected
        - correct_options: list of QuestionOption instances that are correct

        Only returns results if:
        - form.strategy is QUIZ

        We will use this function in multiple places. Sometimes we'll want to show the incorrect answers to the teacher. Even if we dont want to show the answers to the learner, this function should work
        """
        incorrect_answers: list[dict] = []

        if self.form.strategy != FormStrategy.QUIZ:
            return incorrect_answers

        # Iterate through all pages and questions
        for page in self.form.pages.all():
            for child in page.children():
                # Only process FormQuestion objects
                if child.content_type != "FORM_QUESTION":
                    continue

                question = child

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

                # Check if the answer is correct
                is_correct = is_quiz_answer_correct(
                    selected_option_ids, question.options.all()
                )

                if not is_correct:
                    # Get the correct option(s)
                    correct_options = list(question.options.filter(correct=True))

                    incorrect_answers.append(
                        {
                            "question": question,
                            "learner_selected": selected_options,
                            "correct_options": correct_options,
                        }
                    )

        return incorrect_answers


class QuestionAnswer(SiteAwareModel):
    """Stores answers to form questions."""

    form_progress = models.ForeignKey(
        FormProgress, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(
        QuestionOption, blank=True
    )  # For checkbox/multiple choice questions
    text_answer = models.TextField(blank=True, default="")  # For text questions
    last_updated_time = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["form_progress", "question"]

    def __str__(self):
        return f"{self.form_progress.user} - {self.question}"
