# Research: message body format and length

Question from `idea.md` ("Message body"): is the body plain text with line breaks and linked URLs, or markdown rendered through the existing pipeline, and what is the length limit?

## 1. Reusing the existing markdown pipeline

What exists (read in `freedom_ls/markdown_rendering/markdown_utils.py`, `render_markdown(markdown_text, request, context=None)`):

1. `markdown.Markdown` with `fenced_code`, `mdx_headdown`, `tables`, `pymdownx.tasklist`.
2. `nh3.clean` over the whole document, with an allowlist of `nh3.ALLOWED_TAGS` plus every key of the project setting `MARKDOWN_ALLOWED_TAGS` (the `c-*` widget tags and their attributes), plus `input`, `li[class]`, `ul[class]`.
3. django-cotton compile of the cleaned HTML, then a Django template render with the caller's `context` and `request`. The result is trusted output.

Findings:

- The sanitiser is nh3 (not bleach). nh3 sets `rel="noopener noreferrer"` on links by default and strips `javascript:` URLs (its URL scheme allowlist is http, https, mailto and a few others).
- Cotton components do pass through, but only the ones listed in `MARKDOWN_ALLOWED_TAGS`, and only with their listed attributes. That list is for course authors, who are trusted staff. Reusing the pipeline for messages would give any sender (including a learner, once policy allows learner-initiated messages) the course widgets: accordions, flashcards, code blocks, task-list checkboxes, headings, tables, images (`img` is in nh3's default allowlist, so a sender can embed a remote image: a tracking pixel and a way to show content from outside).
- Step 3 is the risk. Sanitised text is then compiled as a Django template. nh3 does not strip `{{ ... }}` or `{% ... %}`, so a message that survives sanitising is rendered as a template against the viewer's context. This is safe for staff-authored course content only because authors are trusted. For user messages it is a template-injection surface (`{% cotton %}` is generated from `c-` tags, but raw `{% %}` text is also evaluated). It could be avoided with `MARKDOWN_TEMPLATE_RENDER_ON=False`, but that is a global setting and would break course widgets.
- Slot content is sanitised a second time inside widgets (`{% markdown slot %}`), so layering is already subtle (see `.claude/agent-memory/ds-code-reviewer/project_markdown_widget_pipeline.md`).

Conclusion: do not send user-authored messages through `render_markdown`. If markdown is ever wanted, it needs a separate, narrow renderer (markdown then `nh3.clean` with tags `p, br, strong, em, ul, ol, li, a, code, blockquote`, no template render). That is new code and new tests for no stated requirement.

Django built-ins for the plain-text option:

- `{{ body|urlize|linebreaksbr }}` or `{{ body|urlizetrunc:40|linebreaksbr }}`. With autoescape on (the default) both filters escape the input first. `urlize` escapes the text, then wraps recognised `http(s)://`, `www.` and bare `name.tld` text and email addresses in `<a href>` with `rel="nofollow"`. It only produces http, https and mailto links, so `javascript:` text is left as inert escaped text. `linebreaksbr` converts `\n` to `<br>` after escaping. Order matters: `urlize` then `linebreaksbr` is fine; both are documented as autoescape-aware (https://docs.djangoproject.com/en/stable/ref/templates/builtins/#urlize, https://docs.djangoproject.com/en/stable/ref/templates/builtins/#linebreaksbr).
- Known `urlize` caveats: it has had repeated denial-of-service advisories on pathological input (very long runs of punctuation or many `@`/`.`), fixed by patch releases (e.g. CVE-2025-27556 and earlier urlize CVEs). A hard length cap on the body bounds that cost. Keep Django patched.
- `urlize` gives `rel="nofollow"` only. Add `target="_blank"` and `noopener` yourself only if wanted; modern browsers treat `target=_blank` as `noopener` by default. For a custom filter, `nh3.clean(urlize(escape(body)), tags={"a"}, attributes={"a": {"href"}}, link_rel="nofollow noopener noreferrer")` would normalise it, but that is optional.
- Phishing: a link in a private message from a person is the main abuse path ("your account is locked, click here"). Mitigations that stay in scope: show the real URL text (plain `urlize` does, whereas markdown `[safe text](evil)` hides it, another argument against markdown), use `urlizetrunc` only with a generous limit, `nofollow`. A "you are leaving FLS" interstitial is not needed for a first cut; reporting and blocking is spec 6.

## 2. What other products use and their limits

Verified by search: Moodle had no message length cap before 3.10.1 / 3.9.4 / 3.8.7 / 3.5.16; a very large message could crash the recipient's browser (CVE-2021-20185), so a cap was added (https://osv.dev/vulnerability/CVE-2021-20185). The exact cap was not confirmed by search.

From general knowledge, not verified in this session (treat as indicative):

| Product | Format | Approximate limit |
| --- | --- | --- |
| Canvas Inbox | Plain text, line breaks kept, URLs linked, attachments separately | very large; no small cap known |
| Moodle personal messages | Plain text with a few formatting options in the editor (emoji, links); stored as HTML-ish/text | capped after CVE-2021-20185 (about 4,096 characters is recalled, unconfirmed) |
| Google Classroom private comments | Plain text, URLs linked | about 20,000 characters is recalled for comments, unconfirmed |
| Slack | mrkdwn / rich text | 40,000 characters |
| Microsoft Teams | rich text, HTML in the backend | about 28 KB per message |
| WhatsApp | Light markers (`*bold*`, `_italic_`), URLs linked | 65,536 characters (text) |
| SMS / push body | plain text | 160 / about 100 visible characters, relevant only for notification text |

Pattern: LMS inboxes treat private messages as plain text with linked URLs. Chat products allow a light markup but cap far above what a teacher-learner message needs. The design's 2,000 characters is conservative and well within the range of "a few paragraphs".

## 3. Effect on the notification and email

- `freedom_ls/comms/models.py` `Notification` holds no message text of its own: `category`, a generic target (`content_type` + `object_id`), a `data` JSON dict, and timestamps. The displayed `message` property is `category.message % data`, where `message` is a translatable template with `%(name)s` placeholders filled from `data` (checked by `message_placeholders`). So the notification shows something like "%(sender)s sent you a message", and the link is built by the category `url_builder` from the target (the conversation).
- The notification is "one per unread conversation, updated not duplicated" (idea.md), so it cannot carry the latest body in any case. Therefore the body format does not affect the notification. Recommend `data` carries only the sender display name and no message excerpt. That also avoids leaking private content into a shared notification centre, email subject lines, or lock-screen pushes, and avoids escaping questions in `%`-formatted templates.
- Email (spec 2) goes out through the notification, so it likewise holds sender name and a link. If a later spec wants an excerpt, plain text is trivial to excerpt (truncate characters, escape); markdown would need rendering or stripping to excerpt. Plain text keeps that door easy.

## 4. Recommendation

Plain text. Store the raw string unmodified (no HTML stored). Render with `{{ message.body|urlize|linebreaksbr }}` (or `urlizetrunc`) under autoescape, inside an element with `overflow-wrap: anywhere` and `white-space` default so long URLs wrap on a 375px screen. No new dependency, no template-render step on user input, no hidden link text, trivially safe in notifications and email.

Length limit: 2,000 characters, matching both design files, with the counter appearing from 1,800. Enforce server side (a `max_length` on the body field or form field, counted in characters after normalising `\r\n` to `\n`, and reject blank or whitespace-only bodies) as well as `maxlength` on the textarea. Server-side enforcement is what matters; the counter is a convenience. Exceeding the limit on send is a 422 HTMX validation error that keeps the typed text, per project convention. Store as `TextField` so the limit can change without a migration; hold the number in one constant or `comms` config setting.

Tests to include: `<script>` and `<img onerror>` text is escaped; `javascript:alert(1)` is not linked; `https://example.com/a?b=1&c=2` is linked with `rel="nofollow"`; newlines produce `<br>`; `{{ 7*7 }}` and `{% load %}` text is shown literally; a body of 2,001 characters is refused.

Open for the spec: whether to add `noopener` / `target=_blank` to links (small custom filter) and whether a message excerpt in the notification is ever wanted (recommend no).

## References

- https://docs.djangoproject.com/en/stable/ref/templates/builtins/#urlize
- https://docs.djangoproject.com/en/stable/ref/templates/builtins/#linebreaksbr
- https://osv.dev/vulnerability/CVE-2021-20185
- Code read: `freedom_ls/markdown_rendering/markdown_utils.py`, `freedom_ls/markdown_rendering/config.py`, `freedom_ls/comms/models.py`

status: ok · reason: complete; competitor limits other than Moodle's uncapped history are from general knowledge and flagged as unverified
