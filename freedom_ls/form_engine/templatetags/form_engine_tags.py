"""Template tags for the form_engine app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template
from django.template import Context

from freedom_ls.form_engine.phone_numbers import (
    browser_country,
    country_choices,
    phone_after_calling_code,
    phone_example,
    phone_examples,
    stored_phone_country,
)
from freedom_ls.form_engine.submissions import submitted_phone_country
from freedom_ls.form_engine.typed_answers import format_answer
from freedom_ls.form_engine.uploads import (
    ACCEPT_ATTRIBUTE,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_LABEL,
)

if TYPE_CHECKING:
    from django.http import HttpRequest

    from freedom_ls.form_engine.models import FormQuestion

register = template.Library()


@register.simple_tag
def upload_limits() -> dict[str, object]:
    """The upload caps, so no template hard-codes a number the validator owns."""
    return {
        "max_bytes": MAX_UPLOAD_BYTES,
        "accept": ACCEPT_ATTRIBUTE,
        "max_label": MAX_UPLOAD_LABEL,
    }


def _country_for_an_empty_question(
    question: FormQuestion, request: HttpRequest | None
) -> str:
    """The country to select beside an empty number box.

    Only an empty question takes the browser's hint: guessing a country beside
    a number someone already typed could change which number it means.
    """
    if request is None:
        return ""
    if f"phone_country_{question.id}" in request.POST:
        # The page is coming back after a submission that left the number
        # blank. Whatever the picker held, a cleared one included, is the
        # person's choice and outranks a guess.
        return submitted_phone_country(question, request.POST)
    return browser_country(request.headers.get("Accept-Language", "")) or ""


@register.simple_tag(takes_context=True)
def phone_field_state(context: Context) -> dict[str, object]:
    """What the phone question's two controls show: the selected country, the
    number, the countries on offer, and the example hint for each country.

    Reads `question`, `rejected`, `existing_answers` and `request` from the
    context the question template already holds, so no view computes anything for it.
    """
    question = context["question"]
    rejected = context.get("rejected")
    if rejected:
        # An empty choice stays empty: someone who cleared the picker and
        # was refused must not find a country chosen for them.
        country, number = rejected.country, rejected.text
    else:
        answer = (context.get("existing_answers") or {}).get(question.id)
        stored = answer.text_answer if answer else ""
        country = stored_phone_country(stored) or ""
        number = phone_after_calling_code(stored)
        if not stored:
            country = _country_for_an_empty_question(question, context.get("request"))
    return {
        "country": country,
        "number": number,
        "choices": country_choices(),
        "example": (phone_example(country) or "") if country else "",
        "examples": phone_examples(),
        "examples_id": f"phone_examples_{question.id}",
    }


@register.filter
def answer_display(text_answer: object, question_type: object) -> str:
    """A stored answer rendered for a reader.

    Takes the type as an argument rather than walking `answer.question`, so a
    caller already holding both in memory (as the check-your-answers page
    does, from a prefetch that does not include `answers__question`) does not
    pay a query per row to reach it.

    Usage: {{ answer.text_answer|answer_display:question.type }}
    """
    if not isinstance(text_answer, str):
        return ""
    if not isinstance(question_type, str):
        return text_answer
    return format_answer(question_type, text_answer)
