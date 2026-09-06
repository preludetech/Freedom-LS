# `c-table`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

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

## Do not nest `c-table` inside another widget

`c-table` only works at the top level of a topic. Put a plain GFM table in the
body of a `c-accordion`, `c-flashcard` slot, or `c-admonition` — it is styled
there already.

Those components render their bodies as author markdown, which runs the
sanitiser over the already-rendered `c-table` markup and strips the wrapper's
attributes. The table still appears, but it loses the scrollable region, the
focus ring, the `role="group"` label, and the caption styling — so a nested
`c-table` reads worse than the plain table it replaced.
