import factory

from freedom_ls.site_aware_models.factories import SiteAwareFactory
from freedom_ls.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookEvent


class WebhookEndpointFactory(SiteAwareFactory):
    class Meta:
        model = WebhookEndpoint

    url = factory.Faker("url")
    description = factory.Faker("sentence", nb_words=4)
    event_types = factory.LazyFunction(lambda: ["user.registered"])
    is_active = True
    # secret is auto-generated in WebhookEndpoint.save()


class WebhookEventFactory(SiteAwareFactory):
    class Meta:
        model = WebhookEvent

    event_type = "user.registered"
    payload = factory.LazyFunction(lambda: {"user_id": "abc-123"})


class WebhookDeliveryFactory(SiteAwareFactory):
    class Meta:
        model = WebhookDelivery

    event = factory.SubFactory(WebhookEventFactory)
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    status = "pending"
