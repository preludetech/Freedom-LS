# Idea: the anonymous-hero test asserts FLS's own marketing copy, so every rebranded project fails it

## The bug

Source: running the downstream test gate
(`pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"`) in this
project. Reproduced identically at both `a690daf3` and `c43a3381` — not an upgrade regression.

```
FAILED freedom_ls/learner_interface/tests/test_anonymous_home_page.py
       ::test_anonymous_dashboard_contains_hero_headline
assert 'Teach the way your learners need' in body
```

The test asserts FLS's default hero headline verbatim. Overriding
`learner_interface/partials/anonymous_hero.html` is the documented, expected way for a concrete
project to put its own value proposition on its own home page — this project's override says "From
curiosity to career" — so the assertion fails for exactly the projects that used the extension point
correctly.

The marker taxonomy already exists for this. `pyproject.toml` registers `playwright`,
`fls_internal`, `ci_only` and `weasyprint`, and the downstream integration command describes the
selection as deselecting FLS's "browser tests, brand/demo-coupled tests, and slow-only tests". This
test is brand-coupled and carries no marker, so it lands in every downstream's gate. A downstream
cannot mark it either, because the file is inside the read-only submodule — the only escape is to
stop overriding the template, which defeats the point.

Worth checking whether other tests assert shipped copy in the same way; this is the one this
project happens to override.

## Expected fix

Mark `test_anonymous_dashboard_contains_hero_headline` `fls_internal`. If the intent is to test that
*a* hero renders rather than which words it contains, the more durable form is asserting on the
block's structure — a `data-testid` on the hero, say — and leaving the copy to whoever owns the
template.

## Sources

- `submodules/Freedom-LS/freedom_ls/learner_interface/tests/test_anonymous_home_page.py` — line 39.
- `templates/learner_interface/partials/anonymous_hero.html` — this project's override.
- `pyproject.toml` — the four registered markers and the `addopts` selection.
