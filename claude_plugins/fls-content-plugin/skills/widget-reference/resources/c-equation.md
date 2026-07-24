# `c-equation`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

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
