from django.contrib import admin
from unfold.admin import TabularInline
from system_base.admin import SiteAwareModelAdmin
from .models import ContentItem, ContentSequence, ContentSequenceItem


class ContentItemSequencesInline(TabularInline):
    model = ContentSequenceItem
    extra = 0
    autocomplete_fields = ["content_sequence"]
    exclude = ["site_id"]
    verbose_name = "Content Sequence"
    verbose_name_plural = "Content Sequences"
    fields = ["content_sequence", "order"]


class ContentSequenceItemsInline(TabularInline):
    model = ContentSequenceItem
    extra = 1
    autocomplete_fields = ["content_item"]
    exclude = ["site_id"]
    verbose_name = "Content Item"
    verbose_name_plural = "Content Items"
    fields = ["order", "content_item"]
    ordering = ["order"]


@admin.register(ContentItem)
class ContentItemAdmin(SiteAwareModelAdmin):
    list_display = ["title", "blurb", "get_sequences"]
    search_fields = ["title", "blurb"]
    inlines = [ContentItemSequencesInline]

    def get_sequences(self, obj):
        sequences = ContentSequence.objects.filter(contentsequenceitem__content_item=obj)
        return ", ".join([seq.title for seq in sequences])
    get_sequences.short_description = "Sequences"


@admin.register(ContentSequence)
class ContentSequenceAdmin(SiteAwareModelAdmin):
    list_display = ["title", "blurb", "get_item_count"]
    search_fields = ["title", "blurb"]
    inlines = [ContentSequenceItemsInline]

    def get_item_count(self, obj):
        return obj.contentsequenceitem_set.count()
    get_item_count.short_description = "Items"
