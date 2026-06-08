# Runner Interaction & Accessibility Design Research

Scope: exam/test runner for the Freedom Learning System (Django 6 + HTMX 2 + Alpine.js 3 CSP build + Tailwind v4).
Reference design: `/home/sheena/workspace/lms/design/computed/exam/` (desktop/runner.html, desktop/finish.html, mobile/page.html).

---

## 1. Page Navigation Mechanics

### Recommendation: Keep full-page POST/redirect for Next; use a plain GET link for Previous

**Reasoning grounded in the current codebase:**

The current `form_fill_page` view (views.py lines 427-532) already implements the full POST-save-redirect-to-GET pattern (PRG). On POST it calls `form_progress.save_answers(questions, request.POST)` then redirects to the next page URL or calls `form_progress.complete()` and redirects to the results page. This is correct and should be preserved.

The FLS HTMX skill states: "HTMX handles server-side interactions: data fetching, form submission, partial updates" and "Alpine.js handles client-side state". Swapping the entire `<form>` body via HTMX would technically be possible, but it introduces additional complexity without a meaningful payoff for this use case:

- The runner uses a fixed chrome (top bar, progress bar, page dots, footer navigation) that stays constant between pages. Only the question body and page metadata change. An HTMX `hx-target` on the form body area could swap just that region.
- However, doing so means managing the progress bar, page-dot state, and answered-count indicator as server-rendered partials that also update on each swap — adding a `hx-swap-oob` or multiple `hx-target` co-ordination requirement.
- The existing `page_links` context (built in the view, lines 498-517) already serialises all page state cleanly for the full-page render. Keeping full-page navigation keeps this simple.
- HTMX form swap would also require disabling the browser's native scroll-to-top on navigation, then managing focus — work that the full-page redirect handles for free.

**Verdict: retain full-page POST → save → redirect.**

The only reason to prefer HTMX here would be to animate progress-bar growth without a flash, but that is a polish enhancement that can be added later with a CSS transition on the `width` of the fill bar (the design already has `transition:width 300ms` on `.fc-runner-progress .fill`).

### Saving answers before navigating

**Next (POST → save):** The form POSTs to `form_fill_page`. `save_answers()` persists every question on the page. Only then does the redirect happen. This is safe — the learner cannot advance without the current page's answers being written to the database.

**Previous (GET link):** "Previous" must NOT POST the form — it must navigate back without saving the current page's (possibly partially edited) answers over the already-saved state. The current template (`course_form_page.html` line 169) already renders Previous as an `<a href>` link, not a submit button. This is correct.

One edge case: the learner edits answers on page N, clicks Previous (loses the edits), then clicks Next again. The previously-saved answers for page N are restored from the database via `existing_answers_dict()`. That is the correct behaviour for "Previous does not save" — it matches the pattern used by Canvas, Moodle, and other LMSes.

However, to avoid learner confusion, the template should make it visually and textually clear that Previous navigates without saving the current page's changes. A small inline note ("Previous — your unsaved changes on this page won't be kept") or simply making the Previous button visually secondary (ghost style) relative to the primary Next/Submit is sufficient.

### Progress bar and page dots

Both elements are server-rendered on each full-page load using template context:
- `current_page_num` and `total_pages` drive the progress bar percentage (`(current_page_num / total_pages) * 100`).
- The `page_links` list (with `is_current` and `is_accessible` flags) drives the page dots.

On a full-page redirect, these update automatically with no HTMX co-ordination needed. The CSS `transition:width 300ms` on the fill bar can still animate smoothly because the browser paints the new width after the page loads — no JavaScript is needed.

The design (runner.html lines 157-158) shows:
```
.fc-runner-progress .fill{ transition:width 300ms; }
```
This will work with full-page navigation: the browser renders the new fill width and the transition fires as the element appears.

---

## 2. Submit-on-Exit Confirmation Dialog

### Fixed scope reminder

Exit behaviour = SUBMIT ON EXIT. Navigating away mid-test finalises and scores the attempt. A confirmation dialog must warn the learner.

### Recommended pattern: Alpine-driven modal for in-page controls; `beforeunload` for browser-level exits with documented limitations

There are two distinct exit paths to handle, and they require different approaches:

#### Path A: In-page exit controls (the X / "Save & exit" button in the top bar)

This is the normal case. The design shows an X icon button in `.fc-runner-bar .left` that links to the form start page (runner.html line 566):
```html
<a class="fc-icon-btn" href="start_page.html" title="Save & exit">
```

**Recommendation:** Replace this plain anchor with an Alpine-controlled confirmation modal. The button sets a flag (`exitWarning = true`) and the modal renders with two options:

- "Leave and submit" — follows through to `form_progress.complete()` then redirects to the results URL. This can be implemented as a small Django view that accepts a POST to complete and redirect (the same logic as the final page's POST, triggered independently).
- "Keep going" — dismisses the modal, learner stays on the current page.

The FLS Alpine skill specifies the CSP build, which means no inline expressions. The component must be registered in `alpine-components.js`:

```javascript
// student_interface/static/student_interface/js/alpine-components.js
Alpine.data("exitWarning", () => ({
    open: false,
    showExit() { this.open = true; },
    dismiss() { this.open = false; },
}));
```

Template (registered component name in `x-data`, method calls in event handlers per SKILL.md):
```html
<div x-data="exitWarning">
    <button x-on:click="showExit" class="fc-icon-btn" ...>X</button>
    <div x-show="open" x-cloak role="dialog" aria-modal="true"
         aria-labelledby="exit-dialog-title"
         x-on:keydown.escape.window="dismiss">
        <h3 id="exit-dialog-title">Leave the test?</h3>
        <p>Leaving now will submit your current answers and score your attempt. You won't be able to change answers afterwards.</p>
        <button x-on:click="dismiss">Keep going</button>
        <a href="{{ submit_and_exit_url }}">Leave and submit</a>
    </div>
</div>
```

The "Leave and submit" action must POST (not GET) to prevent caching issues. Use a small form with `method="post"` and CSRF, submitted via JavaScript, or a dedicated POST-only Django view URL that `complete()`s the progress and redirects to results. Using an `<a>` tag is shown above for brevity — in implementation it should be a form POST.

#### Path B: Browser navigation away (back button, address bar, tab close, link to another page)

This requires the `beforeunload` event.

**What `beforeunload` CAN do (2024 browser behaviour):**
- Fire when the page is about to be unloaded due to a real browser navigation (address bar, back button, tab close on desktop).
- Show a browser-generic confirmation dialog if `event.preventDefault()` is called (or `returnValue` is set). The text is always browser-controlled — you cannot show a custom message. MDN states: "Browsers display standardized text in the confirmation dialog; the custom message is not shown." ([MDN beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event))
- Only fires if the page has had a user gesture/interaction first (browsers require "sticky activation").

**What `beforeunload` CANNOT reliably do:**
- **Mobile browsers:** Widely unreliable on iOS Safari and Android Chrome. Mobile tabs are regularly backgrounded and killed; `beforeunload` does not fire. ([w3tutorials.net](https://www.w3tutorials.net/blog/is-there-any-way-to-use-window-onbeforeunload-on-mobile-safari-for-ios-devices/))
- **In-app HTMX/Alpine link clicks that don't trigger a full navigation:** If the runner is ever enhanced with HTMX or client-side routing, `beforeunload` will not fire for those navigations. (For FLS's current full-page redirect architecture, every internal navigation IS a full page load, so `beforeunload` WOULD fire on them — but this is why the in-page X button approach above is more reliable and should be the primary mechanism.)
- **Custom dialog text:** Cannot show "Leaving will submit your test" — only a browser chrome message.
- **Chrome's deprecation of unload:** Chrome is progressively deprecating the `unload` event family for bfcache reasons ([Chrome developers](https://developer.chrome.com/docs/web-platform/deprecating-unload)).

**What is realistically achievable:**

| Exit scenario | Reliable interception? | What happens |
|---|---|---|
| In-page X button click | Yes (Alpine modal) | Custom warning dialog before completing |
| In-page nav to another course item | Yes (intercept links in runner, Alpine modal) | Custom warning dialog |
| Browser back button (desktop) | Partial (`beforeunload` fires, generic dialog only) | Generic browser dialog; if dismissed, attempt submitted on next load or via server-side session check |
| Tab close (desktop Chrome/Firefox) | Partial (generic dialog) | Same |
| Mobile tab backgrounded/killed | No | Attempt left incomplete; handled by "submit on exit" logic when learner next visits |
| Address bar navigation (desktop) | Partial (generic dialog) | Same |

**Implementation recommendation for `beforeunload`:**

Add a `beforeunload` listener in the runner template's Alpine component (via `init()` and `destroy()`) that fires only while the runner is active:

```javascript
Alpine.data("runnerPage", () => ({
    _unloadHandler: null,
    init() {
        this._unloadHandler = (e) => { e.preventDefault(); };
        window.addEventListener("beforeunload", this._unloadHandler);
    },
    destroy() {
        window.removeEventListener("beforeunload", this._unloadHandler);
    },
}));
```

The "submit on exit" backend logic: when a learner with an incomplete `FormProgress` returns to the form start page (or any course page), the server should detect the incomplete `FormProgress` and call `form_progress.complete()` before starting a new attempt. This is the most reliable fallback for the mobile / bfcache cases where `beforeunload` never fires. This server-side clean-up at next access is the real safety net; `beforeunload` is a best-effort courtesy warning only.

**Do NOT attempt to intercept navigation in `beforeunload` by calling Django endpoints** — the `beforeunload` callback cannot reliably make synchronous XHR/fetch calls (browsers throttle or block them). Server-side cleanup at next visit is the correct pattern.

---

## 3. Final-Page Review/Submit Dialog

### Dialog placement and trigger

The "Next" button on the final page should open the review/submit dialog rather than immediately POSTing. This matches the design (runner.html line 662: `@click="submit=true"`). In the FLS Alpine CSP build, this becomes:

```javascript
Alpine.data("finalPageRunner", () => ({
    showSubmit: false,
    openSubmitDialog() { this.showSubmit = true; },
    closeSubmitDialog() { this.showSubmit = false; },
}));
```

The "Next" button on the final page calls `openSubmitDialog()` instead of submitting the form directly.

### Recommended wording

Dialog title: **"Ready to submit?"**

Body copy:
> "Once you submit, your answers will be scored and you won't be able to change them. If you'd like to review your work first, you can go back to any page."

Summary panel (showing only truthfully-derivable counts — see section 4 for detail):

```
[N answered]   [M unanswered]
```

Two actions:

1. **"Go back and review"** (ghost/secondary button) — dismisses the dialog. The learner is still on the final page and can use page dots/Previous to navigate back.
2. **"Submit"** (primary button) — submits the form via the standard POST. The form's hidden submit button or a programmatic `form.submit()` call triggers the existing `form_fill_page` POST handler, which calls `form_progress.complete()` and redirects to `course_form_complete`.

**Do not show "Flagged" count** — flagging is out of scope. The design shows it; ignore it.

**"Answered" vs "Unanswered" is derivable from our data:**

For a given `FormProgress`, the server can count:
- Total questions: iterate all pages' children and count `content_type == "FORM_QUESTION"` items.
- Answered: count `QuestionAnswer` objects linked to this `FormProgress`.
- Unanswered = Total - Answered.

This count must be computed server-side and passed in the template context, because the current page's unsaved answers (the learner has seen but not yet clicked Next on the final page) are NOT yet in the database at the time the final page renders. The view should pass `answered_count` and `total_question_count` so the dialog shows the state as of the last save (all pages except the current one's new edits).

Note: this means the dialog may show the final page's questions as "unanswered" even if the learner has filled them in (since they haven't POSTed yet). The dialog should acknowledge this: "Answers on this page will be saved when you submit."

### On "Submit" action

Clicking "Submit" in the dialog should submit the page's form. The form already contains the current page's answers as field values. The standard POST flow handles:
1. `save_answers()` for this final page.
2. `form_progress.complete()` (since there is no `next_page_url`).
3. Redirect to `course_form_complete`.

No separate endpoint is needed.

### Double-submit protection

The Submit button must be disabled after first click to prevent double-submission on slow networks. Use Alpine's `submitting` state flag or a simple `disabled` attribute set via JavaScript on the form's `submit` event. See UX pitfalls section 6 for details.

---

## 4. Autosave / "Saved" Indicator

### What we can show truthfully

The current architecture saves answers only on POST (clicking Next). Answers typed into the current page are held only in the browser's form fields until Next is clicked. Therefore:

**What is true:**
- Answers from all completed (POSTed) pages are safely in the database.
- The current page's answers are NOT saved until Next is clicked.

**What the design shows:** `"5/8 answered · saved"` (runner.html line 571). The "saved" label implies all current answers are persisted, which is false if the learner is mid-page.

### Options and recommendations

**Option A (Recommended): Show "X of N answered" without "saved"**

Show the count of answered questions (derived from `QuestionAnswer` records for the current `FormProgress`) with no "saved" claim. Example: `"5 of 8 answered"`. This is fully truthful — it reflects the persisted state. The current page's in-progress answers are not counted until Next is clicked.

Tradeoff: learners who have filled in the current page see a lower answered count than they've "done", which could feel odd. Mitigate with a note on the progress bar: `"Page 2 of 3 — answers saved when you click Next"`.

**Option B: Add per-keystroke HTMX autosave**

Each question input could fire an HTMX POST (debounced) to a `partial_autosave_answer` endpoint on change. The view would call `form_progress.save_answers()` for that single question and return 200. Then the "answered · saved" indicator would be truthful.

Tradeoff: adds server load and complexity. Every keystroke in a text field would queue a debounced request. The FLS HTMX skill supports this pattern (debounced search input pattern applies). If this is chosen, the HTMX call should use `hx-trigger="change delay:800ms"` on each input, posting to a dedicated autosave URL, with `hx-indicator` showing a brief "saving..." state.

**Option C: Track "dirty" state client-side, show "Unsaved changes"**

Use Alpine's component state to track whether any answer on the current page has been changed since the page loaded (by watching `input` and `change` events). Show "Unsaved changes on this page" when dirty, and "All changes saved" when clean (i.e., the learner hasn't touched anything on this page since it loaded). This is truthful because "clean" means the server does have the last-saved state.

Tradeoff: adds Alpine component complexity; "All changes saved" when no changes have been made on the current page is technically true but could mislead a learner who believes their in-progress edits are saved.

**Spec flag for product decision:** The product owner should choose between A (simpler, fully honest, slightly confusing count), B (fully honest and live, higher complexity), or C (truthful dual-state indicator, moderate complexity). The research recommendation is **Option A** as the default, with Option B noted for forms that have many long-text questions where accidental navigation away is a higher risk.

---

## 5. Accessibility Patterns for the Question UI

### 5.1 Radio groups (multiple_choice)

**Current implementation concern:** The current template (`course_form_page.html` lines 7-23) renders radio buttons as plain `<input type="radio">` elements inside a `<div class="flex items-center">`. There is no `<fieldset>` wrapping the group, and no `<legend>` labelling the question.

**Recommendation:** Wrap each question's options in a `<fieldset>` with a `<legend>` containing the question text. This is the correct semantic structure per WCAG 1.3.1 (Info and Relationships) and WAI-ARIA Authoring Practices. ([W3C WAI Forms Grouping Tutorial](https://www.w3.org/WAI/tutorials/forms/grouping/))

```html
<fieldset>
    <legend>{{ question.rendered_question }}{% if question.required %} (required){% endif %}</legend>
    <div class="fc-choices">
        <div class="flex items-center">
            <input type="radio" id="q{{ question.id }}_opt{{ option.id }}"
                   name="question_{{ question.id }}"
                   value="{{ option.id }}" />
            <label for="q{{ question.id }}_opt{{ option.id }}">{{ option.text }}</label>
        </div>
        ...
    </div>
</fieldset>
```

The keyboard interaction for native `<input type="radio">` is: Tab moves focus to the group (first or currently-selected item), arrow keys move between options within the group, Space selects the focused option. This is handled natively by the browser with no additional JavaScript. ([MDN ARIA radiogroup role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/radiogroup_role))

### 5.2 Checkbox groups (checkboxes)

Same pattern: wrap in `<fieldset>` / `<legend>`. Checkboxes navigate differently from radios — each checkbox is individually focusable via Tab, and Space toggles. This is native browser behaviour requiring no ARIA.

### 5.3 The styled `.fc-choice` divs — critical accessibility issue

The design's `fc-choice` divs (runner.html lines 609-621) use `@click` on `<div>` elements to toggle visual selection state in Alpine, storing the picked value in `x-data`. There are NO real `<input>` elements backing the choices in the design. **This approach is inaccessible by default.**

**Recommendation:** Retain real `<input type="radio">` and `<input type="checkbox">` elements as the authoritative form controls. Use CSS to visually hide the native inputs (`sr-only` in Tailwind) while keeping them focusable, then style the surrounding `<label>` element as the visual choice tile. The Alpine-driven selected state becomes redundant — the native `:checked` CSS pseudo-class drives the `.selected` visual style.

```html
<div class="fc-choices">
    {% for option in question.options.all %}
    <label class="fc-choice" for="q{{ question.id }}_opt{{ option.id }}">
        <input type="radio"
               id="q{{ question.id }}_opt{{ option.id }}"
               name="question_{{ question.id }}"
               value="{{ option.id }}"
               class="sr-only"
               {% if existing answers %}...{% endif %} />
        <div class="fc-choice-marker">{{ forloop.counter|letter }}</div>
        <div class="fc-choice-text">{{ option.text }}</div>
    </label>
    {% endfor %}
</div>
```

With CSS:
```css
.fc-choice:has(input:checked) {
    border-color: var(--color-primary);
    background: rgba(40,53,147,0.04);
}
.fc-choice:has(input:checked) .fc-choice-marker {
    border-color: var(--color-primary);
    background: var(--color-primary);
    color: #fff;
}
```

This approach:
- Is keyboard-operable natively (Tab → into group, arrows → between options).
- Passes form data via standard POST without JavaScript dependency.
- Is announced correctly by all screen readers.
- Has full `:focus-visible` support for keyboard users.

**True/False (2-option multiple_choice):** May use the `.fc-tf` layout. The same label-wrapping-input approach applies — just two large label tiles wrapping radio inputs.

### 5.4 Short text and long text

These are standard `<input type="text">` and `<textarea>` elements. They need associated `<label>` elements (already partially present). The `for`/`id` pairing must be correct. The question text should be the label, not a visual `<span>` floating beside the input.

### 5.5 Focus management when changing pages

On a full-page redirect (GET), the browser focuses the document body or the first focusable element. Screen reader users will hear the page title. To give useful context on page change:

**Recommendation:** Set `tabindex="-1"` on the page heading (`<h2>` showing the page title and number) and call `element.focus()` in a short `DOMContentLoaded` listener. This causes screen readers to announce the page heading immediately. Do not use `aria-live` for this purpose at the same time as focus management — they can conflict ([frontendeng.dev](https://www.frontendeng.dev/blog/15-announcing-changes-for-screen-readers-accessibility)).

```javascript
document.addEventListener("DOMContentLoaded", () => {
    const heading = document.querySelector("[data-runner-page-heading]");
    if (heading) heading.focus();
});
```

Add `data-runner-page-heading` and `tabindex="-1"` to the `<h2>` in the template.

### 5.6 Announcing progress to screen readers

Add a visually-hidden `aria-live="polite"` region that contains the current page progress text (e.g., "Page 2 of 3"). On a full-page load this fires once when the region is inserted, which is acceptable. Do not use `aria-live="assertive"` as it is disruptive.

```html
<div class="sr-only" aria-live="polite" aria-atomic="true">
    Page {{ current_page_num }} of {{ total_pages }}: {{ form_page.title }}
</div>
```

### 5.7 Dialog (review/submit and exit warning) — focus trap and ARIA requirements

Per WAI-ARIA Authoring Practices ([W3C Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)):

Required attributes on the dialog container:
- `role="dialog"`
- `aria-modal="true"`
- `aria-labelledby` pointing to the dialog's `<h3>` heading

Required behaviour:
- Focus must move INTO the dialog when it opens (to the first focusable element, typically the heading or the primary action button).
- Focus must be TRAPPED inside the dialog while open (Tab cycles only within dialog focusables).
- Escape key must close the dialog. (The Alpine skill provides `x-on:keydown.escape.window="close"` — use this.)
- When the dialog closes, focus must return to the element that triggered it (the X button or final-page Next button).

Focus trap implementation: Alpine does not provide a built-in focus trap. A minimal vanilla JS implementation is needed in the `alpine-components.js`:

```javascript
Alpine.data("confirmDialog", () => ({
    open: false,
    _triggerEl: null,
    _focusTrap: null,
    openDialog(triggerEl) {
        this._triggerEl = triggerEl;
        this.open = true;
        this.$nextTick(() => {
            const focusable = this.$el.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            if (focusable.length) focusable[0].focus();
            // Trap focus
            this._focusTrap = (e) => {
                if (e.key !== "Tab") return;
                const els = Array.from(focusable);
                const first = els[0];
                const last = els[els.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault(); last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault(); first.focus();
                }
            };
            this.$el.addEventListener("keydown", this._focusTrap);
        });
    },
    closeDialog() {
        this.open = false;
        if (this._focusTrap) this.$el.removeEventListener("keydown", this._focusTrap);
        if (this._triggerEl) this._triggerEl.focus();
    },
}));
```

**Note on `aria-modal` and browser support:** `aria-modal="true"` tells screen readers that content outside the dialog is inert. However, some older screen reader + browser combinations do not fully honour this and may still allow users to navigate outside. For belt-and-braces coverage, also set `inert` on the non-dialog content (modern browsers support the `inert` attribute natively) when the dialog is open. ([MDN aria-modal](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal))

**Native `<dialog>` element consideration:** The HTML `<dialog>` element with `.showModal()` provides built-in focus trapping, Escape handling, and correct semantics in modern browsers. For a new build, this is the cleaner approach and avoids the manual focus trap above. The Alpine component would call `this.$refs.dialog.showModal()` / `this.$refs.dialog.close()`. Verify target browser support if IE or very old mobile WebViews are a concern — modern FLS deployment targets should be fine.

---

## 6. Common UX Pitfalls for Multi-Page Online Tests

### 6.1 Lost answers on browser Back

**Pitfall:** Learner uses the browser's Back button, which may load a cached version of the previous page without triggering a new GET to the server — their POSTed answers for the forward page may seem to disappear.

**Our mitigation:** The PRG pattern (POST → redirect → GET) ensures that after each save, the browser's current URL is the GET URL for that page. The back button navigates to the previous page's GET URL, which re-renders the form with `existing_answers_dict()` pre-populating all previously saved answers. Answers are not lost — only in-progress edits on the page the learner was on when they hit Back are discarded (same as the Previous button behaviour).

**Additional mitigation:** Add `Cache-Control: no-store` to the runner page responses to ensure the browser does not serve a stale cached version of a page. ([Canvas best practices](https://ceete.engr.wisc.edu/canvas-best-practices-for-online-exams-and-quizzes/))

### 6.2 Accidental submit on the final page

**Mitigation:** The two-step submit dialog (section 3) is the primary guard. The dialog shows answered/unanswered counts, giving the learner one more chance to review. The "Go back and review" action is the default visual focus in the dialog (it is the less destructive option) — the Submit button is the secondary action but labelled clearly.

### 6.3 Double-submit on slow networks

**Pitfall:** Learner clicks Submit, the network is slow, they click again — two POST requests are sent, potentially creating two `FormProgress` completions.

**Mitigation:** Disable the Submit button immediately on first click. In the Alpine component:

```javascript
Alpine.data("submitForm", () => ({
    submitting: false,
    submit(formEl) {
        if (this.submitting) return;
        this.submitting = true;
        formEl.submit();
    },
}));
```

And in the template bind `x-bind:disabled="submitting"` to the Submit button. Also, the server side should be idempotent: if `form_progress.completed_time` is already set, do not call `complete()` again (the current `complete()` method sets `completed_time = timezone.now()` unconditionally — add a guard: `if self.completed_time: return`).

### 6.4 Losing progress on accidental page close (mobile)

**Mitigation:** As discussed in section 2, `beforeunload` is unreliable on mobile. The server-side safety net (completing the attempt on next visit to the form) is the correct mitigation. The spec should document that on mobile, a mid-session close results in the attempt being auto-submitted at the server's next opportunity.

### 6.5 Confusion about which answers are saved

**Mitigation:** Covered in section 4. The progress bar subtext `"Answers saved when you click Next"` sets correct expectations. The answered count reflects only server-confirmed answers.

### 6.6 Page-dot navigation allowing learner to skip ahead past unanswered pages

**Current behaviour:** `page_links` marks pages as `is_accessible` only if `i <= furthest_page`. This prevents forward-skipping past pages that have never been visited. This is correct for a test context.

**Watch for:** If the learner uses the page dots to navigate back to page 1 and then uses the Next button, do they re-save page 1's answers? Yes — every Next button POSTs the current page's answers. This is correct and non-destructive because `save_answers()` uses `get_or_create` then `clear()` + `add()` — it replaces the previous answer with the new one.

### 6.7 Screen reader users not knowing they are in a special "exam" mode

The runner's visual chrome (progress bar, page dots, top bar with exit button) communicates context. For screen reader users, add a visually-hidden heading at the top of the `<main>` element: `<h1 class="sr-only">{{ form.title }} — Question {{ current_page_num }} of {{ total_pages }}</h1>`. This is read when the page loads and orients the learner.

---

## Reference URLs

- [MDN Window: beforeunload event](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event)
- [Chrome: Deprecating the unload event](https://developer.chrome.com/docs/web-platform/deprecating-unload)
- [w3tutorials: window.onbeforeunload on Mobile Safari](https://www.w3tutorials.net/blog/is-there-any-way-to-use-window-onbeforeunload-on-mobile-safari-for-ios-devices/)
- [W3C WAI: Grouping Controls (Forms)](https://www.w3.org/WAI/tutorials/forms/grouping/)
- [MDN: ARIA radiogroup role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/radiogroup_role)
- [MDN: ARIA radio role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/radio_role)
- [W3C WAI ARIA APG: Dialog (Modal) Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- [W3C WAI ARIA APG: Modal Dialog Example](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/)
- [MDN: aria-modal attribute](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal)
- [frontendeng.dev: Announcing page changes for screen readers](https://www.frontendeng.dev/blog/15-announcing-changes-for-screen-readers-accessibility)
- [MDN: ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions)
- [Evinced: Creating accessible styled radio groups](https://www.evinced.com/blog/creating-accessible-styled-radio-groups)
- [Canvas best practices for online exams and quizzes](https://ceete.engr.wisc.edu/canvas-best-practices-for-online-exams-and-quizzes/)
- [UVA LTS: Best Practices for Delivering Online Quizzes and Exams](https://lts-help.its.virginia.edu/m/design-tips/l/1793631-best-practices-for-delivering-online-quizzes-and-exams)

---

status: ok
reason: All six deliverables researched and written, grounded in existing codebase (views.py, models.py, templates, HTMX skill, Alpine CSP skill) and cited web sources.
