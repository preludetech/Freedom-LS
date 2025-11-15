from django.db import models
from django.contrib.auth import get_user_model
from content_engine.models import (
    Form,
    FormQuestion,
    QuestionOption,
    Topic,
    FormStrategy,
)
from site_aware_models.models import SiteAwareModel

User = get_user_model()


class FormProgress(SiteAwareModel):
    """Tracks a user's progress through a form."""

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

    def score_category_value_sum(self):
        """
        Use the CATEGORY_VALUE_SUM scoring strategy:

        Each form page can have a category. This is the parent category
        Each question has a category. This is the child category

        Each question answer has a numerical value
        """
        # Note this only works with multiple_choice questions for now

        # 1. Get all the FormAnswers and create a data structure
        answer_data = []
        for answer in self.answers.all():
            question = answer.question

            # Only process multiple choice questions for now
            if question.type != "multiple_choice":
                continue

            # Get the selected option(s)
            selected_options = answer.selected_options.all()
            if not selected_options.exists():
                continue

            # Get the value of the selected option (convert to int)
            selected_option = selected_options.first()
            try:
                value = int(selected_option.value)
            except (ValueError, TypeError):
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

            # Get categories
            page_category = question.form_page.category
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
        scores = {}

        for item in answer_data:
            page_cat = item["page_category"] or "Uncategorized"
            question_cat = item["question_category"] or "Uncategorized"

            # Initialize category structure if not exists
            if page_cat not in scores:
                scores[page_cat] = {"score": 0, "max_score": 0, "sub_categories": {}}

            # Initialize subcategory if not exists
            if question_cat not in scores[page_cat]["sub_categories"]:
                scores[page_cat]["sub_categories"][question_cat] = {
                    "score": 0,
                    "max_score": 0,
                }

            # Add to subcategory scores
            scores[page_cat]["sub_categories"][question_cat]["score"] += item["value"]
            scores[page_cat]["sub_categories"][question_cat]["max_score"] += item[
                "max_value"
            ]

            # Add to parent category scores
            scores[page_cat]["score"] += item["value"]
            scores[page_cat]["max_score"] += item["max_value"]

        # 3. Save to JSON field
        self.scores = scores
        self.save()

    def score(self):
        """calculate the final score for the form"""
        if self.form.strategy == FormStrategy.CATEGORY_VALUE_SUM:
            self.score_category_value_sum()
        else:
            raise Exception(f"Unhandled Strategy: {self.form.strategy}")


class QuestionAnswer(SiteAwareModel):
    """Stores answers to form questions."""

    form_progress = models.ForeignKey(
        FormProgress, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(
        QuestionOption, blank=True
    )  # For checkbox/multiple choice questions
    text_answer = models.TextField(blank=True, null=True)  # For text questions
    last_updated_time = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["form_progress", "question"]

    def __str__(self):
        return f"{self.form_progress.user} - {self.question}"


class TopicProgress(SiteAwareModel):
    """Tracks a user's progress through a topic."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="topic_progress"
    )
    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name="progress_records"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_accessed_time = models.DateTimeField(auto_now=True)
    complete_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Topic progress records"
        unique_together = ["user", "topic"]

    def __str__(self):
        return f"{self.user} - {self.topic.title}"
