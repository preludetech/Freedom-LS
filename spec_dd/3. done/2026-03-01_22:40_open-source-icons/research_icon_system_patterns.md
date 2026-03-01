# Research: Icon System Patterns for Django + HTMX + TailwindCSS

## 1. Central Icon Registry Patterns

The goal is a single source of truth that maps semantic names (like "next", "deadline", "menu-open") to actual icon identifiers, so that changing the mapping in one place updates every icon across the application.

### 1.1 Python Dict/Module Approach

A Python module (e.g., `icons.py`) exports a dictionary or dataclass mapping semantic names to icon identifiers:

```python
# freedom_ls/base/icons.py

ICONS: dict[str, str] = {
    "next": "arrow-right",
    "previous": "arrow-left",
    "deadline": "clock",
    "menu_open": "chevron-right",
    "menu_close": "chevron-left",
    "complete": "check",
    "success": "check-circle",
    "error": "x-circle",
    "warning": "alert-triangle",
    "info": "info",
    "close": "x",
    "download": "download",
    "locked": "lock",
    "loading": "loader",
    # ...
}
```

**Pros:**
- Type-checkable, IDE-friendly, easy to validate in tests
- Can write a test that ensures every value in the dict corresponds to an actual icon file
- Easy to expose via a Django context processor for templates

**Cons:**
- Requires a context processor or template tag to bridge into templates
- Two layers of indirection (Python dict -> template tag -> SVG output)

### 1.2 Python Enum Approach

```python
from enum import StrEnum

class Icon(StrEnum):
    NEXT = "arrow-right"
    PREVIOUS = "arrow-left"
    DEADLINE = "clock"
    # ...
```

**Pros:**
- Strongest type safety, autocomplete in Python code
- Can iterate members for validation tests

**Cons:**
- Slightly more ceremony than a plain dict
- Enum member names must be valid Python identifiers (underscores, not hyphens)
- Less convenient to merge with template rendering

### 1.3 Django Context Processor + Dict (Recommended Hybrid)

Expose the icon registry to every template via a context processor:

```python
# freedom_ls/base/context_processors.py
from freedom_ls.base.icons import ICONS

def icons(request):
    return {"ICONS": ICONS}
```

Templates then reference icons semantically:

```html
<c-icon name="{{ ICONS.next }}" class="size-5" />
```

**Pros:**
- Available in every template without `{% load %}` tags
- Changing a mapping in `icons.py` propagates everywhere
- Testable: write a test that every ICONS value maps to a real icon file

**Cons:**
- The registry dict is added to every template context (minor overhead)
- Template authors need to know the semantic names

### 1.4 Configuration File Approaches (YAML/JSON)

Some projects store icon mappings in YAML or JSON:

```yaml
# icons.yaml
next: arrow-right
previous: arrow-left
deadline: clock
```

**Pros:**
- Non-developers can edit icon mappings
- Language-agnostic

**Cons:**
- Adds a parsing dependency (PyYAML)
- No type checking at definition time
- Harder to validate without extra tooling
- FLS already has no YAML config pattern (except for course content), so this would be inconsistent

**Recommendation for FLS:** Use a Python dict in a module (`icons.py`) exposed via context processor. This fits the project's existing Python-centric approach, is testable, and integrates naturally with Django templates.

---

## 2. Django Template Integration Patterns

### 2.1 Inline SVG via Custom Template Tag

The classic approach: a custom template tag reads an SVG file from disk and injects it inline.

```python
# templatetags/icons.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def icon(name, size="size-5", **attrs):
    # Read SVG file, inject attributes, return mark_safe(svg_string)
    ...
```

Usage:
```html
{% load icons %}
{% icon "check-circle" size="size-6" class="text-green-500" %}
```

**Packages that implement this pattern:**
- [heroicons](https://github.com/adamchainz/heroicons) -- Adam Johnson's package provides `{% heroicon_outline "name" %}` and `{% heroicon_solid "name" %}` tags
- [django-inline-svg](https://github.com/mixxorz/django-inline-svg) -- generic `{% svg "filename" %}` tag
- [django-svg-templatetag](https://github.com/Mediamoose/django-svg-templatetag) -- similar approach

**Pros:**
- Full control over SVG attributes (class, aria, role)
- SVGs are part of the HTML, so `currentColor` inheritance works with Tailwind `text-*` classes
- No extra HTTP requests
- Can cache parsed SVGs in memory

**Cons:**
- Increases HTML document size (each SVG is repeated in the markup)
- Requires file I/O (mitigated by caching)
- More complex template tag implementation

### 2.2 SVG Sprite Sheets

Combine all icons into a single SVG sprite file with `<symbol>` elements, then reference them with `<use>`:

```html
<!-- In base template: hidden sprite sheet -->
<svg style="display:none">
  <symbol id="icon-check" viewBox="0 0 24 24">
    <path d="M5 13l4 4L19 7" />
  </symbol>
  <!-- ... more symbols ... -->
</svg>

<!-- Usage anywhere on the page -->
<svg class="size-5 text-green-500"><use href="#icon-check" /></svg>
```

**Pros:**
- Each icon's SVG data appears only once in the document
- Good performance when many icons are repeated on a page
- `currentColor` inheritance works

**Cons:**
- Screen reader support for `<use>` + `<title>` is inconsistent across browsers ([Smashing Magazine: Accessible SVG Patterns](https://www.smashingmagazine.com/2021/05/accessible-svg-patterns-comparison/))
- The sprite sheet must be included on every page (or managed carefully)
- Build step needed to generate the sprite sheet
- Harder to add new icons without rebuilding

### 2.3 Django-Cotton Components (Recommended for FLS)

Django-Cotton enables component-based SVG icons that feel like HTML elements:

```html
<!-- cotton/icon/check.html -->
<c-vars size="size-5" />
<svg {{ attrs }} class="{{ size }}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M5 13l4 4L19 7" />
</svg>
```

Usage:
```html
<c-icon.check class="text-green-500" />
<c-icon.check size="size-8" class="text-red-500" />
```

The [cotton-icons](https://github.com/wrabit/cotton-icons) package provides pre-built cotton components for Heroicons, Tabler Icons, and Lucide Icons:

```html
<c-heroicon.chevron-down class="size-5" />
<c-tablericon.graph variant="filled" class="size-5" />
<c-lucideicon.search stroke-width="3" />
```

Ref: [Django Cotton Icons Documentation](https://django-cotton.com/docs/icons)

**Pros:**
- FLS already uses django-cotton extensively for buttons, chips, modals, etc.
- Consistent with existing component patterns (`<c-button>`, `<c-chip>`, etc.)
- All SVG attributes pass through to the `<svg>` tag
- `currentColor` works, enabling Tailwind `text-*` color classes
- No build step required
- Each icon is a standalone template file -- easy to add, remove, or replace

**Cons:**
- Each icon is a separate template file (manageable for ~30 icons, could get unwieldy for hundreds)
- Template rendering overhead per icon (negligible in practice)

### 2.4 Template Includes

Simple `{% include %}` with SVG partials:

```html
{% include "icons/check.svg" with class="size-5 text-green-500" %}
```

**Pros:**
- No custom template tags needed
- Works with any Django project

**Cons:**
- `{% include %}` doesn't support attribute pass-through as cleanly as cotton
- Verbose compared to component syntax
- No variable defaults without extra logic

**Recommendation for FLS:** Use django-cotton icon components. The project already depends on django-cotton and uses it for all UI components. The `cotton-icons` package provides drop-in Heroicon/Tabler/Lucide components. For the central registry, wrap these in a semantic icon component that maps semantic names to underlying icon components.

### 2.5 Hybrid Pattern: Semantic Wrapper Component + Icon Library

The strongest approach for FLS combines patterns: a semantic cotton component that reads from the registry:

```html
<!-- cotton/icon.html -->
<c-vars name="" size="size-5" />

{% load icon_tags %}
{% render_icon name size attrs %}
```

Where `render_icon` is a template tag that:
1. Looks up the semantic name in the ICONS registry (if it matches)
2. Resolves to the actual icon component
3. Renders the appropriate SVG

This gives templates a clean semantic API:
```html
<c-icon name="next" class="text-blue-500" />
<c-icon name="success" size="size-8" />
```

---

## 3. Common UX Patterns for Icon Usage in LMS/Education Apps

Based on the [existing FLS icon audit](research_current_icon_audit.md), the icons fall into well-defined semantic categories typical of education platforms.

### 3.1 Semantic Icon Categories

#### Navigation
| Semantic Name | Purpose | Common Icon Choices |
|--------------|---------|-------------------|
| `next` / `previous` | Course content navigation | Arrow right/left, Chevron right/left |
| `home` | Return to course home / dashboard | House icon |
| `expand` / `collapse` | TOC sections, sidebars | Chevron down/right, Chevron down/up |
| `menu_open` / `menu_close` | Sidebar toggle | Bars/hamburger, X, Chevron |
| `dropdown` | Dropdown indicator | Chevron down |

#### Status Indicators
| Semantic Name | Purpose | Common Icon Choices |
|--------------|---------|-------------------|
| `success` / `complete` | Task/quiz passed, item completed | Check circle, Circle check |
| `error` / `failed` | Task/quiz failed | X circle, Circle X |
| `warning` | Warning state | Alert triangle, Triangle alert |
| `info` | Information notice | Info circle, Circle info |
| `in_progress` | Currently working on item | Spinner, Circle dot, Play |
| `locked` | Content not yet available | Lock, Lock closed |
| `not_started` | Available but not begun | Circle (empty), Minus |
| `repeatable` | Can be retried | Repeat, Refresh |

#### Actions
| Semantic Name | Purpose | Common Icon Choices |
|--------------|---------|-------------------|
| `check` / `confirm` | Mark complete, submit | Check mark |
| `close` / `dismiss` | Close modal, dismiss notification | X |
| `retry` | Retry quiz/assessment | Redo, Refresh |
| `download` | Download file | Download, Arrow down to line |
| `more_options` | Overflow/context menu | Ellipsis vertical, Dots vertical |
| `settings` | Settings/configuration | Cog, Gear |

#### Content Types
| Semantic Name | Purpose | Common Icon Choices |
|--------------|---------|-------------------|
| `reading` | Reading/topic content | Book, Book open |
| `quiz` / `form` | Quiz or form content | Pencil, Edit, Clipboard |
| `assessment` | Formal assessment | Graduation cap, Award |
| `section` / `group` | Content grouping | Folder, Layers |

#### User/System
| Semantic Name | Purpose | Common Icon Choices |
|--------------|---------|-------------------|
| `user` | User profile/avatar | User, Circle user |
| `notifications` | Notification bell | Bell |
| `deadline` | Due date/time constraint | Clock, Calendar |
| `achievement` | Completion celebration | Trophy, Star, Award |
| `loading` | Async operation in progress | Spinner (animated), Loader |
| `sort_asc` / `sort_desc` / `sort_neutral` | Table column sorting | Arrow up/down, Chevron up/down, Sort |

#### Boolean / Data Display
| Semantic Name | Purpose | Common Icon Choices |
|--------------|---------|-------------------|
| `boolean_true` | True value in data table | Check mark |
| `boolean_false` | False value in data table | X mark |

### 3.2 Accessibility Considerations

Based on research from [Smashing Magazine](https://www.smashingmagazine.com/2021/05/accessible-svg-patterns-comparison/), [Deque](https://www.deque.com/blog/creating-accessible-svgs/), and [CSS-Tricks](https://css-tricks.com/accessible-svg-icons/):

**Decorative icons** (icon accompanies visible text):
```html
<!-- Icon is decorative, text provides meaning -->
<button>
  <svg aria-hidden="true" class="size-5">...</svg>
  Continue
</button>
```
- Add `aria-hidden="true"` to hide from screen readers
- The adjacent text label provides the accessible name
- This is the most common case in FLS (buttons with text + icon)

**Informative icons** (icon is the only content):
```html
<!-- Icon-only button needs an accessible name -->
<button aria-label="Close dialog">
  <svg aria-hidden="true" class="size-5">...</svg>
</button>
```
- The `aria-label` goes on the interactive parent element, not the SVG
- The SVG itself is still `aria-hidden="true"`
- The parent provides the accessible name

**Standalone informative icons** (icon conveys meaning without interactive parent):
```html
<!-- Icon conveys status information -->
<svg role="img" aria-labelledby="status-title" class="size-5">
  <title id="status-title">Completed</title>
  <path d="..." />
</svg>
```
- Use `role="img"` on the SVG element
- Pair with `<title>` and `aria-labelledby` for best screen reader support
- This pattern has the broadest screen reader compatibility per the Smashing Magazine study

**Key rules for the FLS icon system:**
1. Default to `aria-hidden="true"` on all icons (most are decorative)
2. Provide an `aria_label` parameter on the icon component for the informative case
3. When `aria_label` is set, render `role="img"` and a `<title>` element instead of `aria-hidden`
4. Never rely on the icon alone to convey meaning -- always pair with visible text or an `aria-label`

### 3.3 Sizing Conventions with TailwindCSS

Tailwind's `size-*` utility sets both width and height simultaneously. Common conventions for icons:

| Context | Tailwind Class | Pixels | Usage |
|---------|---------------|--------|-------|
| Inline with body text | `size-4` | 16px | Small indicators, status dots |
| Standard UI icons | `size-5` | 20px | Buttons, navigation, most common |
| Emphasized icons | `size-6` | 24px | Headers, prominent actions |
| Large feature icons | `size-8` | 32px | Empty states, hero sections |
| Extra large | `size-12` or `size-16` | 48-64px | Celebration/completion screens |

Ref: [Heroicons sizing discussion](https://github.com/tailwindlabs/heroicons/discussions/675)

**Recommendations for FLS:**
- Set `size-5` as the default size in the icon component
- Use `size-4` for inline/dense contexts (TOC items, table cells)
- Use `size-6` for heading-level icons
- Use `size-12` or larger for celebratory/completion screens (trophy, etc.)
- Always use `size-*` (not separate `w-*` and `h-*`) for consistency

---

## 4. Common Challenges When Migrating Icon Systems

### 4.1 Missed Icon Replacements

The most common migration failure. Icons are scattered across templates, Python code, JavaScript, CSS pseudo-elements, and user-generated content.

**Mitigation strategies:**
- Run a comprehensive audit first (FLS already has [research_current_icon_audit.md](research_current_icon_audit.md))
- Write a test or CI check that greps for old icon patterns (e.g., `fa-`, `fa `, `font-awesome`)
- Search for ALL icon delivery methods: `<i class="fa`, inline `<svg>`, Unicode characters
- Check CSS files for `::before` / `::after` pseudo-elements with font-awesome content codes
- Check JavaScript/HTMX responses for dynamically-inserted icons

Ref: [Web Performance Calendar: From Fonts to SVG](https://calendar.perfplanet.com/2021/from-fonts-to-svg-an-icon-migration-strategy/)

### 4.2 Inconsistent Sizing

When migrating from icon fonts to SVGs, sizing behaves differently:
- Font Awesome icons inherit `font-size` from their parent
- SVGs require explicit `width`/`height` or a CSS class like Tailwind's `size-*`
- Without explicit sizing, SVGs may render at their native viewBox size (often 24x24 or larger)

**Mitigation strategies:**
- Set a sensible default size in the icon component (`size-5`)
- Document the sizing convention
- Audit after migration to catch oversized/undersized icons visually

### 4.3 Accessibility Regressions

Font Awesome automatically handles some accessibility (e.g., `aria-hidden` on decorative icons). A manual SVG system must handle this explicitly.

**Common regressions:**
- Missing `aria-hidden="true"` on decorative icons, causing screen readers to announce meaningless SVG data
- Missing accessible names on icon-only buttons after removing FA's automatic handling
- `<title>` elements in SVGs being announced unexpectedly

**Mitigation strategies:**
- Build `aria-hidden="true"` into the icon component as the default
- Provide an explicit `aria_label` parameter for informative icons
- Test with a screen reader (or at minimum, automated a11y checks) after migration
- The icon component should handle the accessible pattern automatically based on whether `aria_label` is provided

### 4.4 Performance Considerations

| Approach | HTTP Requests | Cacheability | HTML Size | Render Speed |
|----------|--------------|--------------|-----------|-------------|
| Icon font (FA CDN) | 1-2 (CSS + font) | Excellent (CDN) | Small | Fast |
| Inline SVG | 0 | Not cacheable | Larger | Fast for <100 icons |
| SVG sprite (embedded) | 0 | Not cacheable | Medium | Fast |
| SVG sprite (external) | 1 | Excellent | Small | Variable by browser |
| Cotton components | 0 | N/A (server-rendered) | Larger | Fast |

Ref: [Cloud Four SVG Icon Stress Test](https://cloudfour.com/thinks/svg-icon-stress-test/)

**Key findings from performance research:**
- For the typical FLS page (5-30 icons), inline SVG or cotton component performance is excellent
- Optimization of SVG markup matters more than delivery technique -- unoptimized inline SVGs are 3x slower than optimized ones
- Icon fonts win only when displaying thousands of different icons on one page (not an FLS scenario)
- The current FA CDN approach loads ~100KB of CSS for 28 icons -- replacing with inline SVGs will be a net performance win

**FLS-specific performance note:** Since FLS uses server-side rendering with HTMX partial responses, icons in HTMX partials are re-sent on each swap. This is fine for inline SVGs (they're small), but means a sprite sheet approach would need the sprite embedded in the base template (not in partials).

### 4.5 Color Inheritance Issues

Font Awesome icons inherit `color` from their parent. SVGs need `stroke="currentColor"` or `fill="currentColor"` to achieve the same behavior.

**Mitigation:**
- Ensure all icon SVGs use `currentColor` for stroke/fill
- Tailwind's `text-*` utilities then control icon color naturally
- The icon component should set `stroke="currentColor"` by default

### 4.6 Animation Differences

Font Awesome provides built-in animation classes (`fa-spin`, `fa-pulse`). SVG icons need Tailwind animation utilities instead.

**Mitigation:**
- Replace `fa-spin` with Tailwind's `animate-spin`
- Replace `fa-pulse` with `animate-pulse`
- Document animation patterns in the icon component

---

## 5. Recommended Approach for FLS

Based on this research and the existing FLS architecture:

1. **Use `cotton-icons` package** with Heroicons or Lucide as the base icon library -- both are MIT-licensed, have broad icon coverage, and integrate directly with django-cotton
2. **Create a Python icon registry** (`freedom_ls/base/icons.py`) mapping semantic names to icon identifiers
3. **Expose the registry via context processor** so templates can reference `{{ ICONS.next }}` etc.
4. **Build a semantic `<c-icon>` cotton component** that accepts a `name` parameter, looks it up in the registry, and delegates to the underlying icon library component
5. **Default to `aria-hidden="true"`** with an opt-in `aria_label` parameter for informative icons
6. **Default to `size-5`** with a `size` parameter override
7. **Write a CI test** that greps for leftover Font Awesome patterns (`fa-`, `fa `, `font-awesome`) to prevent regression
8. **Write a test** that validates every entry in the ICONS dict corresponds to an actual icon in the chosen library

---

## References

- [django-cotton Icons Documentation](https://django-cotton.com/docs/icons)
- [cotton-icons: Heroicons + Tabler + Lucide for Django Cotton](https://github.com/wrabit/cotton-icons)
- [heroicons Python package (Adam Johnson)](https://github.com/adamchainz/heroicons)
- [Smashing Magazine: Accessible SVG Patterns Comparison](https://www.smashingmagazine.com/2021/05/accessible-svg-patterns-comparison/)
- [Deque: Creating Accessible SVGs](https://www.deque.com/blog/creating-accessible-svgs/)
- [CSS-Tricks: Accessible SVG Icons](https://css-tricks.com/accessible-svg-icons/)
- [Cloud Four: SVG Icon Stress Test (Performance)](https://cloudfour.com/thinks/svg-icon-stress-test/)
- [Web Performance Calendar: From Fonts to SVG Migration Strategy](https://calendar.perfplanet.com/2021/from-fonts-to-svg-an-icon-migration-strategy/)
- [CSS-Tricks: Icon Fonts vs SVG](https://css-tricks.com/icon-fonts-vs-svg/)
- [Font Awesome Accessibility Docs](https://docs.fontawesome.com/web/dig-deeper/accessibility/)
- [Heroicons Sizing Discussion](https://github.com/tailwindlabs/heroicons/discussions/675)
- [Orange Digital Accessibility: SVG Images](https://a11y-guidelines.orange.com/en/articles/accessible-svg/)
- [MvT: How to Use SVG Icons in Django Templates](https://mirellavanteulingen.nl/blog/svg-icons-django-template.html)
- [django-svg-icons (JSON-based icon loading)](https://github.com/djangomango/django-svg-icons)
- [Huge Icons: Icon Font vs SVG Comparison](https://hugeicons.com/blog/technology/icon-font-vs-svg-which-one-should-you-use)
