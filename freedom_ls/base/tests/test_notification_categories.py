from django.utils.translation import gettext_lazy as _

from freedom_ls.base.notification_categories import (
    FLS_NOTIFICATION_CATEGORIES,
    NotificationCategory,
)


def test_a_category_built_without_a_colour_has_none() -> None:
    category = NotificationCategory(
        key="a.b",
        label=_("A"),
        icon="course",
        message=_("m"),
        url_builder=None,
    )

    assert category.colour is None


def test_each_pause_category_keeps_its_own_row_per_event() -> None:
    categories = {category.key: category for category in FLS_NOTIFICATION_CATEGORIES}

    assert (
        categories["course.paused"].rollup,
        categories["course.resumed"].rollup,
    ) == (
        False,
        False,
    )
