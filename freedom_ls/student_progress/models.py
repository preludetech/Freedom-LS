from django.db import models
from django.contrib.auth import get_user_model
from freedom_ls.content_engine.models import (
    Form,
    FormQuestion,
    QuestionOption,
    Topic,
    FormStrategy,
    Course,
)
from freedom_ls.site_aware_models.models import SiteAwareModel
from django.utils import timezone

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

    def quiz_percentage(self):
        if self.form.strategy != FormStrategy.QUIZ:
            raise ValueError("This method should only work for quiz models")
        if not self.scores:
            raise ValueError("Need to score the quiz before calling this method")

        return round((self.scores["score"] / self.scores["max_score"]) * 100)

    def passed(self):
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

    def score_quiz(self):
        """
        Calculate quiz score by counting correct answers.
        """
        score = 0
        max_score = 0

        # Iterate through all pages and questions
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
                    selected_options = answer.selected_options.all()

                    # Check if any selected option is marked as correct
                    for option in selected_options:
                        if option.correct:
                            score += 1
                            break  # Only count once per question

                except QuestionAnswer.DoesNotExist:
                    # Question not answered, contributes 0 to score
                    pass

        # Save the scores
        self.scores = {"score": score, "max_score": max_score}
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
        - student_selected: list of QuestionOption instances the student selected
        - correct_options: list of QuestionOption instances that are correct

        Only returns results if:
        - form.strategy is QUIZ

        We will use this function in multiple places. Sometimes we'll want to show the incorrect answers to the teacher. Even if we dont want to show the answers to the student, this function should work
        """
        incorrect_answers = []

        if self.form.strategy != FormStrategy.QUIZ:
            return incorrect_answers

        # Iterate through all pages and questions
        for page in self.form.pages.all():
            for child in page.children():
                # Only process FormQuestion objects
                if child.content_type != "FORM_QUESTION":
                    continue

                question = child

                # Get the student's answer for this question
                try:
                    answer = self.answers.get(question=question)
                except QuestionAnswer.DoesNotExist:
                    # Question not answered, skip
                    continue

                selected_options = list(answer.selected_options.all())

                # Check if the answer is correct
                is_correct = any(option.correct for option in selected_options)

                if not is_correct:
                    # Get the correct option(s)
                    correct_options = list(question.options.filter(correct=True))

                    incorrect_answers.append(
                        {
                            "question": question,
                            "student_selected": selected_options,
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


class CourseProgress(SiteAwareModel):
    """Tracks a user's progress through a course."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="course_progress"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="progress_records"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_accessed_time = models.DateTimeField(auto_now=True)
    completed_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Course progress records"
        unique_together = ["user", "course"]

    def __str__(self):
        return f"{self.user} - {self.course.title}"
