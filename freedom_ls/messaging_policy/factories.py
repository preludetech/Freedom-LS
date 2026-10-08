from __future__ import annotations

from freedom_ls.messaging_policy.models import SiteMessagingConfig
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class SiteMessagingConfigFactory(SiteAwareFactory):
    class Meta:
        model = SiteMessagingConfig
