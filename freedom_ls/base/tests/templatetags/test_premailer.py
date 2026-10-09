from django.template import Context, Template
from django.test import override_settings


def test_premailer_tag_inlines_css():
    template = Template(
        "{% load premailer %}{% premailer %}<style>p { color: red; }</style><p>Hello</p>{% endpremailer %}"
    )
    result = template.render(Context({}))
    assert "style=" in result
    assert "color" in result


def test_premailer_tag_reads_settings_options():
    with override_settings(PREMAILER_OPTIONS={"remove_classes": True}):
        template = Template(
            '{% load premailer %}{% premailer %}<style>.foo { color: blue; }</style><p class="foo">Hello</p>{% endpremailer %}'
        )
        result = template.render(Context({}))
        assert "class=" not in result


def test_premailer_tag_renders_inner_content():
    template = Template(
        "{% load premailer %}{% premailer %}<p>{{ greeting }}</p>{% endpremailer %}"
    )
    result = template.render(Context({"greeting": "Hello World"}))
    assert "Hello World" in result
