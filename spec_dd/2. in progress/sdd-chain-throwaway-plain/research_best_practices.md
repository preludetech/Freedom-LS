# Research: best practices for small display-formatting helpers

Scope: `format_duration(seconds)` -> `1h 02m`, `format_score(earned, possible)` -> `7 / 10`.
Based on general Python/Django practice (no web lookups were made; no URLs cited).

## Design
- Keep helpers pure: no I/O, no Django model access, return `str`, no side effects.
- Full type hints, no `Any`: `def format_duration(seconds: int) -> str`, `def format_score(earned: int, possible: int) -> str`.
- Use integer arithmetic: `hours, rem = divmod(seconds, 3600)`; `minutes = rem // 60`. Floor, do not round, so 3599s never shows as `1h 00m`.
- Format with f-strings: `f"{hours}h {minutes:02d}m"`. Hours are not zero-padded and do not wrap at 24.
- Keep each helper in its own module with a one-line docstring stating the floor and edge behaviour.

## Input validation
- Type hints do not enforce anything at runtime. Decide explicitly what to do with bad input.
- Negative values: raise `ValueError` rather than render `-1h -5m` (a display helper should not hide bad data). Same for negative `earned` or `possible`.
- Floats: either declare `int` and reject non-ints with `TypeError`, or accept `float` and floor with `int()`. Pick one and test it. Avoid silently truncating `NaN`/`inf`: `int(float("nan"))` raises `ValueError`, `inf` raises `OverflowError`.
- `None`: not handled inside the helper. Callers (templates or views) decide the placeholder. This avoids a hidden `"-"` convention. Passing `None` raises `TypeError` naturally.
- `bool` is an `int` subclass. Reject it only if that matters (probably not for a throwaway).
- Catch specific exceptions only, never a bare `except`. No silent failure.
- Decisions already made (answers.md): under one minute renders `0h 00m`; `possible == 0` renders `0 / 0` with no division.

## i18n
- Unit letters `h`/`m` and the `/` separator are English/ASCII conventions. For Django i18n, wrap the format string in `gettext_lazy` or `gettext` if localisation is needed, e.g. `_("%(h)dh %(m)02dm")` with named placeholders so translators can reorder.
- Number localisation (`django.utils.formats.number_format`) is not needed for small integers in this format.
- For a throwaway helper, note i18n as out of scope rather than half-implementing it. The project says not to build unrequested functionality.

## Testing
- Use `pytest.mark.parametrize` with `(input, expected)` ids. Cover boundaries: `0`, `59`, `60`, `3599`, `3600`, `3720`, large values (`100000`), and `0 / 0`, `0 / 10`, `10 / 10`, `earned > possible` (render as given).
- Invalid-input cases get a separate parametrised `pytest.raises(ValueError/TypeError)` test, including negatives, `None` and floats.
- Plain pytest functions, no DB fixtures. Mark nothing as `django_db`.
- One test file per helper, beside its app's other tests.

status: ok
