import factory

from freedom_ls.site_aware_models.factories import SiteAwareFactory
from freedom_ls.webhooks.models import (
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
    WebhookSecret,
)


class WebhookEndpointFactory(SiteAwareFactory):
    class Meta:
        model = WebhookEndpoint

    url = factory.Faker("url")
    description = factory.Faker("sentence", nb_words=4)
    event_types = factory.LazyFunction(lambda: ["user.registered"])
    is_active = True
    # secret is auto-generated in WebhookEndpoint.save()
    http_method = ""
    content_type = ""
    headers_template = ""
    body_template = ""
    preset_slug = ""
    auth_type = "signing"


class TransformedWebhookEndpointFactory(WebhookEndpointFactory):
    body_template: str = (
        '{"event": "{{ event.type }}", "data": {{ event.data | tojson }}}'
    )
    headers_template: str = '{"X-Custom-Header": "transformed"}'
    http_method: str = "POST"
    content_type: str = "application/json"
    auth_type = "none"


class WebhookEventFactory(SiteAwareFactory):
    class Meta:
        model = WebhookEvent

    event_type = "user.registered"
    payload = factory.LazyFunction(lambda: {"user_id": "abc-123"})


class WebhookSecretFactory(SiteAwareFactory):
    class Meta:
        model = WebhookSecret

    name = factory.Sequence(lambda n: f"secret_key_{n}")
    description = factory.Faker("sentence", nb_words=4)
    encrypted_value = factory.Faker("password", length=32)


class WebhookDeliveryFactory(SiteAwareFactory):
    class Meta:
        model = WebhookDelivery

    event = factory.SubFactory(WebhookEventFactory)
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    status = "pending"
