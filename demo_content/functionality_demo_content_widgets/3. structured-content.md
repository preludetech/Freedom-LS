---
content_type: TOPIC
description: Tables and code blocks
subtitle: Laying out data and code so it reads cleanly
title: Structured Content
uuid: 81581ab3-3ecd-45da-bb28-84cc6ff369e2
---

## Tables

The table widget wraps a table in a focusable, horizontally scrollable region and adds an accessible `caption`. On narrow screens a wide table scrolls sideways instead of squashing its columns, and the caption names the region for screen readers.

The simplest form holds a GitHub-flavoured markdown table in the slot. Leave a blank line above and below the table so it parses:

<c-table caption="Plan comparison">

| Plan | Price | Seats |
|------|-------|-------|
| Free | 0     | 1     |
| Pro  | 10    | 5     |
| Team | 40    | 25    |

</c-table>

When you need fuller control over accessibility — explicit row and column headers — write raw HTML inside the slot instead. The `scope` attributes survive the sanitiser unchanged, so each header cell announces which row or column it governs:

<c-table caption="Feature comparison">
<table>
<thead><tr><th scope="col">Feature</th><th scope="col">Free</th><th scope="col">Pro</th></tr></thead>
<tbody>
<tr><th scope="row">Storage</th><td>1 GB</td><td>100 GB</td></tr>
<tr><th scope="row">Support</th><td>Community</td><td>Priority</td></tr>
<tr><th scope="row">Seats</th><td>1</td><td>5</td></tr>
</tbody>
</table>
</c-table>

## Code and log blocks

The code block shows preformatted text without syntax highlighting or a copy button — deliberately plain. Its slot is raw text, not markdown, so you must escape `<`, `>`, and `&` as `&lt;`, `&gt;`, and `&amp;` (and quotes inside the source as `&quot;`) so the sanitiser leaves them alone. Three optional attributes: `title` for a chrome label such as a filename, `language` for a display-only language tag, and `wrap` to wrap long lines instead of scrolling.

With a title and a language label:

<c-code-block title="deploy.sh" language="bash">echo "Deploying..."
if [ &quot;$count&quot; -gt 5 ]; then
    echo "More than five items"
fi</c-code-block>

By default a long line scrolls horizontally rather than wrapping, which keeps code readable:

<c-code-block title="query.py" language="python">queryset = Topic.objects.select_related("course").prefetch_related("activities").filter(course__site=current_site, published=True).order_by("course__title", "order").values_list("title", flat=True)</c-code-block>

For prose-like output such as logs, set `wrap="true"` so long lines fold instead of scrolling:

<c-code-block title="server.log" wrap="true">[2026-06-01 09:14:02] INFO  Request received for /courses/content-widgets/ from a learner session; rendering markdown, sanitising with nh3, then compiling cotton components before returning the response.</c-code-block>
