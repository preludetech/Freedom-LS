type JSONValue = (
    str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]
)
