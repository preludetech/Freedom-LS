from __future__ import annotations

import factory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class NotificationFactory(SiteAwareFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    category = "course.registered"
    target = factory.SubFactory(CourseFactory)
    data = factory.LazyAttribute(lambda n: {"course_title": n.target.title})
