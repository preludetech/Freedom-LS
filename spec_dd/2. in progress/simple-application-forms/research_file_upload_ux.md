# File-upload UX inside the paged application form

Scope: what the applicant sees and does when a `FormQuestion` asks for a file — a scan or phone photo
of an ID/passport — inside the new plain `course_applications` form runner (not the exam runner). Does
not repeat `research_multistep_ux.md`'s general multi-step findings or its anti-pattern table, and does
not re-argue anything `research_draft_and_submit_semantics.md` already settled (paged form, review page
as page N+1, `completed_time` as draft/submitted, `save_answers` called on every POST).

**Model shape is out of scope here** — a sibling research file settles whether a file hangs directly off
`QuestionAnswer` (e.g. a `FileField`) or off a child row (e.g. `QuestionAnswer.file_answer`, a
`OneToOneField`). Everywhere below that the answer depends on that choice, it is flagged and phrased so
it survives either one. The working name `QuestionType.FILE` is used for the new type; it does **not**
join `FREE_TEXT_QUESTION_TYPES` (`freedom_ls/form_engine/enums.py:22`) — a file is a third storage
shape, not a fifth free-text field, so it must not silently pick up the frozenset's free-text behaviour
in `submissions.py`, `save_answers`, `get_incorrect_quiz_answers`, or the reports modules the way
`NUMBER` correctly did (`research_question_types_and_validation.md` §2–3).

## 1. `save_answers` will eat the upload — traced, and how the design prevents it

Trace, with the exact call chain a plain page re-POST takes:

1. `form_fill_page`'s POST branch (`freedom_ls/learner_interface/views.py:1106`, and the
   `course_applications`-side equivalent this spec is building) calls
   `form_progress.save_answers(questions, request.POST)` on **every** POST of a page, unconditionally —
   this is deliberate and already relied on (`research_draft_and_submit_semantics.md` row 6).
2. Inside `save_answers` (`freedom_ls/form_engine/models.py:290-311`), each question on the page is
   checked with `has_submitted_answer(question, post_data)` (`freedom_ls/form_engine/submissions.py:23-32`).
3. `has_submitted_answer` branches on `question.type in FREE_TEXT_QUESTION_TYPES`; a file question falls
   to the `else` arm, `bool(submitted_option_ids(question, post_data))`, which reads
   `post_data.getlist(f"question_{question.id}")` — i.e. `request.POST`. A file's bytes live in
   `request.FILES`, never in `request.POST`, and browsers do not repopulate `<input type="file">` on a
   re-render — there is no value to resubmit even in principle, not even the filename. So
   `has_submitted_answer` reads **False** for a file question on every POST of that page after the
   file's own request has already saved it.
4. Back in `save_answers`: `if not has_submitted_answer(...): self.answers.filter(question=question).delete(); continue`.
   That delete is not a bug for the four existing types — it is the documented, load-bearing behaviour
   that keeps a cleared text box or unchecked radio from leaving a stale row behind. For a file question
   it deletes the row that owns the applicant's uploaded ID scan, on the very next "Next" click, or on
   the re-render that follows an unrelated required-field rejection on the *same* page, or on any later
   page's POST if `questions` is ever widened past "this page's questions" (it currently is not, but the
   review page's whole-form check in §7 iterates every question, and must not reuse `save_answers` to do
   it for exactly this reason).

**This settles the shape of the whole feature: a file must never ride the page's own POST body.** It is
uploaded (and removed) through its own endpoint, its own request, independent of "Next"/"Previous". Two
changes follow from the trace, not one:

- **The upload/remove endpoints own the file's `QuestionAnswer` row entirely.** They `get_or_create`/
  delete it directly, outside `save_answers`.
- **`save_answers` (or its caller) must skip file questions outright** — not "treat an empty POST value
  as meaningful," but "never inspect this question's row at all when processing a page POST." The
  cleanest seam is the same one `has_submitted_answer` already uses: an explicit
  `if question.type == QuestionType.FILE: continue` ahead of the existing `FREE_TEXT_QUESTION_TYPES`
  branch, so nothing about the four existing types' behaviour changes. Whether that guard lives in
  `save_answers` itself or in the `questions` iterable the view passes in (filtering `FILE` questions
  out before calling `save_answers` at all) is an implementation choice; either is correct, and either
  keeps `save_answers`'s delete-on-blank behaviour exactly as load-bearing as it is today for the other
  four types.

One consequence falls out for the markup in §2: because the "attached" state's partial contains no
`<input type="file">` at all (only Replace/Remove controls), a native "Next" submit of the surrounding
`<form id="runner-page-form">` posts nothing named `question_{id}` for an already-attached file question
— which is exactly what the guard above expects, and needs no `enctype="multipart/form-data"` on that
outer form. The file's own multipart POST is a separate request from a separate element with its own
`hx-encoding`; the page form stays plain `application/x-www-form-urlencoded`, unchanged from today.

## 2. The upload interaction

A fifth partial, `form-input-file`, sits beside `form-input-multiple-choice` / `-checkboxes` /
`-short-text` / `-long-text` in `course_form_page.html` and is dispatched from `form-question`
(`freedom_ls/learner_interface/templates/learner_interface/course_form_page.html:128-144`) the same way
`NUMBER` will be — one more `{% elif question.type == "file" %}` branch, otherwise the
`ERROR! UNHANDLED FORM TYPE` fallback (`:142`) fires. It composes into the new plain application-runner
shell exactly like the other four (`research_draft_and_submit_semantics.md` §6).

The whole widget is one self-swapping fragment, `hx-target="this"` / `hx-swap="outerHTML"` (the house
pairing, `claude_plugins/django-stack/skills/htmx/SKILL.md:70-78`), so its own request never touches
anything outside itself:

```html
{% partialdef form-input-file %}
<div id="question-{{ question.id }}-file" hx-target="this" hx-swap="outerHTML">
    {% with answer=existing_answers|get_dict_item:question.id %}
    {% if answer and answer.file %}
        {# Attached — the only "has a file" state; see below for why there is no separate "pending scan" state. #}
        <div class="flex items-center justify-between gap-3 p-3 rounded-md border border-border bg-surface">
            <div class="flex items-center gap-2 min-w-0">
                <c-icon name="success" class="size-5 text-forest flex-none" aria_label="Attached" />
                <span class="truncate text-on-surface" data-testid="attached-filename">{{ answer.original_filename }}</span>
                <span class="text-sm text-muted flex-none">{{ answer.file.size|filesizeformat }}</span>
            </div>
            <div class="flex items-center gap-2 flex-none">
                <c-button variant="secondary" size="small"
                          hx-get="{% url 'course_applications:application_file_replace' application.pk question.id %}">
                    Replace
                </c-button>
                <c-button variant="error" size="small"
                          hx-delete="{% url 'course_applications:application_file_remove' application.pk question.id %}"
                          hx-confirm="Remove this file?">
                    Remove
                </c-button>
            </div>
        </div>
    {% else %}
        <label class="sr-only" for="question_{{ question.id }}_file">{{ question.rendered_question }}</label>
        <input type="file"
               id="question_{{ question.id }}_file"
               name="file"
               accept="image/jpeg,image/png,application/pdf"
               data-testid="file-input"
               hx-post="{% url 'course_applications:application_file_upload' application.pk question.id %}"
               hx-encoding="multipart/form-data"
               hx-trigger="change"
               hx-indicator="#question-{{ question.id }}-progress"
               hx-disabled-elt="#runner-page-form button[type='submit']"
               {% if question.required %}required{% endif %} />
        <div id="question-{{ question.id }}-progress"
             class="htmx-indicator"
             x-data="fileUploadProgress">
            <div class="h-1.5 bg-border rounded-pill overflow-hidden">
                <div class="h-full bg-secondary rounded-pill" x-bind:style="barStyle"></div>
            </div>
        </div>
    {% endif %}
    {% endwith %}
</div>
{% endpartialdef %}
```

Notes on each piece:

- **Two states only: empty, and attached.** No "uploading" state is drawn separately from empty (the
  progress bar overlays the empty state via `hx-indicator`/`.htmx-request`), and — this is the load
  bearing call for decision 5 — **no distinct "pending scan" state either.** A file that is quarantined
  and not yet marked clean renders identically to a file that has been marked clean: the same "Attached"
  card, same filename, same Replace/Remove. The applicant has no action available that depends on scan
  status (they cannot re-scan it, and decision 5 already puts review in the Django admin, not on this
  page), so surfacing "pending" copy would raise a question they cannot resolve — exactly the kind of
  unhelpful internal-machinery exposure `.claude/skills/brand-guidelines/SKILL.md` warns against
  ("Name the specific problem. Suggest a specific fix."). There is no problem to name yet and no fix for
  the applicant to make. **They can continue immediately after a successful upload** — nothing in the
  paging, the required check (§7), or submission gates on scan status; scan status is read only by
  whoever reviews the application later, in the admin decision 5 and 6 already assign it to.
- **Progress indicator and its event.** `hx-indicator` toggles the container's opacity via HTMX's own
  `.htmx-request`/`.htmx-indicator` CSS (`claude_plugins/django-stack/skills/htmx/SKILL.md:134-153`);
  the bar's *width* is driven by `htmx:xhr:progress`, per the existing CSP-build convention of listening
  in a registered component's `init()` (`freedom_ls/base/static/base/js/alpine-components.js:170-172,
  185-189` — the `dropdownMenu`/`modal` pattern of `this.$el.addEventListener("htmx:afterRequest", ...)`
  generalises directly to `htmx:xhr:progress`), not an inline `x-on:htmx:xhr:progress`:

  ```javascript
  // freedom_ls/course_applications/static/course_applications/js/alpine-components.js
  document.addEventListener("alpine:init", () => {
      Alpine.data("fileUploadProgress", () => ({
          percent: 0,
          barStyle() {
              return `width: ${this.percent}%`;
          },
          init() {
              this.$el.closest("[hx-target]").addEventListener("htmx:xhr:progress", (event) => {
                  if (event.detail.lengthComputable) {
                      this.percent = Math.round((event.detail.loaded / event.detail.total) * 100);
                  }
              });
          },
      }));
  });
  ```

  `course_applications` has no `static/`/`alpine-components.js` yet (`freedom_ls/course_applications/`
  currently has none — checked); this is the first component it needs, loaded the same way every other
  app-scoped file is, via `{% block extra_alpine_components %}` on the new plain shell template
  (mirroring `_exam_runner_base.html:16-27`), not via `_base.html`.
- **`hx-disabled-elt`** (htmx 2.x — https://htmx.org/attributes/hx-disabled-elt/) disables the page's
  own Next/Submit button for the duration of the upload request. Without it, the applicant could click
  Next while the upload is in flight; the two requests don't corrupt each other's data (§1's fix means
  the page POST never touches the file row), but navigating away mid-upload can abort the in-flight
  request in some browsers, silently losing the attach.
- **`accept="image/jpeg,image/png,application/pdf"`**, not `image/*` — see §4 for why `image/*` is too
  wide for iOS's HEIC edge case, and §3 for why `accept=` is a UI filter only, never a control.
- **Replace** re-fetches the empty-input state (`hx-get` back to a GET that returns the `{% else %}`
  branch of this same partial) rather than clearing in place — the applicant needs the native file
  picker again, which only a fresh `<input type="file">` in the DOM provides.
- **Remove is a real delete of the `QuestionAnswer` row**, not a null-out of a field on a row left
  behind. §7 explains why this specific detail is what keeps the required check and
  `get_current_page_number` correct without a file-specific branch in either.

## 3. Validation feedback

- **`accept=` is a picker filter, not a gate.** It only affects which files the OS-native chooser
  offers; a renamed extension or a file dragged/dropped (if drag-drop is ever added) bypasses it
  trivially. Every check that matters runs server-side, in the dedicated upload view.
- **Type**: read magic bytes, not the browser-supplied `Content-Type` — this was already the right call
  when files were designed the first time and stays right now that they're back in scope
  (`research_form_schema.md:139`, recommending `python-magic`/libmagic over trusting the multipart
  header). Reject anything outside a small allowlist (JPEG, PNG, PDF).
- **Size**: an explicit `if uploaded_file.size > MAX_BYTES` check in the view, where `MAX_BYTES` is
  chosen at or below whatever this deployment's `DATA_UPLOAD_MAX_MEMORY_SIZE`/edge cap is (see below) —
  otherwise the size check the view can actually reach is dead code for the failure mode that matters
  most on mobile.
- **On either failure, HTTP 422 re-rendering the same partial's empty-input branch, plus an inline
  message.** This is the FLS HTMX convention —
  `claude_plugins/django-stack/skills/htmx/SKILL.md:63-66`, "**422** for validation errors on HTMX
  requests" — applied exactly the way `form_fill_page` already applies it for the required-answers
  check (`freedom_ls/learner_interface/views.py:1243`, `status=422 if required_answers_error else 200`).
  Because the widget's own `hx-target="this"` / `outerHTML` pairing scopes the swap to just this one
  field, the 422 response is the whole `#question-{{ question.id }}-file` div again — empty-input
  markup plus e.g. `<p class="text-sm text-error">That doesn't look like a JPEG, PNG or PDF — try a
  different file.</p>` — not a page-wide re-render, and not the 422 the page-level required check
  produces for the other four types (§7's check is a separate, whole-form concern).
- **What happens when the request never reaches the view at all — the case the 422 convention can't
  cover.** Production pins `DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE = 5_242_880` (5
  MB) in lock-step with the edge's own `request_body max_size 5MiB` Caddy directive
  (`config/settings_prod.py:53-54`; `EDGE-7`,
  `spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/research_contract_conformance.md:37`). A body over
  that ceiling is rejected by the edge with a bare 413 before Django's routing ever runs — no view, no
  422, no partial. Even where Django is directly reachable (dev, or a non-file part of the multipart
  body alone exceeding the setting), Django raises `RequestDataTooBig` (a `SuspiciousOperation`) the
  first time something touches `request.POST`/`request.FILES`, which for a POST happens inside Django's
  own request machinery before the upload view's body executes — the result is a generic "Bad Request
  (400)", with no view-rendered content at all. HTMX's default handling of any non-2xx response is to
  fire `htmx:responseError` and leave the DOM target untouched, so without an explicit listener the
  applicant sees nothing happen — the button doesn't restyle, no message appears, the spinner just stops.
  **This failure must be prevented from leaving the browser, not styled after the fact**: check
  `file.size` against the same `MAX_BYTES` in a `change` listener before `hx-post` fires at all, and
  short-circuit with the identical "try a smaller file" copy the server-side check would produce, so the
  two paths read as one to the applicant. Wire a document-level `htmx:responseError` fallback for the
  rare case something still slips through (a stale client-side constant, a body that's technically under
  the file-size cap but pushes the multipart envelope over it) — but it is a backstop, not the design.

## 4. Mobile

- **`accept="image/jpeg,image/png,application/pdf"`, no `capture` attribute.** The applicant uploads "a
  scan or a phone photo" — a scan is very often a PDF from a scanning app or the Files app, which never
  arrives through a camera capture. Setting `capture="environment"` forces the camera and skips the
  gallery/Files chooser entirely, which would make "or a scan" impossible on mobile. Leaving `capture`
  off is what lets iOS Safari and Android Chrome present their full native chooser — "Take Photo",
  "Photo Library", and "Browse"/Files — for the same `<input>`.
- **iOS**: a photo taken live through the chooser is converted to JPEG on the way into the form
  regardless of the device's HEIC/"High Efficiency" camera setting — this conversion has been Safari's
  behaviour for form file inputs for years, precisely so web forms don't have to handle HEIC. A photo
  picked from the Photos library is converted the same way. The one gap `accept=` alone doesn't close is
  "Browse" into the Files app reaching an already-HEIC file saved there directly (e.g. AirDropped to
  Files rather than the Photos library) — narrow, and the server-side type check in §3 rejects it with a
  clear message rather than needing special handling.
- **Android**: Chrome's chooser offers Camera and a gallery/Files picker the same way; camera output is
  JPEG. Some OEM camera apps default to HEIF, caught by the same server-side allowlist.
- **Size is the real mobile cost, and it collides with the 5 MB ceiling from §3.** A modern phone
  camera's default-quality JPEG is routinely 2–8 MB — very plausibly over the deployment's 5 MB cap on
  the applicant's very first attempt, and (per §3) that specific failure is the one HTMX renders worst.
  Tell the applicant what helps, next to the input, before they take the photo — concrete and
  actionable, not a generic warning: *"A clear photo of the whole page, under 5 MB. If your camera's
  photo quality is set to 'High' or 'Max', switching it to 'Medium' before taking the photo usually gets
  it under the limit."* Do not build client-side image compression/resizing for v1 — a canvas-based
  downscale-and-re-encode pipeline is a real, if small, feature nothing else in this form needs, and
  "Don't build functionality that is not explicitly requested" (`CLAUDE.md`) applies squarely. Flag it as
  the honest follow-up if this ceiling turns out to reject a meaningful share of first attempts.
- **Rotation is not this feature's problem to solve twice.** Portrait phone photos carry an EXIF
  `Orientation` tag rather than physically rotated pixels; every evergreen browser already respects it
  when rendering an `<img>`, which covers the one place this form displays the file at all if §6's "no
  thumbnail" recommendation is followed. The one place EXIF orientation silently breaks is a
  server-generated thumbnail via Pillow, which does not auto-rotate unless `ImageOps.exif_transpose()`
  is called before resizing — moot as long as no such pipeline is built (§6), and the one line that
  matters if it ever is.

## 5. Leaving and coming back

A file answer is durably saved the instant its own upload request succeeds — before the page's "Next" is
ever clicked, unlike the other four types, which only persist once the surrounding page's POST is
handled by `save_answers`. So leaving the page immediately after a successful upload (browser back, tab
close, session timeout) never loses it, whereas the same interruption on a half-typed text answer loses
whatever wasn't yet POSTed — that asymmetry is inherent to "own endpoint, own request" (§1), not a
separate feature.

- **`existing_answers_dict`** (`freedom_ls/form_engine/models.py:274-288`) needs no file-specific
  branch: it already does `QuestionAnswer.objects.get(form_progress=self, question=question)` per
  question with no awareness of type, so whatever holds the file — a `FileField` directly on that row,
  or a related child reached via e.g. `answer.file_answer` — is reachable through the exact same
  `existing_answers` dict the other four partials already read via
  `existing_answers|get_dict_item:question.id` (`course_form_page.html:50, 80, 102, 112`). Only the
  *partial* branches per type (reading `answer.file` instead of `answer.text_answer`); the view-side
  context-building step this dict comes from does not, regardless of which model shape wins.
- **`get_current_page_number()`** (`:251-272`) is likewise type-blind: `if not
  self.answers.filter(question=question).exists(): return idx + 1`. A file question with an attached
  file reads as "answered" the same way a saved text answer does, with no special case — **provided**
  §1's fix holds and §7's "Remove deletes the row" discipline holds, so that "a row exists" keeps meaning
  "this question has a real answer" exactly as it already does for the other four types. If either of
  those slips — if `save_answers` is ever allowed to touch file rows, or Remove is implemented as
  "blank a field on a row left behind" instead of deleting the row — the consequence is not merely a
  wrong required-check: it reproduces `research_draft_and_submit_semantics.md` §3's "resume walks
  backward" defect specifically for file questions, dragging the applicant back to the file's page on
  every future session even though they attached it. This is the sharpest reason §1 and §7's row-deletion
  discipline are not independent nice-to-haves — they are the same invariant, load-bearing in two places.
- **An uploaded-but-unanswered-elsewhere page** is not a distinct case: once the corrected
  `furthest_page` logic from `research_draft_and_submit_semantics.md` §3 is applied to the resume
  redirect (not yet true of `form_start`'s bare call today, per that note), a file question's answer row
  counts toward "answered so far" exactly like any other question's row, on whichever page it happens to
  sit relative to other unanswered pages. Nothing about resume ordering treats file questions specially.

## 6. The check-your-answers page

- **Filename and size, a download link, no thumbnail.** `answer.original_filename` (or the equivalent
  the sibling model-shape research names) plus `answer.file.size|filesizeformat`, next to
  `<c-icon name="download">` (an existing semantic icon,
  `claude_plugins/fls-dev/skills/icon-usage/SKILL.md:40`), linking to the streaming download view below.
  No thumbnail: building one means a Pillow-based derivative pipeline (with the EXIF-rotation trap from
  §4) for a page whose whole point, per `idea.md`, is a plain, minimal review step — a filename and a
  working download link tell the applicant exactly what was attached without that cost. This also
  matches `idea.md`'s own framing that the concrete first deployment, not FLS, owns anything beyond the
  mechanism.
- **The download link is the same permission-checked streaming pattern the admin reviewer's link uses,
  not a raw storage URL** — the `user_uploads` bucket's read policy is "Private, signed URLs or streamed
  by Django" (`claude_plugins/fls-dev/skills/file-storage/SKILL.md:27`), and `FileResponse(...,
  as_attachment=True, filename=...)` with `Cache-Control: private, no-store, must-revalidate`
  (`freedom_ls/reports/views.py:109-132`, `download_report_view`) is the concrete house pattern for
  exactly this shape of "stream a private file to whoever is allowed to see it." Two thin views should
  share one streaming helper and differ only in their permission check — the applicant's view checks
  "is this my own `CourseApplication`'s answer" (a 404 for anyone else, matching `application_status`'s
  own-application-only check, `freedom_ls/course_applications/views.py:76`), and the admin reviewer's
  view is wired the way `reports/admin.py:114-134` wires `download_report_view` — through
  `self.admin_site.admin_view(...)`, staff-gated, no separate public URL. Writing the streaming logic
  once and branching only the permission check is what "Avoid repeating code" (`CLAUDE.md`) asks for
  here.
- **Letting the applicant re-open their own file is fine, deliberately.** They already possess the
  original (it's their own ID; they could photograph it again in a minute), so there is no
  confidentiality boundary between "you already have this" and "here it is again" — no extra
  confirmation step, no rate-limit beyond whatever the streaming view already needs for abuse in
  general.
- **The Change link does nothing file-specific.** Per `research_draft_and_submit_semantics.md` §4, every
  Change link is an ordinary `<a href>` back to that question's own page, and walking forward again lands
  back on review because it's next in sequence — no `?return=review` machinery. For a file question,
  landing back on its page shows the "Attached" card from §2 (via `existing_answers_dict`, §5), whose own
  Replace/Remove controls are already the mechanism for changing it. Nothing new is needed at the review
  page beyond the same link every other question type already gets.

## 7. The required check

`FormQuestion.required` (`freedom_ls/form_engine/models.py:145`) has no type-specific meaning today —
the per-page check computes `has_submitted_answer` against `request.POST`
(`freedom_ls/learner_interface/views.py:1098-1102`), which is exactly the check §1 shows cannot be
reused for a file question at all (there is nothing file-shaped in `request.POST` even when the file is
correctly attached). The whole-form required check `research_draft_and_submit_semantics.md` §5 places on
the review page's POST handler is not `request.POST`-shaped in the first place — the review page's own
POST carries no per-question answers, only "confirm and submit" — so it has to read from what's already
stored, per question, the same way `get_current_page_number` already does:
`self.answers.filter(question=question).exists()`.

That existence check is correct for a file question with **zero** file-specific code, on one condition
this spec must hold regardless of which model shape wins: **a `QuestionAnswer` row's existence must mean
"this question has a real answer,"** exactly the invariant `save_answers` already maintains for the
other four types by deleting rather than leaving a blank row. Concretely:

- If the file lives directly on `QuestionAnswer` (e.g. a `FileField`), **Remove must delete the row**,
  not clear the field and leave an empty row behind — an empty row would read as "answered" to both
  `get_current_page_number` and this required check with nothing attached.
- If the file lives on a child row, **Remove must delete the child, and whatever creates that child must
  never eagerly create the parent `QuestionAnswer` without one** — otherwise a parent row can exist with
  no child, and a bare `self.answers.filter(question=question).exists()` reads "answered" incorrectly.
  This is the one place the model-shape choice actually surfaces in code: it decides whether the generic
  existence check the other four types already share is sufcient as-is, or needs one
  `question.type == QuestionType.FILE` branch that checks the child relation instead of the parent row.
  Either way, the fix is contained to this one check, not spread through `get_current_page_number` or
  `save_answers`.

**Naming the error is unchanged from every other required question.** The whole-form check surfaces
outstanding questions the same way `_unanswered_required_message` already phrases the per-page one
(`views.py:1027-1033`) — by `question.question_number()` — "Question 4 needs an answer before you can
continue." A file question is a question like any other in that list and that copy; nothing distinguishes
"you didn't answer this" from "you didn't attach a file for this" in the message, because the file's own
page (§2) already carries the only copy that matters at the point of actually doing something about it.

status: ok
