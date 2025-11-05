from django.db import models
from django.contrib.auth import get_user_model
from content_engine.models import Form, FormQuestion, QuestionOption, Topic
from system_base.models import SiteAwareModel

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

    class Meta:
        verbose_name_plural = "Form progress records"

    def __str__(self):
        return f"{self.user} - {self.form.title}"

    @classmethod
    def get_or_create_incomplete(cls, user, form):
        """
        Get the latest incomplete FormProgress for this user and form,
        or create a new one if all existing ones are completed.
        """
        # Try to get the latest incomplete progress
        incomplete = (
            cls.objects.filter(user=user, form=form, completed_time__isnull=True)
            .order_by("-start_time")
            .first()
        )

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
