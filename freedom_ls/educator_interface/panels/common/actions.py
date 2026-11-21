"""The helpers every educator action module shares: parameter readers, reason dialog base and picker titles."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast
from uuid import UUID

from django import forms
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.forms import EducatorReasonForm
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import ReasonMixin, refusal_response
from freedom_ls.panel_framework.context import PanelContext

__all__ = [
    "EducatorReasonMixin",
    "_action_params",
    "_empty_message",
    "_picker_title",
    "_register_title",
    "_uuid_from",
    "inactive_cohort_response",
]


def _uuid_from(params: Mapping[str, str], name: str) -> UUID:
    try:
        return UUID(params.get(name, ""))
    except ValueError:
        raise Http404(f"No such {name}") from None


def _action_params(request: HttpRequest) -> Mapping[str, str]:
    """The parameters an action's trigger sent along: the form on a submit,
    the query string otherwise."""
    return request.POST if request.method == "POST" else request.GET


class EducatorReasonMixin(ReasonMixin):
    """A reason dialog that words its field the educator way."""

    reason_form_class = EducatorReasonForm


def _empty_message(form: forms.BaseForm, field_name: str, message: str) -> str | None:
    """`message` when the picker's field offers nothing, otherwise None."""
    queryset = cast(forms.ModelChoiceField, form.fields[field_name]).queryset
    return None if queryset is not None and queryset.exists() else message


def _picker_title[M: Model](
    form: forms.BaseForm,
    field_name: str,
    *,
    unchosen: str,
    chosen: Callable[[M], str],
) -> str:
    """The question a picker dialog asks: `chosen` names the valid choice the
    form holds, `unchosen` stands until there is one."""
    if form.is_bound and form.is_valid():
        return f"{chosen(cast(M, form.cleaned_data[field_name]))}?"
    return f"{unchosen}?"


def _register_title(
    form: forms.BaseForm, subject: str, organisation: Organisation
) -> str:
    """Title a register-for-a-course dialog for `subject` (a learner's or a
    cohort's name), naming the course once one is chosen, as `organisation`
    reads it."""

    def chosen(course: Course) -> str:
        return f"Register {subject} for {course.label_for(organisation)}"

    return _picker_title(
        form, "course", unchosen=f"Register {subject} for a course", chosen=chosen
    )


def inactive_cohort_response(
    ctx: PanelContext, cohort: Cohort, blocked_phrase: str
) -> HttpResponse:
    """The 422 fragment for a change aimed at an inactive cohort.
    `blocked_phrase` completes "Reactivate the cohort ... to" with what the
    refused action would have done, such as "deactivate it"."""
    return refusal_response(
        ctx,
        title=f"{cohort} is inactive",
        message=(
            "The change was not made. Reactivate the cohort from its Settings "
            f"tab to {blocked_phrase}."
        ),
    )
