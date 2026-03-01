# Research: Open-Source Icon Libraries to Replace Font Awesome

**Date:** 2026-03-01
**Context:** Django 5.x + HTMX 2.x + TailwindCSS project. No React or JS framework dependencies allowed.

---

## Summary Table

| Library | Icons | License | Django Package | TailwindCSS Fit |
|---------|-------|---------|----------------|-----------------|
| Heroicons | ~316 (x4 styles) | MIT | `heroicons` (adamchainz) | Best (by Tailwind Labs) |
| Lucide | 1,500+ | ISC | `lucide` (franciscobmacedo) | Great |
| Tabler Icons | 5,900+ | MIT | `django-tabler-icons` | Good |
| Phosphor Icons | 1,240+ (x6 styles) | MIT | None | Good |
| Iconoir | 1,600+ | MIT | None | Good |
| Bootstrap Icons | 2,000+ | MIT | `django-bootstrap-icons` | Decent |

---

## 1. Heroicons (by Tailwind Labs)

**Website:** https://heroicons.com/
**GitHub:** https://github.com/tailwindlabs/heroicons
**License:** MIT
**Icon count:** ~316 unique icons, available in 4 styles: outline (24px), solid (24px), mini (20px), micro (16px)

### Django Integration

**Package:** `heroicons` by Adam Johnson
- **PyPI:** https://pypi.org/project/heroicons/
- **GitHub:** https://github.com/adamchainz/heroicons
- **Latest version:** 2.13.0 (September 2025)
- **Supports:** Python 3.10-3.14, Django 4.2-6.0

**Installation:**
```bash
pip install heroicons[django]
# or: uv add heroicons[django]
```

**Usage in Django templates:**
```django
{% load heroicons %}
{% heroicon_outline "academic-cap" %}
{% heroicon_solid "arrow-left" size=20 class="text-gray-500" %}
{% heroicon_mini "calendar" class="w-5 h-5" %}
{% heroicon_micro "clock" %}
```

**Also available via cotton-icons** (if using Django Cotton):
```django
<c-heroicon.academic-cap variant="outline" class="w-6 h-6" />
```
- GitHub: https://github.com/wrabit/cotton-icons

### Pros
- Made by Tailwind Labs -- guaranteed visual harmony with TailwindCSS
- Excellent Django package by Adam Johnson, actively maintained, supports Django up to 6.0
- 4 size variants (micro/mini/outline/solid) cover different UI density needs
- Clean, consistent design language
- Very well-known in the Tailwind ecosystem; lots of examples and community support
- Icons render as inline SVGs -- easy to style with Tailwind utility classes

### Cons
- Only ~316 unique icons -- smallest library in this comparison
- May lack niche or specialized icons (e.g., specific brand icons, advanced chart types)
- If your UI needs grow, you may need to supplement with another library

---

## 2. Lucide Icons (fork of Feather Icons)

**Website:** https://lucide.dev/
**GitHub:** https://github.com/lucide-icons/lucide
**License:** ISC (permissive, similar to MIT)
**Icon count:** 1,500+ icons
**Latest version:** 0.576.0 (February 2026, actively maintained with 653 releases)

### Django Integration

**Package:** `lucide` by Francisco Macedo
- **GitHub:** https://github.com/franciscobmacedo/lucide
- **Latest version:** 1.1.3
- **Supports:** Python 3.8-3.12, Django 3.2-5.0

**Installation:**
```bash
pip install lucide[django]
# or: uv add lucide[django]
```

**Usage in Django templates:**
```django
{% load lucide %}
{% lucide "arrow-left" size=24 class="text-gray-500" %}
{% lucide "calendar" size=20 class="w-5 h-5 stroke-current" %}
```

**Alternative packages:**
- `django-lucide-icons` (https://pypi.org/project/django-lucide-icons/)
- `python-lucide` (https://pypi.org/project/lucide-py/)

**Also available via cotton-icons:**
```django
<c-lucideicon.calendar class="w-6 h-6" />
```

**Plain SVG (no framework):** Use the `lucide-static` npm package for direct SVG file access.

### Pros
- Large icon set (1,500+) with good UI coverage
- Very actively maintained (frequent releases, strong community)
- Consistent 24x24 stroke-based design -- pairs well with TailwindCSS
- Django package exists with template tag support
- ISC license is permissive and simple
- Good successor to Feather Icons with expanded icon set

### Cons
- Django package (`lucide` 1.1.3) lags behind the main library and lists support only up to Django 5.0 / Python 3.12
- Single style (stroke/outline only) -- no solid/filled variants
- Stroke-only design may feel too minimal for some UIs

---

## 3. Tabler Icons

**Website:** https://tabler.io/icons
**GitHub:** https://github.com/tabler/tabler-icons
**License:** MIT
**Icon count:** 5,900+ icons
**Latest version:** 3.37.1 (actively maintained)

### Django Integration

**Package:** `django-tabler-icons`
- **PyPI:** https://pypi.org/project/django-tabler-icons/
- **Latest version:** 0.7.2

**Installation:**
```bash
pip install django-tabler-icons
# or: uv add django-tabler-icons
```

**Usage in Django templates:**
```django
{% load tabler_icons %}
{% tabler_icon_outline "arrow-left" %}
{% tabler_icon_filled "calendar" %}
```

**Also available via cotton-icons:**
```django
<c-tablericon.calendar variant="outline" class="w-6 h-6" />
```

**Note:** The django-tabler-icons package downloads icons to `~/.config/django-tabler-icons/` on first use.

### Pros
- Massive icon set (5,900+) -- you will almost never run out of icons
- Two styles: outline and filled
- MIT license
- Actively maintained with regular updates
- Good Django package available
- Very broad coverage including niche and specialized icons

### Cons
- Django package (0.7.2) is less mature than the heroicons package
- Icon download mechanism (to user home directory) is non-standard
- With 5,900+ icons, consistency can vary slightly across the set
- Not specifically designed for TailwindCSS (but works fine with it)
- Larger package size due to icon count

---

## 4. Phosphor Icons

**Website:** https://phosphoricons.com/
**GitHub:** https://github.com/phosphor-icons/core
**License:** MIT
**Icon count:** ~1,240 unique icons across 6 weights: thin, light, regular, bold, fill, duotone

### Django Integration

**No dedicated Django package found.** You would need to:
1. Copy SVG files into your static/templates directory manually
2. Create a custom template tag/include system
3. Use the npm package `@phosphor-icons/core` to get raw SVGs

**Plain SVG usage:**
```bash
npm install @phosphor-icons/core
```
SVGs are organized as: `assets/<weight>/<icon-name>-<weight>.svg`

### Pros
- 6 weight variants (thin, light, regular, bold, fill, duotone) -- most style options of any library
- Duotone style is unique and visually distinctive
- Clean, consistent design
- MIT license
- Good icon coverage for common UI needs

### Cons
- No Django integration package -- requires manual setup
- Manual SVG management adds maintenance overhead
- The duotone style requires more complex SVG handling (two-color paths)
- Smaller community compared to Heroicons or Lucide in the Django/Python ecosystem
- Integration effort is significantly higher than other options

---

## 5. Iconoir

**Website:** https://iconoir.com/
**GitHub:** https://github.com/iconoir-icons/iconoir
**License:** MIT
**Icon count:** 1,600+ icons

### Django Integration

**No dedicated Django package found.** SVGs available for download or via npm.

### Pros
- Large, well-designed icon set (1,600+)
- Clean, consistent stroke-based design
- MIT license
- Actively maintained

### Cons
- No Django integration package
- Single style (stroke/outline)
- Less community adoption in the Python/Django ecosystem
- Manual integration required

---

## 6. Bootstrap Icons (honorable mention)

**Website:** https://icons.getbootstrap.com/
**GitHub:** https://github.com/twbs/icons
**License:** MIT
**Icon count:** 2,000+

### Django Integration

**Package:** `django-bootstrap-icons`
- **PyPI:** https://pypi.org/project/django-bootstrap-icons/

### Pros
- Large icon set with good coverage
- Dedicated Django package
- Well-known and widely used

### Cons
- Visually associated with Bootstrap -- may feel out of place in a TailwindCSS project
- Design style is heavier/more complex than Tailwind-native options

---

## Recommendation

### Top Pick: Heroicons

**Best fit for this project** because:
1. Made by Tailwind Labs -- guaranteed visual consistency with our TailwindCSS stack
2. Excellent Django integration via `heroicons` package by Adam Johnson (supports Django up to 6.0, Python up to 3.14)
3. 4 icon styles (micro, mini, outline, solid) cover different UI density needs
4. Template tags render inline SVGs that are trivially styled with Tailwind classes
5. No JS framework dependency -- pure server-side rendering

**The main risk** is the smaller icon count (~316). If we find icons missing, the mitigation strategy is:

### Fallback: Lucide Icons

Lucide can supplement Heroicons for any missing icons. It has 1,500+ icons, a Django package, and a visually compatible stroke-based design. Using two libraries adds slight inconsistency but keeps the project flexible.

### If icon count is the primary concern: Tabler Icons

With 5,900+ icons, Tabler Icons eliminates any concern about missing icons. The Django package exists but is less polished. Also available through cotton-icons alongside Heroicons.

### Note on cotton-icons

The `cotton-icons` package (https://github.com/wrabit/cotton-icons) supports Heroicons, Tabler Icons, and Lucide Icons through Django Cotton components. This could be relevant if the project adopts Django Cotton for templating, as it provides a unified interface across multiple icon libraries.

---

## References

- Heroicons: https://heroicons.com/
- Heroicons GitHub: https://github.com/tailwindlabs/heroicons
- Heroicons Python package: https://github.com/adamchainz/heroicons
- Heroicons PyPI: https://pypi.org/project/heroicons/
- Lucide Icons: https://lucide.dev/
- Lucide GitHub: https://github.com/lucide-icons/lucide
- Lucide Django package: https://github.com/franciscobmacedo/lucide
- Tabler Icons: https://tabler.io/icons
- Tabler Icons GitHub: https://github.com/tabler/tabler-icons
- django-tabler-icons PyPI: https://pypi.org/project/django-tabler-icons/
- Phosphor Icons: https://phosphoricons.com/
- Phosphor Core GitHub: https://github.com/phosphor-icons/core
- Iconoir: https://iconoir.com/
- Bootstrap Icons: https://icons.getbootstrap.com/
- cotton-icons: https://github.com/wrabit/cotton-icons
- Django Cotton: https://pypi.org/project/cotton-heroicons/
