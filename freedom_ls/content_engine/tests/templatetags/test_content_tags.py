"""Tests for the content template tags."""

from __future__ import annotations

import pytest

from django.test import override_settings
from django.utils.safestring import SafeString

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import ArticleFactory, TopicFactory
from freedom_ls.content_engine.models import ArticleVisibility
from freedom_ls.content_engine.templatetags.content_tags import (
    admonition_config,
    admonition_icon,
    get_content_by_path,
    get_published_article_by_path,
)
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import Form
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

# Tests for template tags in content_tags.py.
#
# Covers:
# - admonition_config: type→registry entry resolution
# - admonition_icon: renders SVG from a config dict
# - c-admonition component: renders label, icon, body via markdown pipeline
# - get_content_by_path: path→Topic, falling back to path→Form


class TestAdmonitionConfig:
    """admonition_config returns the registry entry for a known type."""

    def test_known_type_returns_its_entry(self) -> None:
        result = admonition_config("note")

        assert result["label"] == "Note"
        assert result["icon"] == "info"
        assert result["color"] == "info"

    def test_known_type_tip_returns_tip_entry(self) -> None:
        result = admonition_config("tip")

        assert result["label"] == "Tip"
        assert result["color"] == "success"

    def test_unknown_type_returns_default_entry(self) -> None:
        result = admonition_config("completely_unknown_type")

        default = admonition_config("default")
        assert result == default

    def test_empty_string_type_returns_default_entry(self) -> None:
        result = admonition_config("")

        default = admonition_config("default")
        assert result == default

    @override_settings(
        ADMONITION_TYPES={
            "custom": {"label": "Custom Label", "icon": "star", "color": "success"},
            "default": {"label": "Fallback", "icon": "info", "color": "info"},
        }
    )
    def test_overridden_settings_are_respected(self) -> None:
        result = admonition_config("custom")

        assert result["label"] == "Custom Label"

    @override_settings(
        ADMONITION_TYPES={
            "custom": {"label": "Custom Label", "icon": "star", "color": "success"},
            "default": {"label": "Fallback", "icon": "info", "color": "info"},
        }
    )
    def test_unknown_type_falls_back_to_overridden_default(self) -> None:
        result = admonition_config("note")  # not in the override

        assert result["label"] == "Fallback"

    def test_returns_dict(self) -> None:
        result = admonition_config("warning")

        assert isinstance(result, dict)

    @pytest.mark.parametrize(
        "admonition_type",
        [
            "note",
            "tip",
            "important",
            "warning",
            "danger",
            "key_takeaways",
            "checklist",
            "default",
        ],
    )
    def test_builtin_type_resolves_to_label_icon_and_color(
        self, admonition_type: str
    ) -> None:
        result = admonition_config(admonition_type)

        assert {"label", "icon", "color"} <= set(result)


# ---------------------------------------------------------------------------
# admonition_icon
# ---------------------------------------------------------------------------


class TestAdmonitionIcon:
    """admonition_icon renders an SVG SafeString from a config dict."""

    def test_returns_safe_string(self) -> None:
        cfg = {"icon": "info", "color": "info"}
        result = admonition_icon(cfg)

        assert isinstance(result, SafeString)

    def test_result_contains_svg(self) -> None:
        cfg = {"icon": "info", "color": "info"}
        result = admonition_icon(cfg)

        assert "<svg" in result

    def test_empty_icon_in_cfg_falls_back_gracefully(self) -> None:
        cfg = {"icon": "", "color": "info"}
        result = admonition_icon(cfg)

        # Falls back to default_semantic="info" — should still produce SVG
        assert "<svg" in result
        assert isinstance(result, SafeString)

    def test_missing_icon_key_falls_back_gracefully(self) -> None:
        cfg = {"color": "info"}
        result = admonition_icon(cfg)

        assert "<svg" in result
        assert isinstance(result, SafeString)


# ---------------------------------------------------------------------------
# c-admonition component (via markdown pipeline)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdmonitionComponent:
    """c-admonition renders through the full markdown pipeline."""

    @pytest.fixture
    def request_(self, site_aware_request):
        return site_aware_request.get("/")

    def test_known_type_renders_label_from_registry(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Body text</c-admonition>', request_
        )

        # The "Note" label from the registry must appear in the output
        assert "Note" in result

    def test_explicit_title_overrides_registry_label(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note" title="My Custom Title">Content</c-admonition>',
            request_,
        )

        assert "My Custom Title" in result

    def test_body_text_appears_in_output(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="tip">Important body content</c-admonition>', request_
        )

        assert "Important body content" in result

    def test_body_markdown_is_processed(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">This is **bold** text</c-admonition>',
            request_,
        )

        assert "<strong>bold</strong>" in result

    def test_icon_svg_is_rendered(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert "<svg" in result

    def test_unknown_type_falls_back_to_default_without_error(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="completely_unknown">Content</c-admonition>', request_
        )

        # Should not raise; body text must survive
        assert "Content" in result

    def test_returns_safe_string(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert isinstance(result, SafeString)

    def test_cotton_tag_not_in_output(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert "<c-admonition" not in result

    @pytest.mark.parametrize(
        ("admonition_type", "label"),
        [("tip", "Tip"), ("warning", "Warning"), ("danger", "Danger")],
    )
    def test_type_renders_its_registry_label_and_body(
        self, request_, admonition_type: str, label: str
    ) -> None:
        result = render_markdown(
            f'<c-admonition type="{admonition_type}">Body here</c-admonition>',
            request_,
        )

        assert label in result
        assert "Body here" in result

    def test_admonition_has_role_note_for_accessibility(self, request_) -> None:
        """Admonition renders with role="note" for screen reader accessibility."""
        result = render_markdown(
            '<c-admonition type="note">Note content</c-admonition>', request_
        )

        assert 'role="note"' in result

    def test_admonition_has_aria_labelledby(self, request_) -> None:
        """Admonition renders with aria-labelledby linking the heading to the container."""
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert "aria-labelledby" in result


# ---------------------------------------------------------------------------
# get_content_by_path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetContentByPath:
    """get_content_by_path resolves a path to a Topic, then falls back to a Form."""

    def test_empty_path_returns_none(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")

        assert get_content_by_path("", source) is None

    def test_matching_topic_is_returned(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")
        target = TopicFactory(file_path="4. topic/content.md")

        assert get_content_by_path("../4. topic/content.md", source) == target

    def test_matching_form_is_returned_when_no_topic_matches(
        self, mock_site_context
    ) -> None:
        """The Form fallback: no Topic carries the path, so the Form is found."""
        source = TopicFactory(file_path="2. topic/content.md")
        target = FormFactory(file_path="3. quiz/form.md")

        assert get_content_by_path("../3. quiz/form.md", source) == target

    def test_unknown_path_returns_none(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")

        assert get_content_by_path("01-what-is-git-for.md", source) is None

    def test_duplicate_forms_return_the_first(self, mock_site_context) -> None:
        """file_path is not unique, so a duplicated Form resolves to the first match."""
        source = TopicFactory(file_path="2. topic/content.md")
        FormFactory(file_path="3. quiz/form.md")
        FormFactory(file_path="3. quiz/form.md")

        expected = Form.objects.filter(file_path="3. quiz/form.md").first()

        assert get_content_by_path("../3. quiz/form.md", source) == expected


# ---------------------------------------------------------------------------
# get_published_article_by_path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetPublishedArticleByPath:
    """get_published_article_by_path resolves a path to a published Article on the content's site."""

    def test_published_target_is_returned(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")
        target = ArticleFactory(file_path="articles/target.md")

        assert get_published_article_by_path("../articles/target.md", source) == target

    def test_hidden_target_returns_none(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")
        ArticleFactory(
            file_path="articles/target.md", visibility=ArticleVisibility.HIDDEN
        )

        assert get_published_article_by_path("../articles/target.md", source) is None

    def test_missing_target_returns_none(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")

        assert get_published_article_by_path("../articles/nope.md", source) is None

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_empty_path_returns_none(self, mock_site_context, empty) -> None:
        source = TopicFactory(file_path="2. topic/content.md")

        assert get_published_article_by_path(empty, source) is None

    def test_same_path_on_another_site_returns_none(self, mock_site_context) -> None:
        source = TopicFactory(file_path="2. topic/content.md")
        other_site = SiteFactory()
        ArticleFactory(file_path="articles/target.md", site=other_site)

        assert get_published_article_by_path("../articles/target.md", source) is None
