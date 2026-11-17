from django.db import models


class FormQuestionTopic(models.Model):
    """A topic a question tests.

    No site column: the question and the topic are both rows of one site.
    PROTECT on the topic so a topic stays while any question names it,
    including a question dropped from its file but still in the database.
    """

    question = models.ForeignKey(
        "freedom_ls_form_engine.FormQuestion", on_delete=models.CASCADE
    )
    topic = models.ForeignKey(
        "freedom_ls_content_engine.Topic", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "topic"], name="unique_form_question_topic"
            )
        ]

    def __str__(self) -> str:
        return f"{self.question_id} tests {self.topic_id}"


class FormQuestionCoursePart(models.Model):
    """A course part a question tests.

    No site column: the question and the part are both rows of one site.
    PROTECT on the part so a part stays while any question names it,
    including a question dropped from its file but still in the database.
    """

    question = models.ForeignKey(
        "freedom_ls_form_engine.FormQuestion", on_delete=models.CASCADE
    )
    course_part = models.ForeignKey(
        "freedom_ls_content_engine.CoursePart", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "course_part"],
                name="unique_form_question_course_part",
            )
        ]

    def __str__(self) -> str:
        return f"{self.question_id} tests {self.course_part_id}"
