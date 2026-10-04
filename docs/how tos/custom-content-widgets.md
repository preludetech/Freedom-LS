# Custom content widgets in a concrete project

A content widget is a cotton component that authors write straight into Markdown, like
`<c-youtube video_id="...">` or `<c-admonition type="tip">`. FLS ships about a dozen of them. A
concrete project can add its own without touching FLS: write the component, add it to the
allowlist, and authors can use it.

| Layer | Owns |
|-------|------|
| FLS | The rendering pipeline, the built-in widgets, the `content_tags` template library |
| Your project | Your widget templates, the `MARKDOWN_ALLOWED_TAGS` setting, telling your authors the widget exists |

---

## How a widget gets from Markdown to HTML

`render_markdown` in `freedom_ls/markdown_rendering/markdown_utils.py` runs four steps:

1. **Markdown to HTML.** Every tag in `MARKDOWN_ALLOWED_TAGS` is registered as a block-level
   element, so the Markdown parser passes it through instead of wrapping it in `<p>`.
2. **Sanitising with nh3.** Only tags and attributes listed in `MARKDOWN_ALLOWED_TAGS` survive. An
   unlisted tag or attribute is removed without any error.
3. **Cotton compilation.** `<c-foo>` becomes `{% cotton foo %}`.
4. **Template render.** The result renders as a Django template.

Step 2 is where custom widgets go wrong. Nothing in the pipeline knows a widget exists until the
allowlist names it.

---

## 1. Write the component

Put the template in a `templates/cotton/` directory that Django searches. Any app in your project
works, and so does a theme's `templates/cotton/`. The filename is the tag name without the `c-`
prefix.

`your_project/course_extras/templates/cotton/worked-example.html`:

```django
<c-vars title="Worked example" difficulty="" />

{% load content_tags %}

{% comment %}
A worked example: a problem statement followed by a solution the learner can reveal.

Attributes:
  title       Optional heading. Defaults to "Worked example".
  difficulty  Optional. Free text shown next to the heading, e.g. "harder".

The body slot is Markdown.
{% endcomment %}

<section class="my-6 rounded-lg border border-border p-4">
    <h3 class="font-semibold text-on-surface">
        {{ title }}
        {% if difficulty %}<span class="text-muted text-sm">({{ difficulty }})</span>{% endif %}
    </h3>
    <div class="mt-3 space-y-4">
        {% markdown slot %}
    </div>
</section>
```

The Markdown parser treats your tag as a block-level HTML element and leaves everything inside it
alone, so the body reaches the template as unparsed Markdown text. `{% markdown slot %}` renders
it. Leave the tag out and authors see their `**asterisks**` and `1.` list markers on the page.

### Don't reuse an FLS widget's name

Your project's template directories come before FLS's. A file at `templates/cotton/picture.html`
in your project replaces FLS's `c-picture` everywhere, including in FLS's own templates. That is
the right move when you mean to restyle `c-picture` (see the [theming how-to](./theme-fls.md)),
and a nasty surprise when you don't. Check `freedom_ls/content_engine/templates/cotton/` and
`freedom_ls/base/templates/cotton/` before picking a name.

---

## 2. Add the widget to `MARKDOWN_ALLOWED_TAGS`

Your settings file already defines `MARKDOWN_ALLOWED_TAGS`. It came across with the rest of your
settings and lists FLS's built-in widgets. Add your widget to that dict:

```python
MARKDOWN_ALLOWED_TAGS = {
    "c-youtube": {"video_id", "video_title", "caption"},
    "c-picture": {"src", "alt", "title", "description", "number"},
    # ... the rest of FLS's widgets ...
    "c-slot": {"name"},
    "c-worked-example": {"title", "difficulty"},
}
```

The setting replaces FLS's list. It does not add to it. FLS's own default is an empty dict, so if
you write a fresh `MARKDOWN_ALLOWED_TAGS` containing only your widget, every built-in widget
disappears from your rendered content. Keep the FLS entries.

That also means your copy can fall behind FLS. When an FLS release adds a widget or an attribute,
its upgrade notes list `MARKDOWN_ALLOWED_TAGS` under `changed_settings`. Copy the new entries
across, or the new attribute is stripped and the widget quietly renders its default.

List every attribute your template reads. An attribute missing from the set never reaches the
template, so `<c-worked-example difficulty="harder">` with only `{"title"}` allowed renders with no
difficulty and no warning.

---

## 3. Make Tailwind scan your templates

`tailwind.input.css` only scans templates under `freedom_ls/`. Classes used only in your widget's
template compile to nothing, and the widget renders unstyled. Add a glob for your app:

```css
@source "./your_project/course_extras/templates/**/*.html";
```

Then run `npm run tailwind_build`. The [landing pages how-to](./landing-pages.md) covers the same
trap.

---

## 4. Use it in content

```markdown
<c-worked-example title="Splitting the bill" difficulty="harder">

Four people share a R480 bill and one of them pays an extra R60 tip. How much does each person pay?

</c-worked-example>
```

Put the tags on their own lines with blank lines around the body, the way the demo content in
`demo_content/` writes `c-admonition`.

Run `content_save` as usual. It does not check widgets or their attributes, so a typo in a tag or
attribute name only shows up when someone looks at the rendered page.

---

## What your widget can rely on

Attribute values arrive as strings. `open="false"` is the non-empty string `"false"`, which is
truthy in a template, so compare against a value rather than testing truthiness.

`content_instance` is in the context whenever a content object's Markdown body renders: the
`Topic`, `Activity`, `Course`, `Form` or `FormContent` that owns the Markdown. The built-in file widgets use it to resolve relative paths:

```django
{% with file_obj=src|get_file_by_path:content_instance %}
    {% if file_obj %}<img src="{{ file_obj.file.url }}" alt="{{ alt }}">{% endif %}
{% endwith %}
```

`request` is `None` when content renders, so there is no logged-in user, no session and no
per-learner state. A widget that needs the learner, for example to show their own progress or
answers, needs a view and htmx, not just a template.

The same pipeline renders form question text and legal documents, and neither of those passes
`content_instance`. A widget that calls `get_file_by_path` with no `content_instance` raises an
error. If authors might use your widget in a form question, guard on `{% if content_instance %}`.

### Treat attributes as untrusted

Authors write the attribute values, and nh3 lets them through as-is once the attribute is
allowlisted. Django autoescapes `{{ title }}`, which is enough for text. Two things undo that:

- Don't mark an attribute `|safe` or wrap it in `{% autoescape off %}`.
- Pass any attribute that ends up in an `href`, `src` or `cite` through the `safe_url` filter
  from `content_tags`, as `c-pull-quote` does. It drops `javascript:` and other unsafe schemes.

---

## Telling your authors

The `fls-content` Claude plugin reads custom widgets from the content repo. For each widget, add a
widget declaration at `.fls-content/widgets/c-<name>.md`, beside `.fls-content.yaml`. The plugin
then accepts the widget and its attributes, and `/fls-content:format-content` can produce it.

The plugin's `custom-widgets.md`
(`claude_plugins/fls-content/skills/widget-reference/resources/custom-widgets.md`) defines the
format and the rules. A declaration for the `c-worked-example` widget from this how-to looks like
this:

````markdown
# `c-worked-example`

A problem statement followed by a solution the learner can reveal. Body is markdown-rendered.

**Allowed attributes:** `title`, `difficulty`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `title` | No | `"Worked example"` | Heading text |
| `difficulty` | No | `""` | Free text shown beside the heading |

```markdown
<c-worked-example title="Splitting the bill" difficulty="harder">
...
</c-worked-example>
```
````

A declaration whose name matches a built-in widget is ignored, and the built-in keeps its
attributes. Whether you generate the declaration files from your project or write them by hand is
up to you.
