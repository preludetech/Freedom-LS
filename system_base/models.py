from django.contrib.sites.models import Site
from django.db import models
import uuid


# class BaseModel(models.Model):
#     pass


class SiteAwareModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.ForeignKey(Site, on_delete=models.PROTECT)

    class Meta:
        abstract = True
