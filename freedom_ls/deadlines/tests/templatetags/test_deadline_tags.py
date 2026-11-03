from datetime import datetime
from zoneinfo import ZoneInfo

from django.template import Context, Template


def test_the_deadline_tags_library_still_renders_local_time_as_the_component():
    due = datetime(2026, 3, 15, 23, 59, tzinfo=ZoneInfo("Africa/Johannesburg"))

    rendered = Template("{% load deadline_tags %}{% local_time due %}").render(
        Context({"due": due})
    )

    assert 'x-data="localTime"' in rendered
