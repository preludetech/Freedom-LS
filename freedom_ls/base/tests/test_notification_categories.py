from django.utils.translation import gettext_lazy as _

from freedom_ls.base.notification_categories import NotificationCategory


def test_a_category_built_without_a_colour_has_none() -> None:
    category = NotificationCategory(
        key="a.b",
        label=_("A"),
        icon="course",
        message=_("m"),
        url_builder=None,
    )

    assert category.colour is None
