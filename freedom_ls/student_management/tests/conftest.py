import pytest
from django.contrib.contenttypes.models import ContentType
from freedom_ls.content_engine.models import Topic


@pytest.fixture
def topic_ct():
    return ContentType.objects.get_for_model(Topic)
