import factory

from django.contrib.sites.models import Site
from django.db.models import Model

from freedom_ls.site_aware_models.factories import SiteAwareFactory

from .models import ApiKey
from .scopes import ApiScope


class ApiKeyFactory(SiteAwareFactory):
    class Meta:
        model = ApiKey

    name = factory.Sequence(lambda n: f"Key {n}")
    scopes = factory.LazyFunction(lambda: [ApiScope.USERS])

    @classmethod
    def _create(
        cls, model_class: type[Model], *args: object, **kwargs: object
    ) -> Model:
        # issue() is the only path that produces a prefix and hash, so the
        # factory goes through it and keeps the key text where tests read it.
        # `site` is the ambient site from mock_site_context unless a test
        # passes one, which only the host-mismatch tests do.
        site = kwargs.pop("site")
        if not isinstance(site, Site):
            raise ValueError(
                "ApiKeyFactory needs a site: take mock_site_context or pass site=."
            )
        instance = model_class(*args, **kwargs)
        if not isinstance(instance, ApiKey):
            raise TypeError("ApiKeyFactory builds ApiKey rows only.")
        instance.issued_key = ApiKey.issue(instance, site=site)
        return instance
