"""The shipped demo content has to show every way a course can be priced,
so each price display can be seen without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.models import Course, PriceKind

pytestmark = pytest.mark.fls_internal


@pytest.mark.django_db
def test_the_demo_courses_cover_every_price_kind(site, loaded_demo_content):
    kinds = set(
        Course.objects.filter(site=site)
        .exclude(price_kind="")
        .values_list("price_kind", flat=True)
    )

    assert kinds == set(PriceKind)
