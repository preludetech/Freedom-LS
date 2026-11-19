# Research: best practices for the Account area on panels

Items marked (fetched) were read from the cited page this session. Items marked (general) are
established practice from memory and were not re-verified against a page.

## 1. Account area information architecture

- (general) Keep one "Account" area with a left sidebar on wide screens. Group by task, not by
  system: "Personal details" (name, picture), "Email", "Password". Later "Public profile" belongs
  in a visibly separate group, so private settings and public presentation are never mixed.
- (general) Use plain-language labels that say what the user changes. "Profile" is ambiguous once a
  public profile exists. Prefer "Personal details" (private) vs "Public profile" (visible to
  others), and use the same word in the page `<h1>`, the sidebar item, the `<title>` and the user
  menu link.
- (general) Every section is a real URL (bookmarkable, back button works, allauth pages already
  work this way). That favours a sidebar of links over client-side tabs. Tabs suit a few sibling
  views on one page; a sidebar scales to the later sections and mixes with allauth's separate
  pages. Inside a section, use a stack of panels.
- (general) On narrow screens the sidebar collapses to a top list or disclosure; keep it a `<nav>`
  of links, not a `<select>`.
- (general) Show the signed-in identity (email) at the top of the area so the user knows which
  account they are editing.

## 2. Inline edit vs form page, and confirmation feedback

- (general) Inline edit (a panel switching between read and edit state) suits small, independent
  groups of fields such as name. Dedicated form pages suit security-sensitive or multi-step flows
  (email, password), which is what allauth already gives. Mixed use inside one shell is common
  (GitHub, Google account settings).
- (general) Each panel saves independently with its own Save and Cancel; after success return to
  the read state showing the new values. Keep the unsaved values and focus on the first invalid
  field when validation fails.
- Confirmation: WCAG 4.1.3 Status Messages requires that success messages be announced without
  moving focus. (fetched) ARIA22: put `role="status"` on a container that exists before the message
  is inserted; it implies `aria-live="polite"` and `aria-atomic="true"`; adding an explicit
  `aria-atomic="true"` helps some environments. Test that the container is present before the
  message appears.
- (general) Use `role="alert"` (assertive) only for errors that block the user. For a saved name,
  announce politely ("Name saved") through the single page announcer and also show the refreshed
  read-state panel. The visible refreshed panel is the primary confirmation; the announcer
  covers screen readers. Do not use both a toast and a live region saying the same thing.
- (general) After swapping a panel, move focus deliberately: to the panel heading or the Edit
  button after save, to the first error (or an error summary) after a 422. Never leave focus on a
  removed element.
- (general) Error messages: associate with fields via `aria-describedby`, set `aria-invalid="true"`,
  and do not rely on colour alone.

## 3. Accessible sidebar navigation

- (fetched) W3C APG navigation landmark example: if a page has more than one `navigation`
  landmark each needs a unique label (`aria-label` or `aria-labelledby` pointing at a heading).
  The site header nav and the account sidebar nav are two landmarks, so label the sidebar
  e.g. "Account".
- (general) Mark the current page link with `aria-current="page"` (not just a CSS class), and
  style the active state from `[aria-current="page"]` so the visual and the semantics cannot
  drift. When a section has sub-pages, use `aria-current="true"` or `page` on the matching item
  only. APG's navigation example does not itself cover `aria-current`; see the MDN reference.
- (general) Render the sidebar as `<nav><ul><li><a>`; allauth pages (email, password) must mark
  their item current too, so the active key has to be derivable from the URL name or from a
  context variable the override sets.
- (general) Keep a single `<h1>` per page; the sidebar heading is not an `<h1>`.

## 4. Wrapping allauth views without forking

- (fetched) allauth docs: add a project template folder to `TEMPLATES["DIRS"]`; Django searches
  `DIRS` before `APP_DIRS`, so project copies win. Two layouts extend `allauth/layouts/base.html`:
  `entrance.html` (login, signup) and `manage.html` (email, password and other account management
  pages). Overriding `allauth/layouts/manage.html` re-skins every management page at once, which
  is exactly the intended seam. Built-in templates use `{% element %}` tags (h1, button, field,
  form, panel, ...) that resolve to `allauth/elements/*.html`; override those only if styling
  must change, because they affect entrance pages too.
- (fetched) The docs do not list the layout's block names. Read the installed
  `allauth/templates/allauth/layouts/manage.html` for the exact `{% block content %}` and
  title blocks, and copy only what is needed; extend the project shell and keep the same block
  names so allauth page templates (`account/email.html`, `account/password_change.html`) fill in
  unchanged.
- (general) Pin the django-allauth version range and add a test that renders `account_email` and
  `account_change_password` as a logged-in user and asserts the shell, sidebar and `aria-current`
  are present, so an allauth upgrade that renames a block fails loudly. Note downstream theme
  overrides of the layout in upgrade notes.
- Views, forms, URLs, emails: unchanged. (fetched) Names: `account_email` (`/accounts/email/`),
  `account_change_password` / `account_set_password` (users without a usable password are
  redirected between the two; an account created without a password will see "set password").
- Rate limits (fetched, `ACCOUNT_RATE_LIMITS`): defaults `change_password` 5/m/user,
  `manage_email` 10/m/user, `reauthenticate` 10/m/user, `login_failed` 10/m/ip,5/5m/key,
  `confirm_email` 1/3m/key. Setting a dict overrides only the keys listed; `False` disables all.
  Wrapping templates must not bypass these because the views stay allauth's; the rate-limit
  response page also renders through allauth templates, so check it looks right in the shell.
  Allauth's limit does not protect Django admin login.
- Reauthentication: allauth can require a recent login before sensitive actions (my page fetch
  returned 404, so the specifics are unverified; read the installed docs/source for the
  reauthentication views and templates, `account/reauthenticate.html`). Those pages use the
  `manage` layout, so they inherit the shell; make sure the sidebar highlights something sensible
  (or nothing) there.
- (general) The shell must not assume `request.user` has an educator profile, and must tolerate
  allauth pages passing no panel context (no announcer content, but the live region host should
  still render so later HTMX content can use it).
- (general) Pre-registration pages (login, signup, reset, confirm) keep `entrance.html`; only
  `manage.html` changes.

## 5. Profile-picture upload and remove UX and validation

- (general) Show the current picture (or initials fallback) at the display size used elsewhere;
  buttons "Upload new picture" / "Remove picture"; preview before save is nice but optional.
  Make removal a confirmation dialog or an undoable single action, naming the effect
  ("Remove your profile picture?"). The framework's dialog host is the natural fit.
- (general) State limits next to the control: accepted types (JPEG, PNG, WebP), maximum size,
  suggested dimensions. Use `accept="image/*"` as a hint only; never as validation.
- (general) Server validation (OWASP unrestricted-file-upload guidance, page fetch redirected, so
  summarised from knowledge): check size before reading fully (Django `DATA_UPLOAD_MAX_MEMORY_SIZE`
  / `FILE_UPLOAD_MAX_MEMORY_SIZE` and a form-level cap), verify content by decoding with Pillow
  (`ImageField` does `verify()`), allow-list formats, ignore the client filename and content type,
  generate a random storage name, re-encode or strip EXIF (location data!) where practical, cap
  pixel dimensions to avoid decompression bombs (`Image.MAX_IMAGE_PIXELS`), serve from media
  storage with no execute permission and `X-Content-Type-Options: nosniff`.
- (general) Replacing a picture should delete the old file after the new one saves; removal clears
  the field and deletes the file. Keep this behaviour as shipped (the idea says to keep it).
- (general) Errors (wrong type, too large) appear next to the field, announced, and the old
  picture stays unchanged until a save succeeds. HTMX multipart uploads need `hx-encoding="multipart/form-data"`.
- (general) Alt text for the picture is the user's name or empty (decorative) when the name is
  adjacent; avoid "profile picture of ...".

## 6. HTMX 422 validation responses

- (fetched) htmx 2 does not swap 4xx/5xx by default: `responseHandling` default
  `{code:"[45]..", swap:false, error:true}`, so a 422 body is ignored and `htmx:responseError`
  fires. To swap 422 bodies, either add `{"code":"422","swap":true}` before the `[45]..` entry in
  `htmx-config` / `htmx.config.responseHandling`, or set `evt.detail.shouldSwap = true` and
  `isError = false` in an `htmx:beforeSwap` listener, or use the response-targets extension.
  The project already returns 422 for validation errors, so confirm the global config swaps 422
  into the panel (not only `isError=false`), then test with a 422 panel save.
- (general) Return the re-rendered edit form (with errors, submitted values and edit state) with
  status 422, targeting the panel itself so no layout shift occurs; return 200 plus the read
  state on success. Use `HX-Retarget`/`HX-Reswap` only if the error target differs from the
  success target.
- (general) Non-HTMX fallback: the same view should return a full page 422 or redirect-with-message
  so the page works without JS where feasible. Auth and 404 rules apply identically to both.

## 7. Private account settings vs public profile

- (general) Different URLs, different labels, different audiences: the account area is only the
  owner (404 for everyone else); the public profile is a read page whose content the owner
  controls. Do not host the public profile's visibility switches inside "Personal details".
- (general) Never leak private fields (email, last login) into public templates; build the public
  profile from an explicit allow-list of fields rather than the user model.
- (general) In the sidebar, put public-profile sections under their own heading ("Public profile")
  with a link "View my public profile" opening the public page, which makes the privacy boundary
  visible. Default new public fields to private/opt-in.
- (general) Name collision: the account name panel edits the user's real name; if the public
  profile shows a display name, say on both panels which name appears where ("Shown on your public
  profile" vs "Only you see this").
- (general) Self-edits writing no audit log is consistent with the idea; still rely on allauth's
  own email notifications for email/password changes.

## Recommendations for the spec

1. Use sidebar links (own URLs) plus a panel stack per page, not tabs.
2. Label: "Account" area, "Personal details", "Email", "Password"; reserve "Public profile".
3. Single announcer in the shell for save confirmations, with the refreshed read-state panel as the
   visible confirmation; focus management specified for save and 422.
4. Sidebar `<nav aria-label="Account">` with `aria-current="page"`; active state styled from that attribute.
5. Override only `allauth/layouts/manage.html`; read the installed allauth's block names; add a
   render test for email, password and reauthentication pages; record the override in upgrade notes.
6. Confirm the global htmx config swaps 422; test the panel 422 path.
7. Keep existing image validation, state limits in the UI, and use the dialog host for removal confirmation.

## References

- https://docs.allauth.org/en/latest/common/templates.html (fetched)
- https://docs.allauth.org/en/latest/account/views.html (fetched)
- https://docs.allauth.org/en/latest/account/rate_limits.html (fetched)
- https://docs.allauth.org/en/latest/account/reauthentication.html (404; unverified)
- https://www.w3.org/WAI/ARIA/apg/patterns/landmarks/examples/navigation.html (fetched)
- https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA22 (fetched)
- https://htmx.org/docs/#validation (fetched)
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-current (general, not fetched)
- https://community.owasp.org/vulnerabilities/Unrestricted_File_Upload (redirect target, not fetched)

status: ok
