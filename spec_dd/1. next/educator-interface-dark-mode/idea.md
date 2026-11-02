# Educator interface dark mode

**What:** a dark colour scheme for the educator interface, defined in the token sets of both shipped
themes (`default` and `first_class`): a dark value for every surface, text, border, status-tone
(`*-light` / `on-*-light`) and focus-ring token, switched by the visitor's `prefers-color-scheme`
and an explicit choice.

**Why:** neither theme has one. Every token in both `theme.css` files is a single light value, so an
educator who works in a dark room or has a system-wide dark setting gets a bright interface that
cannot follow it.

**Open questions:** whether the explicit choice is stored per user or per browser; whether the
learner interface gets the same tokens in the same pass; whether the contrast invariant test in
`freedom_ls/base/tests/invariants/test_theme_contrast.py` grows a dark pairing for every token pair
it checks.
