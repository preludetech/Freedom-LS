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

    def save_answers(self, questions, post_data):
        """
        Save answers from POST data for the given questions.
        Handles multiple_choice, checkboxes, short_text, and long_text question types.
        """
        for question in questions:
            field_name = f"question_{question.id}"

            # Get or create the answer
            answer, created = QuestionAnswer.objects.get_or_create(
                form_progress=self, question=question
            )

            # Handle different question types
            if question.type == "multiple_choice":
                # Get the selected option ID from POST
                option_id = post_data.get(field_name)
                if option_id:
                    # Clear existing selections and set the new one
                    answer.selected_options.clear()
                    answer.selected_options.add(option_id)
                    answer.save()

            elif question.type == "checkboxes":
                # Get all selected option IDs (can be multiple)
                option_ids = post_data.getlist(field_name)
                if option_ids:
                    answer.selected_options.clear()
                    answer.selected_options.add(*option_ids)
                    answer.save()

            elif question.type in ["short_text", "long_text"]:
                # Get text answer
                text_answer = post_data.get(field_name, "")
                answer.text_answer = text_answer
                answer.save()

    def complete(self):
        """
        Mark the form as completed and calculate the final score.
        """
        from django.utils import timezone

        self.completed_time = timezone.now()
        self.score()
        self.save()

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
        scores = {}

        for item in answer_data:
            page_cat = item["page_category"] or "Uncategorized"
            question_cat = item["question_category"]  # Keep as None if not set

            # Initialize category structure if not exists
            if page_cat not in scores:
                scores[page_cat] = {"score": 0, "max_score": 0, "sub_categories": {}}

            # Add to parent category scores (always)
            scores[page_cat]["score"] += item["value"]
            scores[page_cat]["max_score"] += item["max_value"]

            # Only create subcategory if question has a category
            if question_cat is not None:
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

        # 3. Save to JSON field
        self.scores = scores
        self.save()

    def score(self):
        """calculate the final score for the form"""
        if self.form.strategy == FormStrategy.CATEGORY_VALUE_SUM:
            self.score_category_value_sum()
        elif self.form.strategy == FormStrategy.QUIZ:
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
