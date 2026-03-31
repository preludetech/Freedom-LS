# UX Considerations for Icon Set Customization

## 1. Icon Consistency Challenges When Swapping Icon Sets

### Style Mismatches

Icon sets come in distinct visual styles that affect the overall feel of an interface:

- **Stroke vs fill**: Heroicons defaults to outline (stroke-based) icons at 24x24, while other sets may default to filled/solid. Mixing stroke and fill icons in the same UI looks inconsistent.
- **Stroke weight**: Heroicons uses a 1.5px stroke. Lucide uses 2px. Feather uses 2px. This difference is visible when icons sit next to each other or next to text.
- **Corner radius and caps**: Some sets use rounded caps/joins (Heroicons, Lucide), others use square or mixed. This affects perceived "friendliness" of the interface.
- **Optical size**: Heroicons has 4 size variants (16, 20, 24 outline, 24 solid). Not all sets offer size-specific variants, meaning icons may look too thin at small sizes or too heavy at large sizes.

### Naming Convention Differences

Every major icon set uses its own naming scheme. The same concept gets different names:

| FLS Semantic Name | Heroicons Value | Lucide Equivalent | Material (mdi) Equivalent |
|---|---|---|---|
| `success` | `check-circle` | `circle-check` | `check-circle` |
| `warning` | `exclamation-triangle` | `triangle-alert` | `alert` |
| `settings` | `cog-6-tooth` | `settings` | `cog` |
| `close` | `x-mark` | `x` | `close` |
| `assessment` | `academic-cap` | `graduation-cap` | `school` |
| `reading` | `book-open` | `book-open` | `book-open-variant` |
| `achievement` | `trophy` | `trophy` | `trophy` |
| `download` | `arrow-down-tray` | `download` | `download` |
| `repeatable` | `arrow-path` | `refresh-cw` | `refresh` |
| `quiz` | `pencil-square` | `pencil` or `square-pen` | `pencil-box` |
| `sort_neutral` | `bars-arrow-down` | `arrow-down-narrow-wide` | `sort` |

This table demonstrates the core problem: a 1:1 name mapping between icon sets does not exist. Every icon set swap requires a complete mapping table.

### Missing Icons

Some icon sets simply do not have equivalents for certain concepts. For example:
- `arrow-path` (Heroicons' circular arrow) has no direct equivalent in some sets.
- `cog-6-tooth` is very specific to Heroicons.
- Smaller icon sets (Feather has ~287 icons) may lack specialized icons that larger sets (Material Design Icons has 7,400+) include.

## 2. Semantic vs Literal Naming: Best Practices

### What Major Design Systems Do

**Lucide** (successor to Feather Icons) uses **literal/descriptive naming**: icons are named for what they depict, not what they are used for. Their guidelines explicitly state: "Name what icons show, not what they do (`floppy-disk` not `save`)." They use lower-kebab-case with modifiers (`circle-check`, `triangle-alert`).

Reference: https://lucide.dev/guide/design/icon-design-guide

**Material Design Icons** uses literal naming with a large, flat namespace (`home`, `check-circle`, `school`). The sheer size of the set (7,400+ icons) means most concepts are covered.

**Iconify** (a meta-framework spanning 150+ icon sets) preserves each set's original naming and uses a prefix system: `heroicons:arrow-right`, `lucide:arrow-right`, `mdi:arrow-right`. This avoids the naming unification problem entirely.

Reference: https://iconify.design/docs/icons/icon-set-basics.html

### Recommendation for FLS

FLS already uses the right pattern: **a semantic layer that maps purpose to icon name**. The `ICONS` dict in `base/icons.py` maps semantic names (`"success"`, `"quiz"`, `"next"`) to Heroicon-specific names (`"check-circle"`, `"pencil-square"`, `"arrow-right"`).

This is the correct architecture because:
1. Templates reference icons by **purpose** (`{% icon "success" %}`), not by literal icon name.
2. Swapping icon sets only requires providing a new mapping dict, not editing every template.
3. It decouples the visual layer from the semantic layer.

The key insight from design systems research: **icon libraries should name icons literally (what they depict), but applications should reference icons semantically (what they mean in context)**. FLS already has this separation.

## 3. Fallback Strategies

When a semantic name does not have a mapping in the selected icon set, there are several strategies:

### Option A: Error Loudly (Recommended for Development)

The current FLS behavior is to raise a `KeyError` if a semantic name is not found. This is correct for development: it forces the developer to provide a complete mapping before deploying.

### Option B: Fall Back to Default Set

If the overriding icon set is incomplete, fall back to Heroicons for missing entries. This is pragmatic for incremental migration but creates visual inconsistency (mixing two icon styles).

**Approach**: Merge dicts with Heroicons as the base:

```python
effective_icons = {**DEFAULT_HEROICONS_MAP, **custom_icon_map}
```

### Option C: Show a Visible Placeholder

Render a generic placeholder icon (e.g., a question mark in a circle) for unmapped names. This makes gaps visible without crashing the application.

### Option D: Startup Validation (Recommended for Production)

Run a system check at startup (`django.core.checks` framework) that validates the custom icon mapping covers all required semantic names. This catches configuration errors before they reach users.

**Recommendation**: Combine Options A and D. Error during development, validate at startup in production. Optionally support Option B as a transitional strategy with a deprecation warning for missing mappings.

## 4. Icon Set Compatibility: Coverage Gaps

### Coverage Comparison

Based on the current FLS icon registry (47 semantic names mapping to ~30 unique Heroicon names):

**Well-covered concepts** (present in all major sets):
- Arrows/navigation: `arrow-right`, `arrow-left`, `chevron-down`, `chevron-up`
- Common actions: `check`, `close`/`x`, `download`, `settings`/`cog`
- Objects: `home`, `user`, `bell`, `clock`, `lock`, `book-open`, `folder`
- Status: `check-circle`, `x-circle`, `play`

**Potentially problematic concepts**:
- `arrow-path` (circular refresh arrow) - Heroicons-specific name. Lucide uses `refresh-cw`, Material uses `refresh` or `autorenew`.
- `cog-6-tooth` - Very specific to Heroicons. Most sets just have `cog` or `settings`.
- `arrow-down-tray` - Heroicons-specific. Most sets use `download`.
- `bars-arrow-down` - Heroicons-specific. Lucide uses `arrow-down-narrow-wide`.
- `ellipsis-vertical` - Some sets use `more-vertical` or `dots-vertical`.
- `pencil-square` - Lucide uses `square-pen`, Material uses `pencil-box`.

### Key Finding

The ~30 unique icon concepts used by FLS are common enough that all major icon sets (Heroicons, Lucide, Material Design Icons, Phosphor, Tabler) will have equivalents. The challenge is purely in name mapping, not in concept coverage. No icon set gap should block a migration.

## 5. Migration and Transition Concerns

### What Makes Migration Easy

1. **A single mapping file**: FLS already has this (`base/icons.py`). Changing icon sets means providing a new dict, not hunting through templates.
2. **Automated validation**: The existing test `test_all_values_map_to_valid_heroicon_names` validates that every mapped value is a real icon in the installed set. This pattern should extend to any icon set.
3. **No hardcoded icon names in templates**: If all templates use the semantic layer (`{% icon "success" %}`) and none use raw Heroicon names, the swap is clean.
4. **CSS-class-based sizing/coloring**: If icon styling is handled via CSS classes rather than inline SVG attributes, it survives a set change.

### What Makes Migration Hard

1. **Leaked literal names**: Any template using `force=True` to bypass the semantic registry (the current `icon_from_name` filter supports this) creates a hidden dependency on the specific icon set. These must be audited before migration.
2. **Style rendering differences**: Even with correct name mapping, icons from different sets render differently. A visual review of every screen is needed.
3. **SVG structure assumptions**: If the rendering pipeline assumes a specific SVG structure (e.g., Heroicons' `<path>` structure, stroke-width, viewBox), a different icon set may not render correctly.
4. **Icon variants**: Heroicons has outline/solid/mini/micro variants. If FLS uses multiple variants, the replacement set must also offer those variants.

### Practical Migration Checklist

- [ ] Audit all templates for direct (non-semantic) icon references
- [ ] Create the mapping dict for the target icon set
- [ ] Run validation to confirm all mapped names exist in the target set
- [ ] Visually review key screens for style consistency (stroke weight, fill vs outline)
- [ ] Confirm the icon rendering component works with the new set's SVG format
- [ ] Test at all sizes where icons appear (inline text, buttons, empty states, navigation)

## Summary of Recommendations

1. **Keep the semantic mapping layer** - it is the right architecture and already in place.
2. **Provide pre-built mapping dicts** for 2-3 popular icon sets (Heroicons, Lucide, Material Design Icons) so downstream projects can switch via a Django setting.
3. **Validate mappings at startup** using Django's system checks framework.
4. **Support a merge/fallback strategy** for partial overrides (e.g., swap most icons but keep Heroicons for a few custom ones).
5. **Audit for leaked literal names** - the `force=True` escape hatch should be documented as a migration risk.
6. **Consider Iconify as the rendering backend** - it normalizes 150+ icon sets into a single API with the `prefix:name` convention, eliminating the need to bundle multiple icon packages. However, it adds a dependency and may require changes to the rendering pipeline.
7. **Document the complete list of semantic names** that any icon mapping must cover, so downstream projects know exactly what to map.

## References

- NNGroup on icon usability: https://www.nngroup.com/articles/icon-usability/
- Lucide naming conventions: https://lucide.dev/guide/design/icon-design-guide
- Iconify icon set architecture: https://iconify.design/docs/icons/icon-set-basics.html
- Design system iconography guide: https://www.designsystems.com/iconography-guide/
- Heroicons: https://heroicons.com/
- Lucide: https://lucide.dev/icons/
- Material Design Icons via Iconify: https://icon-sets.iconify.design/mdi/
