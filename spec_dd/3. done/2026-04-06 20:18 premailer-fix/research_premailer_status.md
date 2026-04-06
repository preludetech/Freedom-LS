# Research: Premailer Status and Fix Options

## Current State

- **django-premailer** v0.2.0 — last released 2016-06-20. Unmaintained. Provides a single Django template tag (`{% premailer %}...{% endpremailer %}`) that wraps the `premailer` library. Only 38 lines of code.
- **premailer** v3.0.0 installed — last released 2016-06-07. However, **premailer is still actively maintained** with latest version **3.10.0**.
- The `SyntaxWarning: invalid escape sequence '\s'` is at line 105 of premailer v3.0.0, in the regex `re.compile('\s*!important')` — uses `\s` in a regular string instead of a raw string `r'\s*...'`. Python 3.12+ emits `SyntaxWarning` for this; future Python versions will make it a `SyntaxError`.

## The Problem

The error is in the **premailer** library (not django-premailer). We're on premailer 3.0.0 but 3.10.0 is available and almost certainly fixes the invalid escape sequence.

The reason we're stuck on 3.0.0 is that **django-premailer 0.2.0** was released at the same time and its dependency on premailer may have been effectively pinned by the resolver to the version available at that time. However, checking the django-premailer metadata, it only requires `premailer` (no version pin), so upgrading premailer independently should work.

## Fix Options

### Option A: Upgrade premailer to 3.10.0 (simplest)

- `uv add "premailer>=3.10.0"` to force the upgrade
- django-premailer's API usage (`Premailer(html, **kwargs).transform()`) is the core public API — extremely unlikely to break between 3.0.0 and 3.10.0
- Fixes the `\s` warning since newer versions use raw strings
- **Risk:** Low. The `Premailer` class constructor and `.transform()` method are the stable public API
- **Effort:** Minimal — one dependency change + verify emails still render

### Option B: Replace django-premailer with our own template tag

- django-premailer is only 38 lines. We could copy the template tag into our own codebase and depend on `premailer` directly
- Removes the unmaintained django-premailer dependency entirely
- We'd control the code and could update the premailer version freely
- **Risk:** Low. The template tag code is trivial
- **Effort:** Small — create template tag, update template, remove django-premailer from deps

### Option C: Replace premailer entirely with css-inline

- `css-inline` is a modern Rust-based CSS inlining library with Python bindings
- Much faster than premailer (Rust performance)
- Actively maintained
- Would require writing our own template tag (similar to Option B)
- **Risk:** Medium. Different library may handle edge cases differently
- **Effort:** Medium — need to verify email output matches current behavior

## Recommendation

**Option A** is the fastest fix for the immediate production warning. Option B is worth considering as a follow-up to fully remove the unmaintained dependency.

If Option A doesn't fix the warning (unlikely), fall back to Option B.

## References

- django-premailer PyPI: https://pypi.org/project/django-premailer/
- django-premailer GitHub: https://github.com/alexhayes/django-premailer
- premailer PyPI: https://pypi.org/project/premailer/
- premailer GitHub: https://github.com/peterbe/premailer
- css-inline: https://pypi.org/project/css-inline/
