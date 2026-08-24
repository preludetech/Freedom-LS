from pathlib import Path

from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.markdown_rendering.markdown_utils import render_markdown
from freedom_ls.site_aware_models.models import SiteAwareModel


class BaseContent(SiteAwareModel):
    """Base model for all content types."""

    CONTENT_TYPE: str  # Defined on subclasses

    file_path = models.CharField(
        max_length=500,
        help_text=_("Relative path to the source file"),
    )
    meta = models.JSONField(
        null=True, blank=True, help_text=_("Optional metadata as key-value pairs")
    )
    tags = models.JSONField(null=True, blank=True, help_text=_("Optional list of tags"))

    class Meta:
        abstract = True

    @property
    def content_type(self):
        """Instance property that returns the class-level CONTENT_TYPE."""
        return self.CONTENT_TYPE

    def calculate_path_from_root(self, other_relative_path):
        """
        When we load content, the file_paths are relative to the content directory root

        Given a path that is relative to self.file_path, return the path relative to the content root

        For example:
        self.path = tutorial/02-understanding-the-graph-commits-and-checkout.md
        other_relative_path = images/graph1.drawio.svg
        return "tutorial/images/graph1.drawio.svg"

        tutorial/
            images/
                graph1.drawio.svg
            02-understanding-the-graph-commits-and-checkout.md
        """
        parent_dir = Path(self.file_path).parent
        other_relative_path = Path(other_relative_path)

        result = parent_dir

        for part in other_relative_path.parts:
            result = result.parent if part == ".." else result / part

        return result.as_posix()


class TitledContent(BaseContent):
    """Base content model with title and subtitle."""

    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(
        blank=True, default="", help_text=_("Optional description")
    )
    slug = models.SlugField(
        max_length=500,
        help_text=_("URL-friendly identifier"),
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class MarkdownContent(BaseContent):
    """Base content model with markdown content."""

    content = models.TextField(blank=True, default="", help_text=_("Markdown content"))

    def rendered_content(self):
        if not self.content:
            return ""

        # No request: cotton components embedded in content markdown render
        # without request context, so none of them may depend on it.
        return render_markdown(self.content, None, context={"content_instance": self})

    class Meta:
        abstract = True
