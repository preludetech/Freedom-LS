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
