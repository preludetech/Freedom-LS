# Research: Admin UX for Webhook/API Integration Configuration

**Date:** 2026-03-16

---

## 1. Configuration UX Patterns Across Platforms

### 1.1 How Major Platforms Structure Webhook Configuration

**Zapier** treats webhooks as a standard REST resource with CRUD operations. Their key UX decisions:

- **Noun.verb event naming** (e.g., `contact.create`, `contact.update`) gives users predictable, scannable event types.
- **Key-value field mapping**: The left side is the field key, the right side is the value. Previous step data can be inserted into values, creating a visual left-to-right "source to destination" flow.
- **Payload type dropdown**: Users choose between Form (URL-encoded), JSON, or XML. Nested JSON attributes are flattened with double underscores (e.g., `address__city`), which simplifies the mapping UI but can confuse users unfamiliar with the convention.
- **Progressive disclosure**: Start with the most common events; add more later. This prevents configuration overload.

**ThousandEyes** offers one of the clearest preset-vs-custom patterns:

- **Preset dropdown** with options like Generic, Slack, Microsoft Teams, Splunk, AppDynamics. Selecting a preset populates all fields with working sample content.
- **Handlebars templating** in the payload body. The editor provides autocomplete -- typing a character suggests matching variables, and selecting a variable shows available sub-properties.
- **Headers and query parameters** configured as key-value pairs with Handlebars support.
- **Authentication method selector**: None, Basic, Token, or OAuth.
- Important UX caveat: selecting a preset **deletes any existing manual configuration**, which has caused user frustration.

**Marketo (Adobe)** uses a simpler approach:

- **Token insertion button**: Users click "Insert Token" to embed variables like `{{lead.Email Address}}` into URL fields and payload templates.
- **Request Token Encoding dropdown**: Lets users specify how special characters are encoded (JSON vs Form/URL encoding).
- **Response Type selector**: JSON or XML, so the system knows how to parse responses.
- Step-by-step flow: Admin -> Webhooks -> New Webhook -> configure fields -> Create.

**n8n** (open-source workflow automation):

- **Dual URL display**: Shows both test and production webhook URLs at the top of the configuration panel.
- **Random path generation**: Default webhook paths are randomly generated to avoid conflicts.
- **Progressive options**: Core settings visible by default; click "Add Option" to reveal CORS, IP whitelist, binary data handling.
- **Credential separation**: Authentication credentials are managed separately from webhook configuration, referenced by name.

**Retool**:

- **Alias-based custom URLs**: Users can set a human-readable alias that becomes part of the webhook URL.
- **JSON payload access**: Workflow blocks can reference webhook event data using dot notation, matching their existing data reference patterns.
- **Public/private toggle**: Simple switch to enable unauthenticated access when needed.

### 1.2 Common UI Components

Across all platforms, the following components appear repeatedly:

| Component | Purpose | Implementation |
|---|---|---|
| **Endpoint URL field** | Target URL with variable/token support | Text input with autocomplete or token insertion |
| **HTTP method selector** | GET, POST, PUT, PATCH, DELETE | Dropdown |
| **Headers editor** | Key-value pairs for HTTP headers | Repeatable inline key-value rows |
| **Payload template editor** | Request body with variable substitution | Textarea or code editor with syntax highlighting |
| **Authentication config** | Credentials for the target API | Dropdown (None/Basic/Token/OAuth) + credential fields |
| **Event type selector** | Which events trigger the webhook | Checkboxes or multi-select |
| **Test button** | Send a sample request | Button with inline response display |
| **Response/log viewer** | Debug delivery history | Table showing status codes, timestamps, payloads |

### 1.3 Variable/Token Insertion Patterns

Three main approaches exist:

1. **Token button + picker** (Marketo): User clicks a button, selects from a list. Lowest learning curve but interrupts typing flow.
2. **Inline autocomplete** (ThousandEyes): Typing triggers suggestions. Faster for power users but requires learning the trigger character.
3. **Template syntax with documentation** (Zapier, Handlebars): Users type template variables directly (e.g., `{{contact.email}}`). Most flexible but highest error potential.

---

## 2. Common UX Complaints and Challenges

### 2.1 Debugging Is the Biggest Pain Point

- **Silent failures**: Webhooks are fire-and-forget HTTP requests. If there is no logging facility, users have no idea whether delivery succeeded or what went wrong.
- **Delayed error visibility**: The asynchronous nature means errors surface minutes or hours after configuration, not during setup.
- **Reproducing errors locally**: Developers report needing to create entirely separate test environments (e.g., new Shopify stores) just to trigger the same webhook events.
- **Localhost inaccessibility**: Local development servers are not publicly reachable, requiring tunnel tools (ngrok, Hookdeck CLI) that add setup friction.

### 2.2 Payload Format Confusion

- **Content-Type mismatches**: A header claiming JSON but sending XML (or vice versa) causes 400 errors that are hard to diagnose.
- **Malformed payloads**: JSON syntax errors in hand-written templates are extremely common. Users forget commas, mismatch brackets, or incorrectly escape strings.
- **Type mismatches**: Receiving data in unexpected formats (booleans as strings, numbers as strings) causes downstream failures that are not visible in the webhook configuration UI.
- **Encoding issues**: Special characters and non-ASCII content in payloads cause encoding errors that are difficult to trace.

### 2.3 Configuration Management

- **Secret management anxiety**: Users worry about pasting API keys into configuration fields. Questions about how secrets are stored, whether they are encrypted at rest, and who can view them are common.
- **URL rot**: Endpoint URLs become invalid over time (service migrations, expired tokens in URLs), and there is no proactive notification.
- **No version history**: When a webhook configuration breaks, users cannot see what changed or revert to a previous working state.

### 2.4 Testing and Validation

- **No dry-run capability**: Many platforms lack a way to preview what the payload will look like with real data before sending.
- **Mock data idempotency**: Repeatedly testing with the same mock data means clearing test artifacts between runs, tempting users to disable idempotent processing.
- **Missing validation**: Template variables with typos or references to non-existent fields fail silently at delivery time rather than at configuration time.

### 2.5 Timeout and Retry Confusion

- **Slow handler timeouts**: Webhook providers typically enforce 5-10 second timeouts. If the receiving server does synchronous processing before responding, it times out and the provider retries, causing duplicate processing.
- **Retry storm confusion**: Users see multiple deliveries of the same event and do not understand the retry mechanism.

---

## 3. Django Admin Considerations (with Unfold)

### 3.1 JSON Fields in Unfold

Unfold provides basic JSON formatting and syntax highlighting, but **only for read-only fields**. For editable JSON fields, Unfold displays them as plain text using `UnfoldAdminTextareaWidget`. This means a raw JSONField for webhook payload templates will have a poor editing experience out of the box.

**Options to improve this:**

- Install Pygments for syntax highlighting on read-only display.
- Use a custom `PrettyJSONEncoder` to auto-format stored JSON.
- Override the widget with a third-party JSON editor.

### 3.2 Third-Party JSON Editor Widgets

Several Django packages provide better JSON editing in admin:

| Package | Features | Suitability |
|---|---|---|
| **django-jsonform** | Generates a dynamic form from a JSON schema. Supports nested objects, arrays, dynamic choices via callables. | Best for structured config with a known schema. Users fill in form fields rather than editing raw JSON. |
| **django-admin-json-editor** | Renders a JSON editor with schema validation. Supports dynamic schemas via callable functions. | Good for semi-structured data where you want both raw editing and validation. |
| **django-json-widget** | Adds a collapsible, syntax-highlighted JSON tree editor. | Good for viewing/editing arbitrary JSON but no schema enforcement. |

**Recommendation for this project**: `django-jsonform` is the strongest fit because webhook configurations have a known schema (URL, method, headers, body template, auth). You define the schema once and users get a proper form UI instead of raw JSON editing.

### 3.3 Architecture: Inline Models vs JSON Fields

**Option A: JSON field on a single model**

```
WebhookConfig:
  - name: str
  - preset: FK(Preset) | null
  - config: JSONField  # {url, method, headers, body_template, auth}
```

Pros: Simple, single admin page, easy to duplicate/export. Cons: Harder to validate individual fields, less relational integrity, custom widget needed for good UX.

**Option B: Relational models with Django admin inlines**

```
WebhookConfig:
  - name: str
  - url: URLField
  - method: CharField(choices)
  - auth_type: CharField(choices)

WebhookHeader (inline):
  - config: FK(WebhookConfig)
  - key: str
  - value: str

WebhookFieldMapping (inline):
  - config: FK(WebhookConfig)
  - source_field: str
  - target_key: str
  - transform: str | null
```

Pros: Native Django admin UX (no custom widgets needed), validation per field, queryable. Cons: More models/migrations, more complex admin registration, inline editing can be clunky for many headers.

**Option C: Hybrid approach (recommended)**

```
WebhookConfig:
  - name: str
  - preset: CharField(choices) | null
  - url_template: str          # Supports {{variable}} syntax
  - method: CharField(choices)
  - auth_type: CharField(choices)
  - auth_credentials: str      # Reference to secret, not the secret itself
  - headers: JSONField          # Simple key-value, schema-validated
  - body_template: TextField    # Template string with {{variable}} placeholders
  - field_mapping: JSONField    # {source_field: target_key} mapping
```

This keeps top-level fields as proper Django fields (good admin UX, validation, queryability) while using JSONFields only for the parts that are genuinely dynamic (headers, field mapping). The body template is a TextField with template syntax rather than JSON, which is easier for non-technical admins to understand.

### 3.4 Custom Admin Views in Unfold

For features beyond what standard admin provides (e.g., a "Test Webhook" button, delivery log viewer), Unfold supports custom views:

- Inherit from `unfold.views.UnfoldModelAdminViewMixin`.
- Add `title` and `permission_required` properties.
- Register as extra views on the ModelAdmin.

This could power:
- A "Send Test" action that fires a sample payload and shows the response inline.
- A delivery log tab showing recent webhook attempts with status codes and response bodies.
- A "Preview Payload" action that renders the template with sample data without sending.

### 3.5 Secrets Management

Never store API keys or tokens directly in webhook configuration fields. Approaches:

- **Environment variable references**: Store `ENV_VAR_NAME` in the config and resolve at send time.
- **Django settings reference**: Store a key name that maps to a value in `settings` or a secrets backend.
- **Separate credentials model**: A `WebhookCredential` model with encrypted storage, referenced by FK from the webhook config. Display as `****` in admin.

---

## 4. Preset/Template Approach

### 4.1 How Platforms Handle Presets

**ThousandEyes** pattern (most instructive):
- Presets are a dropdown at the top of the configuration form.
- Selecting a preset populates all fields with working defaults for that integration (Slack, Teams, etc.).
- Users can then modify any field. The preset acts as a starting point, not a constraint.
- Warning: selecting a new preset **overwrites** all current field values.

**Zapier** pattern:
- "Zap Templates" are pre-built workflows that connect specific trigger/action pairs.
- Templates use sample data from the selected trigger/action methods.
- Users customize the mapping after selecting a template.

**n8n** pattern:
- Base workflows serve as templates that are duplicated and customized per user.
- Templates are full workflow definitions, not just configuration presets.

### 4.2 Design Recommendations for FLS

A two-tier approach works well:

**Tier 1: Presets (e.g., "Brevo", "Slack", "Generic HTTP")**

- Stored as data (not code) so new presets can be added without deployment.
- A preset defines: default URL pattern, method, headers, body template, auth type, and field mapping.
- Selecting a preset populates the form but all fields remain editable.
- Store the preset name/version on the config so you can notify users when a preset is updated.
- Include a "Reset to Preset Defaults" action for when users want to undo their customizations.

**Tier 2: Fully Custom**

- The "Generic HTTP" preset (or no preset) gives users a blank slate.
- All the same fields are available; they just are not pre-populated.
- Power users who understand HTTP and the target API can configure from scratch.

### 4.3 Preset Storage Options

**Option A: JSON fixtures**
- Presets stored as JSON files in the repo, loaded via management command.
- Pros: Version controlled, reviewable in PRs. Cons: Requires deployment to update.

**Option B: Database model**

```
WebhookPreset:
  - name: str
  - slug: str
  - version: str
  - description: str
  - default_config: JSONField  # All default values
  - is_active: bool
```

- Pros: Admins can create/edit presets without deployment. Cons: Not version-controlled by default.

**Option C: Hybrid** -- Ship built-in presets as fixtures, allow admin-created presets in the database. Built-in presets are marked as non-editable and can be updated via migrations.

---

## 5. Key Takeaways

1. **Test button is non-negotiable.** Every platform provides one. Users will not trust a webhook config they cannot test. Include inline response display (status code, response body, timing).

2. **Use proper form fields, not raw JSON.** The biggest UX improvement over a plain JSONField is rendering a structured form. `django-jsonform` or the hybrid model approach both achieve this.

3. **Template variable autocomplete matters.** Even a simple "available variables" reference panel next to the body template field dramatically reduces errors. Full autocomplete is ideal but a documented list is the minimum.

4. **Separate secrets from configuration.** Never display or store raw credentials in the webhook config form. Use references to a credentials store.

5. **Presets should populate, not constrain.** Users should be able to start from a preset and modify everything. Track which preset was used so you can offer "reset to defaults" and notify about preset updates.

6. **Delivery logging is essential for debugging.** Without it, users are debugging blind. At minimum, log the last N deliveries with timestamp, status code, request payload, and response body.

7. **Validate templates at save time.** Check that template variables reference real fields, that JSON templates produce valid JSON, and that URLs are well-formed. Surface errors in the admin form, not at delivery time.

---

## 6. Django Admin Implementation Patterns (Unfold-Specific)

### 6.1 Unfold Custom Widgets and Inline Forms

Unfold is built on Tailwind CSS and provides a comprehensive set of admin customization features:

**Custom Form Widgets**: Unfold includes a custom template pack for `django-crispy-forms`, allowing forms to be styled consistently with the Unfold design system. It provides built-in support for `ArrayField` (from `django.contrib.postgres.fields`) and WYSIWYG editing via the Trix editor.

**Inline Tabs**: Unfold supports grouping inlines into tabbed navigation on the change form, which is useful for organising related models (e.g., headers, field mappings, delivery logs) as separate tabs on a webhook config page.

**Paginated Inlines**: Large record sets within inlines can be paginated, which is relevant for delivery log inlines that could grow large.

**Conditional Fields**: Unfold has built-in support for dynamically showing/hiding fields based on other field values without custom JavaScript. Configuration is declarative via a `conditional_fields` dictionary on the ModelAdmin:

```python
class WebhookConfigAdmin(ModelAdmin):
    conditional_fields = {
        # Show auth_credentials only when auth_type is not "none"
        "auth_credentials": "auth_type != none",
        # Show custom_url only when preset is "custom"
        "custom_url": "preset == custom",
    }
```

This is directly useful for webhook config forms where auth credential fields should only appear when an auth type is selected, or custom URL fields only appear when no preset is chosen.

**Sources**:
- [Unfold Conditional Fields Documentation](https://unfoldadmin.com/docs/configuration/conditional-fields/)
- [Unfold ModelAdmin Options](https://unfoldadmin.com/docs/configuration/modeladmin/)

### 6.2 Adding a "Send Test" Button to Django Admin

There are three main approaches, with Unfold's changeform actions being the best fit:

**Approach 1: Unfold Changeform Actions (Recommended)**

Unfold provides `actions_detail` -- action buttons that appear at the top of the change form page for individual objects. This is ideal for a "Send Test" button:

```python
from unfold.admin import ModelAdmin
from unfold.decorators import action

class WebhookConfigAdmin(ModelAdmin):
    actions_detail = ["send_test_webhook"]

    @action(
        description="Send Test",
        url_path="send-test",
        attrs={"target": "_blank"},  # optional
    )
    def send_test_webhook(self, request, object_id):
        webhook_config = self.get_object(request, object_id)
        # Fire test payload, capture response
        result = send_test(webhook_config)
        # Return response or redirect with message
        ...
```

Unfold also supports actions with intermediate forms -- when the button is clicked, a form is displayed where users can provide additional input (e.g., select which sample data to use for the test). This uses `@action` with a custom form class.

**Approach 2: Custom Admin View (for richer UI)**

For more complex UI (e.g., showing the request/response inline without a page reload), use a custom admin view:

```python
from unfold.views import UnfoldModelAdminViewMixin

class SendTestWebhookView(UnfoldModelAdminViewMixin, View):
    title = "Send Test Webhook"
    permission_required = "webhook.change_webhookconfig"

    def post(self, request, object_id):
        # Execute test, return JSON response for HTMX
        ...
```

Register it as an extra view on the ModelAdmin and trigger it via HTMX from a custom button in the change form template.

**Approach 3: Override response_change (simplest but limited)**

Override `response_change()` in ModelAdmin to detect a custom submit button:

```python
def response_change(self, request, obj):
    if "_send_test" in request.POST:
        result = send_test(obj)
        self.message_user(request, f"Test sent: {result.status_code}")
        return HttpResponseRedirect(request.path)
    return super().response_change(request, obj)
```

This requires adding a custom submit button to the change form template. It works but provides less control over the UX compared to Unfold's built-in action system.

**Sources**:
- [Unfold Changeform Actions](https://unfoldadmin.com/docs/actions/changeform/)
- [Unfold Action with Form Example](https://unfoldadmin.com/docs/actions/action-form-example/)
- [Haki Benita - Custom Action Buttons in Django Admin](https://hakibenita.com/how-to-add-custom-action-buttons-to-django-admin)
- [Django Admin Cookbook - Custom Action Buttons](https://books.agiliq.com/projects/django-admin-cookbook/en/latest/action_buttons.html)

### 6.3 Code/Template Editor Widgets for Django Admin

For editing Jinja2 body templates, a code editor widget provides syntax highlighting and a better editing experience than a plain textarea.

**Option 1: django-ace (Ace Editor)**

The most mature Django integration for the Ace editor:

```python
from django_ace import AceWidget

class WebhookConfigForm(forms.ModelForm):
    class Meta:
        model = WebhookConfig
        widgets = {
            "body_template": AceWidget(
                mode="jinja2",      # Syntax highlighting mode
                theme="chrome",     # Light theme for admin
                width="100%",
                height="300px",
                wordwrap=True,
                showprintmargin=False,
            ),
        }
```

Ace supports a `jinja2` syntax mode out of the box, which is ideal for our Jinja2 body templates. The widget is a drop-in replacement for `Textarea` and works in Django admin without additional template overrides.

There is also `django-ace-overlay` which uses an overlay/modal for editing, keeping the form layout cleaner for large templates.

**Option 2: CodeMirror**

Several packages exist but most target CodeMirror 5 (legacy). CodeMirror 6 is the current version but Django widget support is limited:

- `django-codemirror-widget` -- basic Textarea replacement with CodeMirror, supports configuration via options dict
- `django-codemirror2` -- similar, provides `CodeMirrorEditor` widget
- `djangocodemirror` -- more full-featured, uses "configuration sets" to manage options

For CodeMirror 6, there is no mature Django widget package yet. A CodeMirror 6 integration would require a custom widget that loads CM6 from npm/CDN and initialises it on the textarea. A discussion on the CodeMirror forum confirms this is a common need but no standard solution exists.

**Option 3: Custom lightweight approach (no package)**

For simple syntax highlighting without a full editor, use a custom widget that loads a syntax highlighter (e.g., Prism.js or highlight.js) and applies it to the textarea on focus/blur. This is lighter weight but provides no editing features (line numbers, auto-indent, bracket matching).

**Recommendation**: `django-ace` with mode `jinja2` is the best fit. It is well-maintained, supports the exact syntax mode we need, and integrates cleanly with Django admin forms.

**Sources**:
- [django-ace on GitHub](https://github.com/django-ace/django-ace)
- [django-ace-overlay on GitHub](https://github.com/ninapavlich/django-ace-overlay)
- [Mr. Coffee - Custom Code Editor in Django Admin](https://mrcoffee.io/blog/code-editor-django-admin)
- [django-codemirror-widget on PyPI](https://pypi.org/project/django-codemirror-widget/)
- [CodeMirror Forum - CM6 Django Widget](https://discuss.codemirror.net/t/implement-cm6-editor-via-django-widget/8196)

### 6.4 Preset/Template Selector That Populates Other Fields

The goal is a dropdown where selecting a preset (e.g., "Brevo", "Slack") auto-fills the URL, method, headers, and body template fields.

**Approach 1: JavaScript data-attributes on options (Recommended)**

Store preset data as `data-*` attributes on the `<option>` elements, then use JavaScript to read them and populate fields on change:

```python
class PresetSelectWidget(forms.Select):
    """Select widget that stores preset config data on each option."""

    def __init__(self, presets: dict, *args, **kwargs):
        self.presets = presets
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value in self.presets:
            # Store preset data as JSON in a data attribute
            option["attrs"]["data-preset"] = json.dumps(self.presets[value])
        return option

    class Media:
        js = ("admin/js/preset_selector.js",)
```

The companion JavaScript listens for the dropdown change event, reads `data-preset`, parses the JSON, and sets the values of the other form fields. This requires no AJAX calls and works offline.

**Approach 2: AJAX endpoint**

When the dropdown changes, fire an AJAX request to a Django view that returns the preset data as JSON. The JavaScript callback then populates the form fields. This is better when preset data is large or needs to be loaded dynamically, but adds latency and requires a server round-trip.

**Approach 3: Unfold conditional fields + preloaded values**

Use Unfold's conditional fields to show/hide preset-specific field groups, combined with JavaScript to populate values. This is more complex but provides the cleanest UX when different presets have different field requirements.

**UX Consideration**: Always show a confirmation dialog before populating fields if the user has already made manual edits. The ThousandEyes research (Section 4.1) found that silently overwriting user changes is a major source of frustration.

**Sources**:
- [abidibo.net - Data Attributes on Django Admin Select Options](https://www.abidibo.net/blog/2017/10/16/add-data-attributes-option-tags-django-admin-select-field/)
- [Simple is Better Than Complex - Dependent Dropdown Lists](https://simpleisbetterthancomplex.com/tutorial/2018/01/29/how-to-implement-dependent-or-chained-dropdown-list-with-django.html)
- [Creating Custom Django Form Widgets with Responsive Behaviour](https://enzedonline.com/en/tech-blog/creating-custom-django-form-widgets-with-responsive-front-end-behaviour/)

### 6.5 Masked Secrets in Django Admin Forms

For fields like API keys, signing secrets, or auth tokens, the admin should never display the full value after initial entry.

**Approach 1: Custom widget that masks on display**

```python
class MaskedSecretWidget(forms.TextInput):
    """Shows asterisks for existing values, allows entering new ones."""

    def __init__(self, mask_char="*", visible_chars=4, **kwargs):
        self.mask_char = mask_char
        self.visible_chars = visible_chars
        super().__init__(**kwargs)

    def format_value(self, value):
        if value and len(value) > self.visible_chars:
            masked = self.mask_char * 8 + value[-self.visible_chars:]
            return masked
        return value
```

Combined with form logic: if the submitted value is all asterisks (unchanged), keep the existing database value. If it contains new text, update the stored value.

**Approach 2: Django's built-in PasswordInput**

`forms.PasswordInput(render_value=False)` renders an `<input type="password">` that browsers display as dots. Setting `render_value=False` means the field is always empty on page load -- the user must re-enter the value to change it. This is the simplest approach but does not indicate whether a value is already set.

**Approach 3: Read-only display + separate edit action**

Display the masked value as read-only text (e.g., `"****abcd"`) and provide a separate "Change Secret" button/link that opens a modal or inline form for updating. This is the most secure approach as the secret never appears in a form field that could be inspected via browser dev tools.

**Approach 4: Reference-based (no secret in admin at all)**

Store only a reference key (e.g., `BREVO_API_KEY`) that maps to an environment variable or secrets manager. The admin form shows a dropdown of available secret names, never the actual values. This is the most secure pattern and aligns with the recommendation in Section 3.5.

**django-auditlog note**: If using audit logging, configure it to mask sensitive fields so secrets do not appear in audit trails. django-auditlog supports a `mask_fields` option that replaces the first half of field values with asterisks.

**Sources**:
- [Django PasswordInput Widget](https://runebook.dev/en/articles/django/ref/forms/widgets/django.forms.PasswordInput)
- [Django Forum - Hide Password Field in Admin](https://forum.djangoproject.com/t/hide-password-field-on-django-admin-dashboard/13336)
- [django-auditlog - Masking Sensitive Fields](https://django-auditlog.readthedocs.io/en/latest/usage.html)

### 6.6 Jinja2 Template Validation Errors in Admin

Webhook body templates use Jinja2 syntax. Validation should catch syntax errors at save time, not at delivery time.

**Server-side validation in the form's clean method:**

```python
import jinja2

class WebhookConfigForm(forms.ModelForm):
    def clean_body_template(self):
        template_str = self.cleaned_data.get("body_template", "")
        if not template_str:
            return template_str

        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        try:
            env.parse(template_str)
        except jinja2.TemplateSyntaxError as e:
            raise forms.ValidationError(
                f"Template syntax error on line {e.lineno}: {e.message}"
            )

        # Optionally validate that referenced variables exist
        ast = env.parse(template_str)
        referenced_vars = jinja2.meta.find_undeclared_variables(ast)
        allowed_vars = {"event", "payload", "user", "timestamp"}
        unknown_vars = referenced_vars - allowed_vars
        if unknown_vars:
            raise forms.ValidationError(
                f"Unknown template variables: {', '.join(sorted(unknown_vars))}. "
                f"Available variables: {', '.join(sorted(allowed_vars))}"
            )

        return template_str
```

Key points:

- **`env.parse()`** checks syntax without rendering. It catches unclosed tags, invalid expressions, and malformed blocks.
- **`jinja2.meta.find_undeclared_variables()`** extracts all variable names referenced in the template, allowing validation that only known context variables are used.
- **`jinja2.StrictUndefined`** causes rendering to fail on undefined variables (useful at delivery time as a safety net, not needed for parse-time validation).
- **`TemplateSyntaxError`** provides `lineno` and `message` attributes, which should be surfaced in the admin error display so users can locate the problem.

**Validating that the rendered output is valid JSON:**

If the body template is expected to produce JSON, add a second validation step:

```python
def clean_body_template(self):
    template_str = self.cleaned_data.get("body_template", "")
    # ... syntax validation as above ...

    # Try rendering with sample data and check JSON validity
    env = jinja2.Environment(undefined=jinja2.Undefined)
    try:
        template = env.from_string(template_str)
        sample_context = self._get_sample_context()
        rendered = template.render(**sample_context)
        json.loads(rendered)  # Validate JSON structure
    except json.JSONDecodeError as e:
        raise forms.ValidationError(
            f"Template renders invalid JSON: {e.msg} at position {e.pos}"
        )
    except jinja2.UndefinedError:
        pass  # Variables not in sample context; skip JSON check

    return template_str
```

**Client-side validation (optional enhancement):**

For immediate feedback while typing, use the Ace editor's built-in annotation system to show errors in the gutter. This requires a small JavaScript addition that sends the template text to a validation endpoint via AJAX and displays returned errors as editor annotations.

**Linting tools**: The `jinjaninja` package provides a Jinja2 linter that checks for common mistakes and bad coding style beyond pure syntax errors, though it may be overkill for webhook templates.

**Sources**:
- [Jinja2 API - Environment.parse()](https://jinja.palletsprojects.com/en/stable/api/)
- [Snyk - TemplateSyntaxError usage](https://snyk.io/advisor/python/Jinja2/functions/jinja2.exceptions.TemplateSyntaxError)
- [jinjaninja - Jinja2 template linter](https://github.com/ramonsaraiva/jinjaninja)
- [Django Form and Field Validation](https://docs.djangoproject.com/en/6.0/ref/forms/validation/)

---

## References

- [Beeceptor - Webhook Architecture Design Pattern](https://beeceptor.com/docs/webhook-feature-design/)
- [Zapier Engineering - Add Webhooks to Your API the Right Way](https://zapier.com/engineering/webhook-design/)
- [Zapier - How to Get Started with Webhooks](https://help.zapier.com/hc/en-us/articles/8496083355661-How-to-get-started-with-Webhooks-by-Zapier)
- [Zapier - Send Webhooks in Zaps](https://help.zapier.com/hc/en-us/articles/8496326446989-Send-webhooks-in-Zaps)
- [Zapier Platform - Zap Templates](https://platform.zapier.com/publish/zap-templates)
- [Hookdeck - Guide to Troubleshooting and Debugging Webhooks](https://hookdeck.com/webhooks/guides/guide-troubleshooting-debugging-webhooks)
- [CodeHook - 5 Common Webhook Errors and How to Fix Them](https://www.codehook.dev/blog/5-common-webhook-errors-and-how-to-fix-them)
- [WebhookDebugger - Common Webhook Errors (2025 Guide)](https://www.webhookdebugger.com/blog/common-webhook-errors-and-how-to-fix-them)
- [ThousandEyes - Custom Webhooks](https://docs.thousandeyes.com/product-documentation/integration-guides/custom-webhooks)
- [Adobe Marketo - Create a Webhook](https://experienceleague.adobe.com/en/docs/marketo/using/product-docs/administration/additional-integrations/create-a-webhook)
- [n8n - Webhook Node Documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [n8n - Webhook Credentials](https://docs.n8n.io/integrations/builtin/credentials/webhook/)
- [Retool - Trigger Workflows with Webhooks](https://docs.retool.com/workflows/guides/webhooks)
- [Retool - Build UI on Any REST API](https://retool.com/use-case/rest-api-ui)
- [Unfold - JSON Field](https://unfoldadmin.com/docs/fields/json/)
- [Unfold - ModelAdmin Options](https://unfoldadmin.com/docs/configuration/modeladmin/)
- [Unfold - Custom Pages](https://unfoldadmin.com/docs/configuration/custom-pages/)
- [django-jsonform Documentation](https://django-jsonform.readthedocs.io/en/stable/fields-and-widgets.html)
- [django-admin-json-editor (PyPI)](https://pypi.org/project/django-admin-json-editor/)
- [django-json-widget (PyPI)](https://pypi.org/project/django-json-widget/)
- [Forth CRM - Configuring Webhooks](https://support.forthcrm.com/hc/en-us/articles/12854382172051-Configuring-WebHooks)
- [FluentCRM - Webhook Integration](https://fluentcrm.com/docs/webhook-integration/)
- [Salesforce Break - Declarative Webhooks](https://salesforcebreak.com/2025/08/04/simplify-salesforce-integrations-with-declarative-webhooks/)
- [Contentful - Configure a Webhook](https://www.contentful.com/developers/docs/webhooks/configure-webhook/)
- [Contentstack - Webhook Payloads 101](https://www.contentstack.com/blog/tech-talk/webhook-payloads-101-components-integration-tips-and-best-practices)
