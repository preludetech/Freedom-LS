from django.contrib.sites.models import Site
from django.db import models
import uuid
from django.contrib.sites.shortcuts import get_current_site
from threading import local

_thread_locals = local()


class SiteAwareManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(_thread_locals, 'request', None)
        if request:
            site = get_current_site(request)
            return queryset.filter(site_id=site)
        return queryset


class SiteAwareModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.ForeignKey(Site, on_delete=models.PROTECT)

    objects = SiteAwareManager()

    class Meta:
        abstract = True
