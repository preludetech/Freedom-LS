from rest_framework.routers import Route, SimpleRouter


class ApiRouter(SimpleRouter):
    # SimpleRouter's two routes with snake_case names, so reverse("api:user_list")
    # matches the project's URL-name convention.
    routes = [
        Route(
            url=r"^{prefix}{trailing_slash}$",
            mapping={"get": "list"},
            name="{basename}_list",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
        Route(
            url=r"^{prefix}/{lookup}{trailing_slash}$",
            mapping={"get": "retrieve"},
            name="{basename}_detail",
            detail=True,
            initkwargs={"suffix": "Instance"},
        ),
    ]


router = ApiRouter()
