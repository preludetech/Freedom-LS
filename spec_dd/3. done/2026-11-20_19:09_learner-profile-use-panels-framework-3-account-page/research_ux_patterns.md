# Research: UX patterns for a self-service account area

Topic `ux_patterns`. Settled by `answers.md`: the area is "Account"; the sidebar lists Personal details, Email, Password (later Public profile); each sidebar entry is its own page with one panel stack (no tabs). The header user menu link becomes "Account".

Evidence quality: most web sources are practitioner blogs, vendor docs and forum threads, not controlled studies. Treat them as directional. Where I found no source, I say so and give a reasoned recommendation.

## 1. Sidebar on mobile

Options seen in the wild:
- Drawer (slide-out): common when the sidebar has many entries. Its trigger must be easy to spot, and its close-on-navigate behaviour needs testing (a Shopify report describes a drawer that stayed open after navigation).
- Section picker (a select): suggested for a short list of sections.
- Top list (horizontal scroll or full-page list that navigates to each section): common for settings.
- Full-screen settings list on mobile, then drill into a section (Intercom's redesign).
- Stacked dropdowns confuse users (Discourse preferences thread).

Recommendation for this area: a short list (3 entries now, perhaps 5 to 6 later) suits a plain list of links above the content below `md` (stacked, wrapping or horizontally scrollable, with the active entry marked), not a drawer. A drawer hides navigation and costs a tap on a three-item area. Switch to a select or drawer only if the list passes about 6 entries. Because each entry is its own page (a settled answer), a link list works with no JavaScript. A `<select>` that navigates on change needs JS and is harder to make accessible. Check whether `panel_framework/partials/sidebar_nav` already has a mobile behaviour, and reuse it before building one.

## 2. Active-state marking

- Mark the current entry with `aria-current="page"` and a visual cue that is not colour alone (weight, a left bar or background fill, brand token colours).
- Do the same in the mobile list.
- Entries owned by allauth (Email, Password) must be marked from the URL name, so the same sidebar partial works on allauth pages.

## 3. Page titles and headings

- Each page has one `<h1>` that names the page ("Personal details", "Email", "Password"). The area name "Account" appears as the sidebar heading or breadcrumb and in `<title>` ("Personal details - Account - <site>"), so tabs and screen-reader page titles differ per page.
- The sidebar label and the page `<h1>` should match, so a user sees where they landed.
- Panels inside the page carry their own `<h2>` ("Name", "Profile picture").
- Per the brand voice: sentence case, plain words. "Personal details" is private by name, which keeps "Profile" free for the public profile.

## 4. Inline edit vs always-editable fields

- Always-editable fields with an explicit Save are the lowest-risk pattern for a small form (two name fields). They need no mode switch, work without JavaScript, and are the easiest to make keyboard- and screen-reader-friendly.
- Click-to-edit (read view, then Edit, then form) suits many read-mostly fields or long forms. The cost is an extra step and an extra state to test.
- The idea settles "inline Save, the way `LearnerNamePanel` does for educators". That means always-editable fields with a Save in the panel. This is consistent with the evidence. Keep Save disabled only if there is a dirty-state signal. Otherwise leave it enabled, because a disabled button gives no reason why.
- Validation errors: return 422 (project convention), put the message next to the field, and use an error summary (`partials/error_summary`) that takes focus.

## 5. Save confirmation: toast vs inline vs live region

Findings:
- Confirmation placed beside the control the user just used is easiest to connect to the action. A Save button with a nearby `role="status"` / `aria-live="polite"` span is the standard recommendation.
- A toast must not be the only record of success: it can vanish before slower readers or screen-reader users have taken it in (W3C WAI-IG thread). Toasts are the visual counterpart of a live-region announcement, but not every toast is a good live region.

Fit with the house system: the panel framework already has an announcer host and an out-of-band toast from `partials/messages.html`. Its skill says a response carrying that toast gets no framework message, because the toast is the message. This answers the open question about "Profile saved":
- Pick one channel per action. Preferred: refresh the panel and have the announcer say "Name saved", with a short visible inline note in the panel. That gives a visible record and a screen-reader announcement.
- If the existing toast is kept, make sure it stays dismissible, is in a polite live region, and the panel also shows the new values.
- Do not show both a toast and an inline message for the same save.

## 6. Avatar: preview, replace and remove

- Show the current picture (or initials placeholder) at a size large enough to judge, with the file control next to it.
- Instant local preview before saving is standard (object URL via a small Alpine handler). It is optional here: the settled design uses a panel form with its own validation, so a preview is an addition only if the spec wants it. Without JS, the saved picture is the preview after the save.
- State the limits up front (accepted types, max size) next to the control, and show server validation errors in the panel (422).
- Replace is just a new upload. Do not ask for confirmation.
- Remove is destructive but cheap to redo (the user can upload again), so a confirm dialog is the safe, consistent choice: the panel framework's `ConfirmAction` already provides it ("Remove profile picture?", confirm label "Remove", destructive variant). Name what happens: the initials placeholder returns. Some sources prefer undo over confirm; the framework has no undo, so use the confirm.
- Show Remove only when a picture exists.
- Give the image meaningful alt text ("Your profile picture") or empty alt when a name is adjacent.
- Cropping is common in consumer apps (Filestack, shadcn blocks) but is feature creep here; the project rule is not to build what is not requested.

## 7. Logout placement in a settings area

- Sign-out should be easy to find (web.dev). Moving it into a settings subpanel drew user complaints on Discourse, and Firefox Accounts added a sign-out link to settings after users were confused.
- The header user menu is the primary home for it and already exists. Do not remove it there.
- Within the Account sidebar, a "Sign out" entry at the bottom, set apart from the section links and not styled as a section (it is an action, not a page), is a common optional secondary placement and matches the "destructive/exit items last" advice. Recommendation: include it only if the user menu is not visible on mobile in this shell. Otherwise leave it out, to avoid two ways of doing one thing. It must be a POST form or button, not a plain link, if allauth's logout needs a POST (check the allauth version in use).

## 8. Signposting private settings vs a public profile

I found no direct source on this. The reasoned approach, consistent with how GitHub, LinkedIn and similar products label things:
- Name the area by what it is: "Account" with "Personal details" is private. The future "Public profile" entry names what others see.
- On the Personal details page, a one-line note under the name panel such as "Only you and your educators see this" (adjust to what is true) tells the user the scope. Check what educators and admins can see before writing it.
- On the future public profile pages, mark them with a visible "Public" badge (`panel-status-badge`) and a link "View your public profile" opening in the same tab.
- Where a field feeds the public page (for example the profile picture, if shown publicly), say so beside it ("Shown on your public profile"). Decide this per field in the later spec, and leave a note in this spec's sidebar comment so the entry is added.
- Keep "Profile" out of labels in this spec, which the answers already do.

## 9. Summary of recommendations

| Question | Recommendation |
|---|---|
| Mobile sidebar | Link list above the content, no JS; revisit past ~6 entries |
| Active state | `aria-current="page"` plus a non-colour cue, driven by URL name so allauth pages work |
| Headings | One `<h1>` equal to the sidebar label; `<title>` includes "Account"; panels use `<h2>` |
| Name fields | Always editable, panel Save, 422 with field errors and summary |
| Save confirmation | One channel: panel refresh plus announcer, with a visible inline note; no double toast |
| Avatar | Current image, limits stated, replace without confirm, remove behind `ConfirmAction`, no cropping |
| Logout | Keep in header user menu; sidebar entry only if needed on mobile |
| Private vs public | Names ("Personal details" vs "Public profile"), a scope note, and a Public badge later |

## References

- https://makerkit.dev/docs/tanstack-supabase/customization/layout-style (sidebar converts to a drawer on mobile)
- https://www.saasui.design/blog/saas-sidebar-navigation-ux-patterns (drawer trigger visibility)
- https://handbook.once-ui.com/common-patterns/settings-and-split-panels (section picker on mobile)
- https://meta.discourse.org/t/on-mobile-the-preferences-page-dropdowns-can-be-a-little-confusing/112484 (stacked dropdowns confuse)
- https://community.shopify.dev/t/customer-account-navigation-issue-ui-inconsistency/33178 (drawer left open after navigation)
- https://setproduct.com/blog/settings-ui-design (settings UI design)
- https://dev.to/miasalazar/replacing-toasts-with-accessible-user-feedback-patterns-1p8l (inline feedback beside the control)
- https://skills.sh/matthewharwood/fantasy-phonics/ux-feedback-patterns (status span with aria-live)
- https://lists.w3.org/Archives/Public/w3c-wai-ig/2025AprJun/0083.html (toast as sole record disadvantages some users)
- https://lists.w3.org/Archives/Public/w3c-wai-ig/2025AprJun/0085.html (argument for toasts)
- https://cedar.rei.com/patterns/status (status notification pattern)
- https://www.saasui.design/blog/saas-file-upload-ux-patterns (upload and removal patterns)
- https://hexdocs.pm/phia_ui/PhiaUi.Components.AvatarUpload.md (avatar upload with preview)
- https://blog.filestack.com/profile-picture-upload-ui/ (preview, cropping)
- https://web.dev/articles/sign-out-best-practices (sign-out visibility)
- https://meta.discourse.org/t/a-click-too-many-logging-out/130615 (logout moved into settings, pushback)
- https://bugzilla.mozilla.org/show_bug.cgi?id=1195382 (sign-out link missing from settings)
- https://app.uxcel.com/courses/common-patterns/settings-best-practices-572/destructive-items-5494 (destructive items last)
- Repo: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` (announcer, toast, ConfirmAction, partials), `.claude/skills/brand-guidelines/SKILL.md` (voice and visual branches; `visual.md` and `voice.md` not read in this pass)

status: ok
