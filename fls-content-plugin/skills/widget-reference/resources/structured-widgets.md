<!-- Source: config/settings_base.py (MARKDOWN_ALLOWED_TAGS), freedom_ls/content_engine/templates/cotton/table.html, code-block.html, pull-quote.html, equation.html, research_authoring_format.md §3 -->

# Structured Widgets

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

---

## `c-table`

Accessible, horizontally scrollable table wrapper.

**Allowed attributes:** `caption`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `caption` | No | `""` | Accessible caption; also names the scroll region for screen readers |

The slot content is markdown-rendered (GFM table syntax supported). Leave a blank line above and below the table inside the tag.

```markdown
<c-table caption="Pricing plan comparison">

| Plan | Price | Features |
|------|-------|----------|
| Free | £0    | Basic    |
| Pro  | £9/mo | Advanced |

</c-table>
```

Raw HTML tables with `scope` attributes are also supported inside the slot.

---

## `c-code-block`

Preformatted code or log output. No syntax highlighting, no copy button. Content is **not** markdown-processed.

**Allowed attributes:** `title`, `language`, `wrap`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `title` | No | `""` | Chrome label (e.g. filename or context) |
| `language` | No | `""` | Display-only language tag (e.g. `"bash"`, `"python"`) |
| `wrap` | No | `""` | Any value enables line-wrapping instead of horizontal scroll |

**HTML-escaping is required.** The slot content passes through the nh3 sanitiser as raw text — you must escape:

| Character | Escape as |
|---|---|
| `<` | `&lt;` |
| `>` | `&gt;` |
| `&` | `&amp;` |
| `"` | `&quot;` |

```markdown
<c-code-block title="deploy.sh" language="bash">#!/bin/bash
echo "Deploying..."
if [ &quot;$count&quot; -gt 5 ]; then
    echo &quot;More than five&quot;
fi</c-code-block>
```

Note: use standard fenced code blocks (` ``` `) for code that needs no title or language label — FLS renders them natively without the escaping requirement.

---

## `c-pull-quote`

Pull quote with optional attribution. Body is markdown-rendered.

**Allowed attributes:** `attribution`, `cite`, `source`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `attribution` | No | `""` | Who said it (plain text) |
| `source` | No | `""` | Work title (rendered in `<cite>`) |
| `cite` | No | `""` | URL linking back to the source |

```markdown
<c-pull-quote attribution="Ada Lovelace" source="Notes on the Analytical Engine" cite="https://example.com">
The Analytical Engine weaves algebraic patterns, just as the Jacquard loom weaves flowers and leaves.
</c-pull-quote>
```

---

## `c-equation`

Client-side KaTeX equation typesetting.

**Allowed attributes:** `label`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `label` | No | `""` | Reference number/label (e.g. `"1"`); shown as `(1)` to the side |

**HTML-escaping is required.** The slot content passes through nh3 before KaTeX processes it — you must escape:

| Character | Escape as |
|---|---|
| `<` | `&lt;` |
| `>` | `&gt;` |
| `&` | `&amp;` |

```markdown
<c-equation label="1">E = mc^2</c-equation>

<c-equation>\sum_{i=1}^{n} i = \frac{n(n+1)}{2}</c-equation>

<c-equation>a &lt; b \implies a + c &lt; b + c</c-equation>
```

On malformed LaTeX, KaTeX falls back to showing the raw source string.
