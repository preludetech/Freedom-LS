# Idea: referral links 404 when the URL has a trailing slash

## The bug

Source: production, First Class (`https://learn.firstclass.training`), FLS `0d1d4d02`.

A referral code `farm` was set up and handed out as a link. These two URLs should behave
the same:

- `https://learn.firstclass.training/go/farm` redirects correctly
- `https://learn.firstclass.training/go/farm/` returns 404

The routes in `freedom_ls/referral_tracking/urls.py` end at the code:

```python
re_path(
    rf"^[gG][oO]/(?P<code>{CODE_PATTERN.pattern})$",
    follow_referral_code,
    {"door": Door.GO},
    name="follow_go",
),
re_path(
    rf"^[dD]/(?P<code>{CODE_PATTERN.pattern})$",
    ...
),
```

`CODE_PATTERN` is `[A-Za-z0-9-]{1,64}`, so a trailing `/` matches nothing. Django's
`APPEND_SLASH` doesn't help, because it only adds a missing slash and never removes an
extra one. The request falls through to the learner interface and 404s.

Referral links get typed by hand, pasted from printed material, and autocompleted by
browsers and chat apps, and all of those add trailing slashes. A 404 loses both the
visitor and the hit, so the referral is never attributed. Both doors (`/go/` and `/d/`)
have the bug.

## Expected fix

Accept an optional trailing slash on both routes and handle it the same as the
slashless form: same view, same door, same hit recorded, same redirect target, query
string preserved.

```python
rf"^[gG][oO]/(?P<code>{CODE_PATTERN.pattern})/?$"
rf"^[dD]/(?P<code>{CODE_PATTERN.pattern})/?$"
```

Points to check:

- `reverse("referral_tracking:follow_go", ...)` must still produce the slashless URL.
  `/?` is reversible in Django (it drops the optional part). Add a test to confirm.
- One request should give one redirect, not a 301 to the slashless URL followed by the
  referral redirect. `test_the_response_has_no_trailing_slash_redirect_hop` already
  asserts this for the slashless form. Extend it to cover the slashed form.
- Answer the slashed form directly instead of redirecting it to the canonical URL. A
  redirect adds a hop, and the response is already `noindex` and `no-store`, so a
  canonical URL has nothing to protect.

## Tests

In `freedom_ls/referral_tracking/tests/test_views.py`:

- Extend `_spellings` (or add a parametrised test) to cover `/go/{code}/`, `/GO/{CODE}/`,
  `/d/{code}/` and `/D/{CODE}/`. Each should redirect to the same target as the
  slashless forms, record a hit with the right door, and keep the query string.
- `/go/{code}//` and `/go/{code}/extra` still 404.

## Downstream

First Class works around this in `config/urls.py` with two extra `re_path`s that match
`.../<code>/$` and call `follow_referral_code` directly. Tests are in
`tests/test_referral_trailing_slash.py`. Remove both once the submodule includes this
fix. The upgrade notes should tell downstreams to drop any similar shim.
