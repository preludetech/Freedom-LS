"""Tests for markdown_utils.py - focusing on custom cotton tag functionality."""

import pytest

from django.test import override_settings
from django.utils.safestring import SafeString

from freedom_ls.markdown_rendering.markdown_utils import render_markdown


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

    @pytest.mark.parametrize("level", ["info", "warning", "error", "success"])
    def test_c_callout_renders_body_for_each_level(self, mock_request, level):
        """The c-callout cotton tag is processed (replaced by HTML) at every level."""
        markdown_text = f'<c-callout level="{level}">Body text {level}</c-callout>'
        result = render_markdown(markdown_text, mock_request)

        assert "<c-callout" not in result  # cotton tag was rendered, not literal
        assert f"Body text {level}" in result

    def test_c_callout_with_title(self, mock_request):
        """Test that c-callout with title attribute works."""
        markdown_text = '<c-callout level="info" title="Note">Content here</c-callout>'
        result = render_markdown(markdown_text, mock_request)

        assert "<c-callout" not in result
        assert "Note" in result
        assert "Content here" in result
        assert "<svg" in result  # Icon rendered as inline SVG

    def test_c_callout_with_markdown_content(self, mock_request):
        """Test that markdown inside c-callout is processed."""
        markdown_text = """<c-callout level="info">
This is **bold** text
</c-callout>"""
        result = render_markdown(markdown_text, mock_request)

        assert "<strong>bold</strong>" in result

    def test_c_youtube_with_caption_renders_figcaption(self, mock_request):
        """c-youtube with a caption wraps the embed in a figure with a figcaption."""
        markdown_text = (
            '<c-youtube video_id="abc123" caption="A helpful clip"></c-youtube>'
        )
        result = render_markdown(markdown_text, mock_request)

        assert "iframe" in result
        assert "youtube.com/embed/abc123" in result
        assert "<figure" in result
        assert "<figcaption" in result
        assert "A helpful clip" in result

    def test_c_youtube_without_caption_has_no_figcaption(self, mock_request):
        """The self-closing c-youtube (no caption) still renders the iframe and no figcaption."""
        markdown_text = '<c-youtube video_id="dQw4w9WgXcQ" />'
        result = render_markdown(markdown_text, mock_request)

        assert "iframe" in result
        assert "youtube.com/embed/dQw4w9WgXcQ" in result
        assert "<figcaption" not in result

    def test_c_pull_quote_renders_figure_and_blockquote(self, mock_request):
        """c-pull-quote renders a figure containing a blockquote."""
        markdown_text = "<c-pull-quote>The only way out is through.</c-pull-quote>"
        result = render_markdown(markdown_text, mock_request)

        assert "<c-pull-quote" not in result  # cotton tag was rendered
        assert "<figure" in result
        assert "<blockquote" in result
        assert "The only way out is through." in result

    def test_c_pull_quote_emits_attribution_and_source(self, mock_request):
        """Attribution and source text both appear in the rendered output."""
        markdown_text = (
            '<c-pull-quote attribution="Robert Frost" source="A Servant to Servants">'
            "The only way out is through."
            "</c-pull-quote>"
        )
        result = render_markdown(markdown_text, mock_request)

        assert "Robert Frost" in result
        assert "A Servant to Servants" in result

    def test_c_pull_quote_cite_wraps_only_source_not_attribution(self, mock_request):
        """<cite> wraps the work title (source) only, never the person (attribution)."""
        markdown_text = (
            '<c-pull-quote attribution="Robert Frost" source="A Servant to Servants">'
            "The only way out is through."
            "</c-pull-quote>"
        )
        result = render_markdown(markdown_text, mock_request)

        assert "<cite>A Servant to Servants</cite>" in result
        assert "<cite>Robert Frost" not in result

    def test_c_pull_quote_body_markdown_is_processed(self, mock_request):
        """Markdown in the pull-quote body is rendered (e.g. bold)."""
        markdown_text = "<c-pull-quote>This is **bold** advice.</c-pull-quote>"
        result = render_markdown(markdown_text, mock_request)

        assert "<strong>bold</strong>" in result

    def test_c_pull_quote_cite_url_sets_blockquote_cite_attribute(self, mock_request):
        """A cite URL is emitted as the blockquote cite attribute."""
        markdown_text = (
            '<c-pull-quote cite="https://example.com/poem">'
            "The only way out is through."
            "</c-pull-quote>"
        )
        result = render_markdown(markdown_text, mock_request)

        assert 'cite="https://example.com/poem"' in result

    def test_c_pull_quote_javascript_cite_is_not_a_usable_link(self, mock_request):
        """A javascript: scheme in cite must not be emitted as a usable script link."""
        markdown_text = (
            '<c-pull-quote cite="javascript:alert(1)">Suspicious quote.</c-pull-quote>'
        )
        result = render_markdown(markdown_text, mock_request)

        # The javascript: payload must not survive as an executable href/cite.
        assert "javascript:alert(1)" not in result
        assert "Suspicious quote." in result

    def test_c_pull_quote_malformed_cite_does_not_crash(self, mock_request):
        """A malformed cite URL fails closed (no cite attr) without raising."""
        markdown_text = '<c-pull-quote cite="http://[::1">Words.</c-pull-quote>'
        result = render_markdown(markdown_text, mock_request)

        assert "<blockquote" in result
        assert "Words." in result
        assert "[::1" not in result

    def test_c_pull_quote_without_attribution_still_renders(self, mock_request):
        """A bare pull-quote (no attribution/source) still renders figure and blockquote."""
        markdown_text = "<c-pull-quote>Just the words.</c-pull-quote>"
        result = render_markdown(markdown_text, mock_request)

        assert "<figure" in result
        assert "<blockquote" in result
        assert "Just the words." in result
        assert "<figcaption" not in result

    def test_c_pull_quote_unknown_attribute_is_stripped(self, mock_request):
        """An attribute not on the allow list for c-pull-quote is stripped."""
        markdown_text = '<c-pull-quote onclick="alert(1)">Words.</c-pull-quote>'
        result = render_markdown(markdown_text, mock_request)

        assert "onclick" not in result
        assert "alert(1)" not in result
        assert "Words." in result

    def test_c_equation_renders_container_with_latex_source(self, mock_request):
        """c-equation renders a role=math container holding the LaTeX as text."""
        markdown_text = "<c-equation>E = mc^2</c-equation>"
        result = render_markdown(markdown_text, mock_request)

        assert "<c-equation" not in result  # cotton tag rendered
        assert 'x-data="equation"' in result
        assert 'role="math"' in result
        assert "E = mc^2" in result  # LaTeX source present as text

    def test_c_equation_without_label_has_generic_aria_label(self, mock_request):
        """Without a label the accessible name is the generic 'Equation'."""
        markdown_text = "<c-equation>a + b</c-equation>"
        result = render_markdown(markdown_text, mock_request)

        assert 'aria-label="Equation"' in result

    def test_c_equation_with_label_renders_label(self, mock_request):
        """A label drives both the accessible name and a visible reference."""
        markdown_text = '<c-equation label="3">a + b</c-equation>'
        result = render_markdown(markdown_text, mock_request)

        assert 'aria-label="Equation 3"' in result
        assert "(3)" in result

    def test_c_equation_unknown_attribute_is_stripped(self, mock_request):
        """An attribute not on the allow list for c-equation is stripped."""
        markdown_text = '<c-equation onclick="alert(1)">a</c-equation>'
        result = render_markdown(markdown_text, mock_request)

        assert "onclick" not in result
        assert "alert(1)" not in result

    def _make_image_file(self, site, file_path="images/cat.png"):
        """Create a site-scoped File row so c-picture can resolve it."""
        from freedom_ls.content_engine.models import File

        return File.objects.create(
            site=site,
            file=file_path,
            file_path=file_path,
            original_filename="cat.png",
            file_type=File.FileType.IMAGE,
        )

    def test_c_picture_lightbox_trigger_is_a_button(self, mock_request, site):
        """Regression: the lightbox trigger is a real keyboard-accessible button.

        (Replaces the old non-keyboard ``<img @click>`` thumbnail.)
        """
        self._make_image_file(site)

        class FakeInstance:
            def calculate_path_from_root(self, path):
                return path

        markdown_text = '<c-picture src="images/cat.png" alt="A cat" />'
        result = render_markdown(
            markdown_text, mock_request, context={"content_instance": FakeInstance()}
        )

        assert "<button" in result
        assert 'type="button"' in result
        assert "contentLightbox" in result
        assert "<dialog" in result

    def test_c_picture_number_renders_figure_prefix(self, mock_request, site):
        """A number and title attribute survive sanitising and render a 'Figure N' prefix."""
        self._make_image_file(site)

        class FakeInstance:
            def calculate_path_from_root(self, path):
                return path

        markdown_text = (
            '<c-picture src="images/cat.png" alt="A cat" number="2" '
            'title="Propeller diagram" />'
        )
        result = render_markdown(
            markdown_text, mock_request, context={"content_instance": FakeInstance()}
        )

        assert "Figure 2" in result
        # Distinct from alt="A cat" so this proves the title rendered in chrome.
        assert "Propeller diagram" in result

    @override_settings(MARKDOWN_TEMPLATE_RENDER_ON=False)
    def test_c_picture_description_attr_survives_sanitising(self, mock_request):
        """title and description attributes on c-picture survive the markdown sanitiser.

        Uses MARKDOWN_TEMPLATE_RENDER_ON=False to inspect the sanitised output
        before cotton template rendering — this is the layer that must pass
        the attributes through unchanged.
        """
        markdown_text = (
            '<c-picture src="images/cat.png" alt="A cat"'
            ' title="Fluffy cat" description="A fluffy tabby cat sitting on a mat." />'
        )
        result = render_markdown(markdown_text, mock_request)

        assert 'title="Fluffy cat"' in result
        assert 'description="A fluffy tabby cat sitting on a mat."' in result

    def test_c_picture_missing_file_shows_error_fallback(self, mock_request, site):
        """An unresolved src renders the 'Image not found' fallback, not a crash."""

        class FakeInstance:
            def calculate_path_from_root(self, path):
                return path

        markdown_text = '<c-picture src="nope.png" alt="x" />'
        result = render_markdown(
            markdown_text, mock_request, context={"content_instance": FakeInstance()}
        )

        assert "Image not found" in result
        assert "<button" not in result

    def test_c_code_block_renders_pre_code_and_preserves_entities(self, mock_request):
        """c-code-block renders <pre><code> and keeps author-escaped entities."""
        markdown_text = (
            "<c-code-block>def f():\n    return &lt;tag&gt; &amp; x</c-code-block>"
        )
        result = render_markdown(markdown_text, mock_request)

        assert "<c-code-block" not in result
        assert "<pre" in result
        assert "<code>" in result
        # Author-escaped entities survive verbatim (render as literal < > &).
        assert "&lt;tag&gt;" in result
        assert "&amp; x" in result

    def test_c_code_block_renders_title_and_language(self, mock_request):
        """title and language appear in the code-block chrome."""
        markdown_text = (
            '<c-code-block title="app.py" language="python">x = 1</c-code-block>'
        )
        result = render_markdown(markdown_text, mock_request)

        assert "app.py" in result
        assert "python" in result

    def test_c_code_block_wrap_toggles_wrapping(self, mock_request):
        """The wrap attribute is the functional toggle for line wrapping."""
        wrapped = render_markdown(
            '<c-code-block wrap="true">long line</c-code-block>', mock_request
        )
        unwrapped = render_markdown(
            "<c-code-block>long line</c-code-block>", mock_request
        )

        assert "whitespace-pre-wrap" in wrapped
        assert "whitespace-pre-wrap" not in unwrapped

    def test_c_table_renders_table_with_injected_caption(self, mock_request):
        """c-table renders a markdown table with a spliced-in caption."""
        markdown_text = (
            '<c-table caption="Plan comparison">\n'
            "| Plan | Price |\n"
            "|------|-------|\n"
            "| Free | 0 |\n"
            "</c-table>"
        )
        result = render_markdown(markdown_text, mock_request)

        assert "<table" in result
        assert "<caption" in result
        assert "Plan comparison" in result
        # Caption is the first child of the table.
        assert result.index("<table") < result.index("<caption") < result.index("<th")

    def test_c_table_without_caption_still_renders_table(self, mock_request):
        """A caption-less c-table renders the table and no <caption>."""
        markdown_text = "<c-table>\n| A | B |\n|---|---|\n| 1 | 2 |\n</c-table>"
        result = render_markdown(markdown_text, mock_request)

        assert "<table" in result
        assert "<caption" not in result

    def test_c_image_grid_preserves_nested_picture_lightbox(self, mock_request, site):
        """The grid wrapper preserves each nested c-picture's lightbox button."""
        self._make_image_file(site, "images/a.png")
        self._make_image_file(site, "images/b.png")

        class FakeInstance:
            def calculate_path_from_root(self, path):
                return path

        # The ![[...]] shorthand rewrites to this non-self-closing form, which
        # is the realistic authoring shape for a grid of pictures.
        markdown_text = (
            '<c-image-grid columns="2">\n\n'
            '<c-picture src="images/a.png" alt="A"></c-picture>\n\n'
            '<c-picture src="images/b.png" alt="B"></c-picture>\n\n'
            "</c-image-grid>"
        )
        result = render_markdown(
            markdown_text, mock_request, context={"content_instance": FakeInstance()}
        )

        # Both nested pictures rendered with their keyboard-accessible lightbox
        # preserved (the grid uses {{ slot }}, so the rendered c-picture HTML is
        # not re-sanitised).
        assert result.count("contentLightbox") == 2
        assert result.count('type="button"') >= 2

    def test_c_image_grid_unknown_columns_falls_back_without_injection(
        self, mock_request
    ):
        """An out-of-whitelist columns value never injects into the class string."""
        markdown_text = '<c-image-grid columns="99">content</c-image-grid>'
        result = render_markdown(markdown_text, mock_request)

        assert "<c-image-grid" not in result  # rendered
        assert "99" not in result  # author value never reached the markup
        assert "content" in result

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

        assert "<c-callout" not in result  # both callouts processed
        assert "First callout" in result
        assert "Second callout" in result
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

    def test_context_variable_is_rendered(self, mock_request):
        """Context vars passed to render_markdown are substituted into the output.

        Production callers (e.g. MarkdownContent.rendered_content) pass a
        context dict, so the template engine must process Django variables.
        """
        markdown_text = "Hello {{ name }}!"
        result = render_markdown(markdown_text, mock_request, context={"name": "Alice"})

        assert "Hello Alice!" in result
        assert "{{ name }}" not in result

    def test_context_object_attribute_is_rendered(self, mock_request):
        """Dotted attribute access on context objects works (mirrors MarkdownContent usage)."""

        class FakeInstance:
            title = "My Topic"

        markdown_text = "Title: {{ content_instance.title }}"
        result = render_markdown(
            markdown_text, mock_request, context={"content_instance": FakeInstance()}
        )

        assert "Title: My Topic" in result

    @override_settings(MARKDOWN_TEMPLATE_RENDER_ON=False)
    def test_render_off_skips_template_processing(self, mock_request):
        """When the flag is off, output is sanitised markdown without template processing.

        Cotton tags and Django variables should pass through unprocessed but the
        output must still be a SafeString and XSS must still be stripped.
        """
        markdown_text = (
            'Hello {{ name }} <c-youtube video_id="abc"></c-youtube>'
            '<script>alert("x")</script>'
        )
        result = render_markdown(markdown_text, mock_request, context={"name": "Bob"})

        assert isinstance(result, SafeString)
        assert "{{ name }}" in result
        assert "<script>" not in result
        assert "iframe" not in result

    def test_raw_html_table_scope_survives_sanitiser(self, mock_request):
        """A raw HTML table with scope/th survives the outer sanitiser.

        The comparison-table demo authors raw <table> markup with explicit
        scope= attributes; nh3's defaults keep scope on th/td, so this needs
        no settings change (success criterion: tables have caption + scope).
        """
        markdown_text = (
            "<table>\n"
            "<caption>Comparison</caption>\n"
            '<tr><th scope="col">Feature</th><th scope="col">A</th></tr>\n'
            '<tr><th scope="row">Speed</th><td>Fast</td></tr>\n'
            "</table>"
        )
        result = render_markdown(markdown_text, mock_request)

        assert 'scope="col"' in result
        assert 'scope="row"' in result
        assert "<caption>Comparison</caption>" in result


class TestInjectTableCaption:
    """Unit tests for the inject_table_caption filter."""

    def test_no_table_returns_input_unchanged(self):
        from freedom_ls.content_engine.templatetags.content_tags import (
            inject_table_caption,
        )

        html = "<p>No table here</p>"
        result = inject_table_caption(html, "My caption")

        assert result == html
        assert "<caption" not in result

    def test_empty_caption_is_a_no_op(self):
        from freedom_ls.content_engine.templatetags.content_tags import (
            inject_table_caption,
        )

        html = "<table><tr><td>1</td></tr></table>"
        result = inject_table_caption(html, "")

        assert result == html

    def test_caption_is_escaped(self):
        from freedom_ls.content_engine.templatetags.content_tags import (
            inject_table_caption,
        )

        html = "<table><tr><td>1</td></tr></table>"
        result = inject_table_caption(html, '<script>alert("x")</script>')

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_caption_inserted_as_first_table_child(self):
        from freedom_ls.content_engine.templatetags.content_tags import (
            inject_table_caption,
        )

        html = "<table><thead></thead></table>"
        result = inject_table_caption(html, "Cap")

        assert (
            result.index("<table") < result.index("<caption") < result.index("<thead")
        )
