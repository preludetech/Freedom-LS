# Idea: the header's site name is an `<h1>`, so every page has two, and there is no skip link

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (DISC-7, APP-9, LEARN-15).

Open any page that uses the standard header (dashboard, course detail, player, application
pages) and list the `h1` elements. There are two: the site name ("First Class") and the page's
own heading, e.g. "Your details". Screen-reader heading navigation starts at the site name. At
phone width with a header logo the site-name `h1` is `hidden`, so there it is one.

There is also no "skip to content" link. A keyboard user tabs through the whole header on every
page.

## Cause

`freedom_ls/base/templates/partials/header_bar.html:13-16` wraps `{{ header_title }}` in `<h1>`.
`freedom_ls/base/templates/_base.html` includes the header (`:118`) and then opens `<main>`
(`:124`) with no skip link in front.

## Suggested fix

- Render the site name as a `<span>` (or `<p>`) with the same classes. The link already has the
  logo's alt text or the name as its accessible name.
- Add a visually hidden, focusable "Skip to content" link as the first child of `<body>`,
  targeting an `id` on `<main>`.

## Downstream workaround

The project's own `templates/partials/header_bar.html` uses a `<span>` for the site name. No skip
link yet.
