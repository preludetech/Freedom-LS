"""Tests for markdown_utils.py - focusing on custom cotton tag functionality."""

import pytest
from django.utils.safestring import SafeString

from freedom_ls.content_engine.markdown_utils import render_markdown


@pytest.fixture
def mock_request(site_aware_request):
    """Create a mock request object."""
    return site_aware_request.get("/")


@pytest.mark.django_db
class TestRenderMarkdownCustomTags:
    """Tests for custom cotton tag handling in render_markdown."""

    def test_c_youtube_tag_is_rendered(self, mock_request):
        """Test that c-youtube custom tag is rendered to iframe."""
        markdown_text = """
        BEFORE
        <c-youtube video_id="dQw4w9WgXcQ"></c-youtube>
        AFTER
        """
        result = render_markdown(markdown_text, mock_request)

        assert isinstance(result, SafeString)
        # Should be rendered by cotton component to an iframe
        assert "iframe" in result
        assert "youtube.com/embed/dQw4w9WgXcQ" in result
        assert "BEFORE" in result
        assert "AFTER" in result

    def test_c_youtube_with_title(self, mock_request):
        """Test that c-youtube with title attribute works."""
        markdown_text = (
            '<c-youtube video_id="abc123" video_title="Test Video"></c-youtube>'
        )
        result = render_markdown(markdown_text, mock_request)

        assert "iframe" in result
        assert "youtube.com/embed/abc123" in result
        assert "Test Video" in result

    def test_c_callout_info_is_rendered(self, mock_request):
        """Test that c-callout with info level is rendered."""
        markdown_text = '<c-callout level="info">Important information</c-callout>'
        result = render_markdown(markdown_text, mock_request)

        # Should be rendered by callout component
        assert "bg-blue-50" in result  # Info styling
        assert "border-blue-400" in result
        assert "Important information" in result

    def test_c_callout_warning_is_rendered(self, mock_request):
        """Test that c-callout with warning level is rendered."""
        markdown_text = '<c-callout level="warning">Warning text</c-callout>'
        result = render_markdown(markdown_text, mock_request)

        assert "bg-yellow-50" in result  # Warning styling
        assert "border-yellow-400" in result
        assert "Warning text" in result

    def test_c_callout_with_title(self, mock_request):
        """Test that c-callout with title attribute works."""
        markdown_text = '<c-callout level="info" title="Note">Content here</c-callout>'
        result = render_markdown(markdown_text, mock_request)

        assert "Note" in result
        assert "Content here" in result
        assert "fa-info-circle" in result

    def test_c_callout_with_markdown_content(self, mock_request):
        """Test that markdown inside c-callout is processed."""
        markdown_text = """<c-callout level="info">
This is **bold** text
</c-callout>"""
        result = render_markdown(markdown_text, mock_request)

        assert "<strong>bold</strong>" in result
        assert "bg-blue-50" in result

    def test_disallowed_script_tag_is_stripped(self, mock_request):
        """Test that script tags are stripped for security."""
        markdown_text = '<script>alert("xss")</script>Content'
        result = render_markdown(markdown_text, mock_request)

        assert "<script>" not in result
        assert "alert" not in result
        assert "Content" in result

    def test_disallowed_iframe_tag_is_stripped(self, mock_request):
        """Test that raw iframe tags (not from c-youtube) are stripped."""
        markdown_text = '<iframe src="evil.com"></iframe>Text'
        result = render_markdown(markdown_text, mock_request)

        # Direct iframe tags should be stripped
        # Only iframes from cotton components should be allowed
        assert "evil.com" not in result
        assert "Text" in result

    def test_disallowed_custom_tag_is_stripped(self, mock_request):
        """Test that non-whitelisted custom tags are stripped."""
        markdown_text = "<c-evil>Bad content</c-evil>"
        result = render_markdown(markdown_text, mock_request)

        assert "<c-evil" not in result
        assert "c-evil" not in result
        assert "Bad content" in result

    def test_mixed_markdown_and_cotton_tags(self, mock_request):
        """Test that markdown and cotton tags work together."""
        markdown_text = """# Tutorial

<c-youtube video_id="abc123"></c-youtube>

Some text with **bold**."""
        result = render_markdown(markdown_text, mock_request)

        # Should have both markdown rendered and cotton component rendered
        assert "Tutorial" in result  # Heading rendered
        assert "iframe" in result  # c-youtube rendered
        assert "youtube.com/embed/abc123" in result
        assert "<strong>bold</strong>" in result

    def test_multiple_cotton_tags(self, mock_request):
        """Test that multiple cotton tags in one document work."""
        markdown_text = """<c-callout level="info">First callout</c-callout>

<c-youtube video_id="test"></c-youtube>

<c-callout level="warning">Second callout</c-callout>"""
        result = render_markdown(markdown_text, mock_request)

        assert "First callout" in result
        assert "Second callout" in result
        assert "bg-blue-50" in result  # Info callout
        assert "bg-yellow-50" in result  # Warning callout
        assert "youtube.com/embed/test" in result

    def test_returns_safe_string(self, mock_request):
        """Test that result is marked as safe HTML."""
        markdown_text = "# Test"
        result = render_markdown(markdown_text, mock_request)

        assert isinstance(result, SafeString)

    def test_empty_string(self, mock_request):
        """Test that empty string is handled."""
        result = render_markdown("", mock_request)

        assert result == ""

    def test_blockquote_rendering(self, mock_request):
        """Test that blockquote rendering works."""
        markdown_text = "> This is a blockquote"
        result = render_markdown(markdown_text, mock_request)
        assert "<blockquote>" in result
        assert "This is a blockquote" in result

    def test_table_rendering(self, mock_request):
        """Test that table rendering works."""
        markdown_text = """
    | Header 1 | Header 2 |
    |----------|----------|
    | Cell 1   | Cell 2   |
    """
        result = render_markdown(markdown_text, mock_request)
        assert "<table>" in result
        assert "<th>Header 1</th>" in result
