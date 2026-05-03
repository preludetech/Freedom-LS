# Legal documents

This directory contains the Terms and Conditions and Privacy Policy text shown to users at signup and at `/accounts/legal/<doc_type>/`.

## Layout

```
legal_docs/
├── _default/
│   ├── terms.md
│   └── privacy.md
└── <site_domain>/        # one directory per site (optional)
    ├── terms.md
    └── privacy.md
```

When the legal-doc loader is asked for a document for a particular site, it looks in:

1. `legal_docs/<site.domain>/<doc_type>.md`
2. `legal_docs/_default/<doc_type>.md`

…and returns the first one that exists. If neither exists, the corresponding signup checkbox is suppressed and a warning is logged.

## File format

Each file is markdown with a YAML frontmatter block:

```markdown
---
version: "1.2"
title: "Terms and Conditions"
type: "terms"
effective_date: "2026-04-27"
---

# Heading

Body content here.
```

Required frontmatter keys:

- `version` — human-readable version string. Used for "has the user accepted v2 or later?" queries.
- `title` — display title.
- `type` — `"terms"` or `"privacy"`.
- `effective_date` — ISO date.

## Source of truth

Document text is read from the **git blob at HEAD** at request time, not from the working tree. This means a tampered checkout cannot change what users see or what is recorded.

For deployments without a `.git` directory at runtime, generate a manifest at build time:

```bash
uv run manage.py build_legal_docs_manifest
```

…and point `settings.LEGAL_DOCS_MANIFEST_PATH` at the resulting JSON file. The manifest must live inside the read-only image filesystem.

## Customising for your deployment

The shipped `_default/terms.md` and `_default/privacy.md` are placeholders. Site operators **must** replace them — or override per-site under `legal_docs/<site_domain>/` — with copy reviewed by their own legal team before going live.
