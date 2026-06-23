# `c-code-block`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

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
