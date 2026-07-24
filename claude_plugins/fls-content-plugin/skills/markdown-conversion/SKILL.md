---
name: markdown-conversion
description: When and how to convert messy Markdown into valid FLS content structure. Use when converting, restructuring, or importing markdown, or when pasting content into FLS.
allowed-tools: Read, Grep, Glob
---

# Markdown Conversion to FLS Content

## When to convert

Use conversion when you have existing Markdown (from a blog, docs site, Obsidian vault, Google Docs export, etc.) that you want to turn into properly structured FLS course content. The goal is a valid structure that passes the bundled validator.

## Conservative philosophy

**Auto-apply only lossless, unambiguous transforms.** Everything semantic — "this blockquote looks like a warning" — is **proposed** in `_conversion_review.md` for the author to accept or reject. When in doubt, leave it as plain Markdown. A conservative conversion that underuses widgets is always safer than one that over-structures.

The three tiers:

1. **Auto-apply** — unambiguous, lossless, zero author decisions needed.
2. **Propose** — semantic intent must be confirmed; listed in `_conversion_review.md`.
3. **Leave alone** — inline formatting, lists, hyperlinks, and anything ambiguous.

## In-place conversion, no dry-run

`/fls-content:format-content` converts **in place** — it writes changes directly to the source files. There is no dry-run mode. This is intentional: content lives in git, so the full before/after diff and one-command rollback are already available. Review the `git diff` after conversion; roll back with `git checkout` or `git restore` if needed.

## After conversion: validate

After converting, validate the structure — run `/fls-content:validate-content` on the
converted path. Do this yourself; never ask the author to run anything. It checks the
structure (required fields, unknown fields, types, recognised content types) and auto-fixes
the obvious, unambiguous problems it finds. For a large conversion, validate per file — one
call per converted file — so each file's issues stay isolated.

This is a **structural pre-flight only**: it catches the most common structural mistakes
before the content is considered done. A clean result here does not guarantee any later
host-side processing will succeed, but it resolves the common errors first.

## Full conversion-pattern tables

See [`resources/conversion-patterns.md`](resources/conversion-patterns.md) for:
- The complete auto / propose / never table
- Heading-handling rules (setext normalisation, title lifting, body re-basing)
- Existing-widget normalisation rules
- Idempotency rules

Cross-references:
- Content type frontmatter → `fls-content:content-types` skill
- Widget syntax → `fls-content:widget-reference` skill
- Numbering, UUID, file-naming rules → `fls-content:conventions` skill
