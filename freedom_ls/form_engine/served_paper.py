"""The paper one quiz sitting is served: its pages, their children and each
question's options, in the order the learner sees them.

Written once per sitting and never changed, so the sitting can be shown and
scored the same way however the form is edited afterwards.
"""

from __future__ import annotations

import secrets

from django.db.models import prefetch_related_objects

from .conditions import SERVED_TREE_LOOKUPS, ServedPage, ServedPaper
from .models import Form, FormProgress, FormQuestion, FormStrategy


def build_served_paper(form: Form) -> ServedPaper:
    """The paper a sitting starting now is served: the form's current tree in authored order."""
    prefetch_related_objects([form], *SERVED_TREE_LOOKUPS)
    pages: list[ServedPage] = []
    options: dict[str, list[str]] = {}
    for page in form.pages.all():
        children = page.children()
        pages.append({"id": str(page.id), "children": [str(c.id) for c in children]})
        for child in children:
            if isinstance(child, FormQuestion):
                option_ids = [str(o.id) for o in child.options.all()]
                if option_ids:
                    options[str(child.id)] = option_ids
    # Provenance only: nothing rebuilds an order from the seed.
    return {"seed": secrets.randbits(63), "pages": pages, "options": options}


def ensure_served_paper(form_progress: FormProgress) -> None:
    """Write the sitting's served paper if it is an open quiz sitting without one."""
    if (
        form_progress.served_paper is not None
        or form_progress.completed_time is not None
        or form_progress.form.strategy != FormStrategy.QUIZ
    ):
        return
    # Conditional on the column still being null, then re-read: two requests
    # racing on a sitting's first page both end up holding the first writer's paper.
    FormProgress.objects.filter(pk=form_progress.pk, served_paper__isnull=True).update(
        served_paper=build_served_paper(form_progress.form)
    )
    form_progress.served_paper = FormProgress.objects.values_list(
        "served_paper", flat=True
    ).get(pk=form_progress.pk)
