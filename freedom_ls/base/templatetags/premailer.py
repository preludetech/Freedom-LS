from premailer import Premailer

from django import template
from django.conf import settings

register = template.Library()


class PremailerNode(template.Node):
    def __init__(
        self,
        nodelist: template.NodeList,
        filter_expressions: list[template.base.FilterExpression],
    ) -> None:
        self.nodelist = nodelist
        self.filter_expressions = filter_expressions

    def render(self, context: template.Context) -> str:
        rendered_contents = self.nodelist.render(context)
        kwargs: dict[str, object] = getattr(settings, "PREMAILER_OPTIONS", {}).copy()
        for expression in self.filter_expressions:
            kwargs.update(base_url=expression.resolve(context, True))
        result: str = Premailer(rendered_contents, **kwargs).transform()
        return result


@register.tag
def premailer(
    parser: template.base.Parser, token: template.base.Token
) -> PremailerNode:
    nodelist = parser.parse(("endpremailer",))
    parser.delete_first_token()
    args = token.split_contents()[1:]
    return PremailerNode(nodelist, [parser.compile_filter(arg) for arg in args])
