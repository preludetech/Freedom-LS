import pytest

from django.test import override_settings

from freedom_ls.icons.backend import DefaultIconBackend, _validate_svg_body

_backend = DefaultIconBackend()


def render_icon(
    semantic_name: str,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> str:
    return _backend.render(
        semantic_name, variant=variant, css_class=css_class, aria_label=aria_label
    )


class TestRenderIcon:
    def test_returns_svg_with_viewbox(self) -> None:
        result = render_icon("success")
        assert "<svg" in result
        assert 'viewBox="0 0 24 24"' in result
        assert "</svg>" in result

    def test_default_class(self) -> None:
        result = render_icon("success")
        assert 'class="inline size-5"' in result

    def test_custom_class(self) -> None:
        result = render_icon("success", css_class="size-6 text-red-500")
        assert 'class="inline size-6 text-red-500"' in result

    def test_default_aria_label_is_semantic_name(self) -> None:
        result = render_icon("success")
        assert 'aria-label="success"' in result

    def test_custom_aria_label(self) -> None:
        result = render_icon("success", aria_label="Done")
        assert 'aria-label="Done"' in result

    def test_role_is_img(self) -> None:
        result = render_icon("success")
        assert 'role="img"' in result

    def test_contains_svg_path_data(self) -> None:
        result = render_icon("success")
        assert "<path" in result

    def test_solid_variant_produces_different_output(self) -> None:
        outline = render_icon("success", variant="outline")
        solid = render_icon("success", variant="solid")
        assert outline != solid
        assert "<svg" in solid

    def test_missing_semantic_name_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            render_icon("nonexistent_icon_xyz")

    @override_settings(FREEDOM_LS_ICON_OVERRIDES={"success": "star"})
    def test_overrides_are_applied(self) -> None:
        result = render_icon("success")
        # "star" icon should be rendered instead of "check-circle"
        assert "<svg" in result
        # The body should be from the "star" icon, not "check-circle"
        normal = render_icon("next")  # unaffected
        assert result != normal

    @override_settings(FREEDOM_LS_ICON_SET="lucide")
    def test_lucide_icon_set(self) -> None:
        result = render_icon("success")
        assert "<svg" in result
        assert 'viewBox="0 0 24 24"' in result

    @override_settings(FREEDOM_LS_ICON_SET="tabler")
    def test_tabler_icon_set(self) -> None:
        result = render_icon("success")
        assert "<svg" in result

    @override_settings(FREEDOM_LS_ICON_SET="phosphor")
    def test_phosphor_icon_set(self) -> None:
        result = render_icon("success")
        assert "<svg" in result

    def test_aria_label_is_escaped(self) -> None:
        result = render_icon("success", aria_label='<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    @override_settings(FREEDOM_LS_ICON_SET="lucide")
    def test_unsupported_variant_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="not supported"):
            render_icon("success", variant="solid")


class TestValidateSvgBody:
    def test_clean_body_passes(self) -> None:
        body = '<path fill="none" stroke="currentColor" d="M9 12.75L11.25 15"/>'
        assert _validate_svg_body(body) == body

    def test_script_tag_rejected(self) -> None:
        with pytest.raises(ValueError, match="dangerous"):
            _validate_svg_body('<script>alert("xss")</script>')

    def test_foreign_object_rejected(self) -> None:
        with pytest.raises(ValueError, match="dangerous"):
            _validate_svg_body("<foreignObject>content</foreignObject>")

    def test_event_handler_rejected(self) -> None:
        with pytest.raises(ValueError, match="dangerous"):
            _validate_svg_body('<path onload="alert(1)" d="M0 0"/>')
