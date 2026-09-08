"""Shared helpers for the course_applications tests."""

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.course_applications"):
    collect_ignore_glob = ["test_*.py"]


def gated_course_with_form():
    """An application-gated course whose applicants fill in a two-page form.

    Page 1 carries one question of each non-file type; page 2 carries the file
    question, so a test can reach a page that needs a real upload without the
    first page demanding one.
    """
    from freedom_ls.content_engine.factories import CourseFactory
    from freedom_ls.form_engine.factories import (
        FormFactory,
        FormPageFactory,
        FormQuestionFactory,
        QuestionOptionFactory,
    )
    from freedom_ls.form_engine.models import FormStrategy

    form = FormFactory(strategy=FormStrategy.UNSCORED)

    page_one = FormPageFactory(form=form, order=0, title="About you")
    FormQuestionFactory(
        form_page=page_one,
        type="short_text",
        order=0,
        question="Your name",
        required=True,
    )
    FormQuestionFactory(
        form_page=page_one,
        type="number",
        order=1,
        question="Years of experience",
        required=False,
    )
    choice = FormQuestionFactory(
        form_page=page_one,
        type="multiple_choice",
        order=2,
        question="How did you hear about us",
        required=False,
    )
    QuestionOptionFactory(question=choice, text="A friend", order=0)
    QuestionOptionFactory(question=choice, text="Search", order=1)
    FormQuestionFactory(
        form_page=page_one,
        type="long_text",
        order=3,
        question="Why apply",
        required=False,
    )

    page_two = FormPageFactory(form=form, order=1, title="Supporting documents")
    FormQuestionFactory(
        form_page=page_two,
        type="file_upload",
        order=0,
        question="Upload your ID",
        required=False,
    )

    course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    return course, form
