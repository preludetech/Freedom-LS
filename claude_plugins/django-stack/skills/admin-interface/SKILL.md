---
name: admin-interface
description: Configure the Django admin (standard Django admin, or django-unfold when enabled). Use when creating/modifying admin classes, working with inlines, or when the user mentions the admin interface.
allowed-tools: Read, Grep, Glob
---

# Admin Interface

## When to Use

Use this skill when:
- Creating or modifying Django admin classes
- Adding admin inlines for related models
- Configuring admin theme customizations

## Read the project config, then load one theme file

This skill is configurable. **Before writing admin code, read `.claude/ds/config.md` → `## Admin`** and
load only the file(s) that config selects — the patterns differ by theme, so reading the wrong one
produces admin classes that don't render.

### 1. Theme — read exactly one of these

| `Admin theme` | Read |
|---|---|
| **`standard`** (also the default when the file, section, or key is absent) | `${CLAUDE_PLUGIN_ROOT}/resources/admin_standard.md` |
| **`unfold`** | `${CLAUDE_PLUGIN_ROOT}/resources/admin_unfold.md` |

Each theme file is self-contained — base classes, common patterns, and rules. Don't read both.

### 2. Object permissions — read only if enabled

| `Object permissions (django-guardian)` | Read |
|---|---|
| **`disabled`** (default) | nothing — never use `GuardedModelAdmin` |
| **`enabled`** | `${CLAUDE_PLUGIN_ROOT}/resources/admin_guardian.md`, in addition to the theme file |

### Sanity check against the code

Config should match reality, but the code wins: if existing admin classes import from
`django.contrib.admin` while the config says `unfold` (or vice versa), follow the existing code and
tell the user the config looks stale.

## Key Rules (both themes)

- Register with the `@admin.register(Model)` decorator.
- Inherit from the base classes your theme file specifies — this is the one thing the themes disagree
  on, and getting it wrong fails silently (the page renders unstyled rather than erroring).
- Use `autocomplete_fields` for ForeignKey/M2M to avoid loading all options.
- Use `readonly_fields` for auto-generated fields (slug, timestamps).
- Use `fieldsets` to organize complex forms.
