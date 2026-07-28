---
description: Use when making HTMX interactions
---

# HTMX Conventions

## Global Setup

HTMX is loaded globally in `_base.html`. CSRF is handled globally via `hx-headers` on the `<body>` tag:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

Never add CSRF tokens to individual HTMX requests.

**On the `<c-*>` tags in the examples below:** they are illustrative placeholders for whatever
components this project defines — `ds` does not ship a component library and guarantees no component
name. Check `templates/cotton/` (project-level and app-local) for what actually exists, and fall back
to plain HTML elements where it doesn't.

## View Conventions

### Detecting HTMX Requests

```python
is_htmx = request.headers.get("HX-Request") == "true"
```

### Returning Responses

Use standard `render()` by default:

```python
def partial_comment_list(request, slug):
    # ...
    return render(request, "app/partials/comment_list.html", context)
```

Use `render_to_string()` only when composing HTML strings into a larger response (e.g., panel systems that assemble multiple partials):

```python
content = render_to_string("app/partials/panel.html", context, request=request)
```

### Dual Rendering (HTMX vs Full Page)

When a view serves both HTMX and full-page requests, return partial content for HTMX and the full wrapped response for normal requests:

```python
def render(self, request, ...) -> str:
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return self.get_content(request, ...)
    return self.get_full_response(request, ...)
```

### Naming

Prefix view functions/methods returning HTMX partials with `partial_` (e.g., `partial_comment_list`, `partial_article_row`).

### HTTP Status Codes

- **200** for successful responses
- **422** for validation errors on HTMX requests

## Template Patterns

### Always Specify `hx-target` and `hx-swap` Together

```html
<div hx-get="{% url 'app:endpoint' %}"
     hx-target="#content"
     hx-swap="outerHTML">
```

Prefer `outerHTML` as the swap strategy.

### Load on Page Load

```html
<div hx-get="{% url 'app:partial_endpoint' %}"
     hx-trigger="load"
     hx-target="#content"
     hx-swap="outerHTML"
     hx-indicator="#loader">
    <c-loading-indicator id="loader" message="Loading..." />
</div>
```

### Form Submission

```html
<form hx-post="{% url 'app:submit' %}"
      hx-target="#result"
      hx-swap="outerHTML">
    <c-button type="submit">Submit</c-button>
</form>
```

### Debounced Search Input

```html
<form hx-get="{{ base_url }}"
      hx-target="#table-container"
      hx-trigger="submit, input delay:300ms from:#search-input"
      hx-include="#search-input"
      hx-swap="outerHTML">
    <input type="search" id="search-input" name="search" />
</form>
```

### State Preservation via URL Query Params

Preserve sort, search, and pagination state in query parameters, not request bodies:

```html
<a hx-get="{{ base_url }}?sort=name&order=asc&page=2"
   hx-target="#table-container"
   hx-swap="outerHTML">
    Sort by Name
</a>
```

### Disabling HTMX for Specific Links

Use `hx-boost="false"` on links that should do full-page navigation (e.g., admin, external links):

```html
<c-button href="/admin/" hx-boost="false">Admin Panel</c-button>
```

## Loading Indicators

HTMX drives loading state with two classes it applies itself, no JavaScript required:

- `.htmx-request` is added to the element issuing the request (or to the element named by
  `hx-indicator`) for the duration of that request.
- `.htmx-indicator` marks an element that should only be visible while a request is in flight — HTMX's
  own stylesheet gives it `opacity: 0` and raises it to `opacity: 1` under `.htmx-request`.

### Standalone Loading Indicator

Point `hx-indicator` at the element that should show the spinner:

```html
<div hx-get="{% url 'app:data' %}"
     hx-trigger="load"
     hx-indicator="#loader">
    <span id="loader" class="htmx-indicator">Loading data…</span>
</div>
```

**If the project has a loading-indicator component, use it instead of hand-rolling one** — check
`templates/cotton/` (project-level and app-local) before writing the markup above.

### Inline Button Loading State

For a button that swaps its label while submitting, toggle two spans on the `.htmx-request` state. The
project may already express this as a component prop (e.g. a `loading` / `loading_text` prop on its
button component) or as a pair of CSS utility classes — **check what exists before adding either.** If
nothing exists, the underlying mechanism is:

```css
/* in the project's Tailwind entry or components stylesheet */
.htmx-request .htmx-hide-on-request { display: none; }
.htmx-show-on-request { display: none; }
.htmx-request .htmx-show-on-request { display: inline; }
```

## Separation of Concerns

- **HTMX** handles server-side interactions: data fetching, form submission, partial updates
- **Alpine.js** handles client-side state: dropdowns, modals, toggles, visibility

Do not use Alpine.js for things that should be server round-trips, and do not use HTMX for purely client-side UI state.

## Testing HTMX Interactions

Simulate HTMX requests in tests by setting the `HX-Request` header:

```python
response = client.get("/endpoint/", HTTP_HX_REQUEST="true")
```

Assert that HTMX responses return partial content without full-page wrappers:

```python
assert "<section" not in response.content.decode()
```
