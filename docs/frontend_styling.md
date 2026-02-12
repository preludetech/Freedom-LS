# Frontend Styling

## TailwindCSS v4

- Build: `npm run tailwind_build`
- Watch: `npm run tailwind_watch`
- Component classes: `tailwind.components.css`

## Critical Rule

**ALWAYS check `tailwind.components.css` before writing Tailwind classes**

```bash
cat tailwind.components.css
```

## Base Styles (Auto-Applied)

Typography and forms have automatic styling via `@layer base`:
- `h1-h4` - Pre-sized and bold
- `a` - link styling
- `ul`, `ol` - List styling
- `input`, `textarea`, `select`, `label` - Form styling

**Don't duplicate these in your markup**

## Component Classes

Available in `tailwind.components.css`:
- `.btn`, `.btn-primary`, `.btn-danger` - Buttons
- `.surface` - Cards/panels
- Form components

## Usage Rules

1. **Check `tailwind.components.css` first** - Use component classes when available
2. **Rely on base styles** - Don't add `text-4xl font-bold` to `<h1>`
3. **Inline classes only for unique styling** - Layout, spacing, positioning
4. **Keep it DRY** - Repeated patterns → add to `tailwind.components.css`
5. **Keep it cohesive** - Styles that only appear once, or that are specific to a single page or location should be inline. Only use `tailwind.components.css` for things that are likely to be reused.

## Example

**BAD:**
```html
<h1 class="text-4xl font-bold">Title</h1>
<button class="px-6 py-2 bg-blue-600...">Click</button>
```

**GOOD:**
```html
<h1>Title</h1>
<button class="btn btn-primary">Click</button>
```
