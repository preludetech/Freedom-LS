from __future__ import annotations

from freedom_ls.messaging_policy.models import FLAG_NAMES, SiteMessagingConfig
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class SiteMessagingConfigForm(ConstraintValidationFormMixin):
    """Admin form for SiteMessagingConfig.

    ``site`` is un-excluded from validation so unique_messaging_config_per_site
    is checked while cleaning rather than failing at the database. It is still
    never rendered.
    """

    class Meta:
        model = SiteMessagingConfig
        fields = list(FLAG_NAMES)
