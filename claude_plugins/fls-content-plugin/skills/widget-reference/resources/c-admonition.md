# `c-admonition`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Typed callout box. Body is markdown-rendered.

**Allowed attributes:** `type`, `title`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `type` | No | `"default"` | Admonition type — see below |
| `title` | No | `""` | Overrides the default label for the type |

```markdown
<c-admonition type="warning" title="Watch out">
This is important to check before proceeding.
</c-admonition>

<c-admonition type="note">
A plain note with the default label.
</c-admonition>

<c-admonition type="checklist">
- [ ] Step one
- [ ] Step two
- [ ] Step three
</c-admonition>
```

### Admonition types are deployment-configurable

The valid `type` values for **your project** are declared in `.fls-content.yaml` at the repo root, which always exists (set up with `/fls-content:init`). The FLS base set is:

`note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`, `default`

This base set is **fully overridable** — a deployment may add, remove, or rename types. Never treat the base set as exhaustive. An unknown `type` falls back **silently** to the `default` style at render time with no error, which is why you must use the types declared in your project's `.fls-content.yaml`.

The `checklist` type renders `- [ ]` markdown task items as read-only disabled checkboxes.
