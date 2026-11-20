# Research: known complaints about account and profile settings pages

Scope: what users and developers complain about on account/profile settings pages, so the
account area (Profile, Email, Password, later Public profile) avoids them. Evidence is uneven.
Each item is marked **Sourced** (a cited page says it) or **Unsourced** (common design
knowledge I did not find a citation for in this pass, so treat it as a hypothesis to check).
Searches for Canvas, Open edX, Google Classroom and accessibility complaints were not run in
this pass.

## 1. Avatar and profile picture upload

- **Sourced: HEIC from iPhones is rejected.** Apple's default photo format is HEIC, which
  most browsers and many server image pipelines cannot read. Reports: Liferay profile image
  error, Cloudron "Photo type not supported", iNaturalist forum, WordPress core trac (support
  depends on Imagick). A support page's workaround is telling the user to switch the camera
  to "Most Compatible". Client-side conversion (heic2any) costs about 2.7 MB of JS.
  Lesson: either convert server-side or say plainly which formats are accepted and give a
  readable error, not a generic failure.
- **Sourced: limits and failure causes are not stated up front.** Help desks answer "why did
  my upload fail" with size, dimensions and file type, which means the form did not say so
  beforehand. One university guide says JPG/PNG work best and updates can take up to 24 hours
  to show.
- **Sourced: phone photos appear sideways** (EXIF orientation not applied). Users are told
  to re-save in an editor. Lesson: apply EXIF orientation on upload.
- **Sourced: quality loss.** Moodle MDL-76616: 4.x smooths uploaded images so avatars look
  blurry, with no setting to turn it off. Moodle MDL-59158: the default avatar overflows its
  layout. Lesson: render the avatar at a defined size, and test the empty-state avatar in
  every place it appears.
- **Unsourced: no cropping or preview.** Users expect to see how the picture will be framed
  before saving. Moodle's older docs say images are reduced to 100px and 35px copies, which
  hints at the same expectation.
- **Unsourced: removal is hard to find, or the picture is cached after removal.**

## 2. Not knowing whether a change saved, and lost edits

- **Sourced: forgotten saves.** A WPMUDEV feature request: users forget to press Save on a
  settings page and find later that nothing was stored.
- **Sourced: over-prompting is also a complaint.** Qualtrics and Octopus users report a
  "discard changes" dialog when nothing changed, or one that appears only some of the time.
  Cloudscape's guidance: only warn when data would really be lost, and not when everything is
  already saved.
- **Sourced: unclear dialog wording** (Redmine UX issue on a profile edit exit dialog).
- **Sourced: dirty-flag pattern.** Attach the navigation guard only while the form is dirty
  (Shopify community thread).
- Implication for this spec: the open question on how "Profile saved" becomes the panel's
  confirmation matters. A confirmation that is visible to a screen reader (announcer) and
  to a sighted user (the refreshed panel) avoids "did it save". Several panels on one page
  (name and picture each have their own Save) raise the lost-edit risk: a user edits the
  name, then uploads a picture, and the unsaved name is lost. **Unsourced** as an LMS
  complaint, but follows from the sourced pattern above.

## 3. Email change and verification

- **Sourced (single blog, treat with caution): the verification deadlock.** A user with an
  unverified primary email cannot log in, so cannot reach the settings page to fix a typo.
- **Sourced (allauth docs): the two email models confuse.** The multi-address page (add,
  verify, remove, make primary as separate steps) and the single-address
  `ACCOUNT_CHANGE_EMAIL` flow (a temporary second address replaces the current one once
  verified) behave differently. "Verified" and "primary" are separate states, and the page
  shows both without explaining them.
- **Unsourced:** users do not know whether the old address still works until the new one is
  confirmed; confirmation emails go to spam; no "resend" feedback.
- Implication: the page keeps allauth's views, so the spec cannot change the model, but it
  can add one line of help text near the email list in the restyled shell if the project
  decides to. Check which `ACCOUNT_CHANGE_EMAIL` setting the project uses.

## 4. Password change friction and reauthentication

- **Sourced (secondary tutorial):** allauth offers `ACCOUNT_REAUTHENTICATION_REQUIRED` and
  `ACCOUNT_REAUTHENTICATION_TIMEOUT`. Reauthentication interrupts a user mid-task with a
  page that looks unlike the rest of the area.
- **Unsourced:** users with a social-only or code-login account are confused by "current
  password" fields (allauth shows set-password instead); unclear password rules until after
  failure; no confirmation of success beyond a redirect.
- Implication: the reauthentication page is an allauth page, so it must also sit in the
  same shell, or the user thinks they were logged out. Check that the restyled
  `manage.html` covers it (allauth's reauthentication templates may use a different layout;
  verify against the installed version).

## 5. Account versus public profile confusion

- **Unsourced in this pass** (no LMS-specific citation found). The risk is structural:
  the idea notes "Profile" is taken by the account page and must stay distinct from the
  coming "public profile". Typical failure: users edit their name here expecting it to
  change what others see, or expect a private page to be visible. Mitigation: label the
  sidebar so private and public are obviously different, and say on the name panel who sees
  the name.

## 6. Settings scattered across pages, and mobile navigation

- **Unsourced in this pass.** The spec's own premise (allauth pages in the same shell as the
  account page) targets the scattered-settings complaint. For mobile, a sidebar with three
  items needs a collapsed form (a select or a top tab row) rather than a hidden drawer;
  verify what the panel framework shell does at narrow widths.

## 7. Accessibility

- **Unsourced in this pass.** Known risks for this design that can be checked against
  tests: save confirmation not announced (relevant to the announcer host), focus lost after
  an HTMX swap or a 422 response, errors not tied to fields, avatar upload control not
  keyboard operable, avatar images without alt text, current sidebar item not marked with
  `aria-current`.

## 8. django-allauth specific

- **Sourced: stale copied templates.** A django-mailman3 GitLab issue: a project that copied
  allauth templates missed a page added by a later allauth release, which then rendered
  unstyled. Relevant to the open question on flagging a downstream override of
  `allauth/layouts/manage.html` in the upgrade notes. Overriding only the layout (as the
  idea does) limits this, but a new allauth page that extends a different layout would still
  escape the shell.
- **Sourced (docs):** `allauth/layouts/manage.html` is the supported override point for
  the manage pages, and allauth documents that you can provide your own copy.
- **Not found:** no GitHub issues or forum threads specifically complaining about the manage
  pages' usability surfaced. The searches were broad web searches, not a read of the
  issue tracker.

## Takeaways for the spec

1. State accepted picture formats and the size limit next to the control, and make the
   error message name the actual problem. Decide about HEIC explicitly (accept and convert,
   or reject with a clear message).
2. Apply EXIF orientation; define avatar render size, including the empty state.
3. Give each panel one clear saved confirmation that is also announced; avoid
   over-prompting about unsaved changes.
4. Make sure every allauth page in the flow, including reauthentication, uses the account
   shell.
5. Make the account/public distinction visible in sidebar labels.
6. Record in the upgrade notes that a stale copy of `manage.html` or a new allauth layout
   escapes the shell.

## References

- Cloudscape unsaved-changes pattern: https://cloudscape.design/patterns/general/unsaved-changes/
- Qualtrics "discard changes" with no change: https://community.qualtrics.com/survey-platform-54/discard-changes-pop-up-when-no-change-made-to-settings-28085
- Octopus erratic unsaved dialog: https://help.octopus.com/t/change-tracking-on-the-project-settings-page-is-erratic/5342
- WPMUDEV forgotten settings save: https://wpmudev.com/?p=4032386
- Redmine profile exit dialog: https://redmine.gc.cuny.edu/issues/4895?tab=notes
- Shopify dirty-state navigation guard: https://community.shopify.com/t/prevent-navigation-when-savebar-is-active/398108
- HEIC article (heic2any cost): https://dev.to/upsidelab/rendering-heic-on-the-web-how-to-make-your-web-app-handle-iphone-photos-pj1
- Liferay HEIC profile image: https://learn.liferay.com/l/33729101
- Cloudron HEIC unsupported: https://forum.cloudron.io/topic/4439/heic-photos-unsupported/
- iNaturalist HEIC: https://forum.inaturalist.org/t/heic-files-not-being-permitted/68333
- WordPress HEIC ticket: https://core.trac.wordpress.org/ticket/64915
- V1CE upload troubleshooting: https://support.v1ce.co/troubleshooting/i-can-t-upload-my-profile-photo-or-logo-to-my-v1ce-page
- Moodle MDL-76616 (blurry uploads): https://tracker-old.moodle.org/browse/MDL-76616
- Moodle MDL-59158 (avatar overflow): https://tracker-old.moodle.org/browse/MDL-59158
- University help desk, profile picture guidance: https://servicedesk.louisiana.edu/node/1565
- Moodle user pictures docs: https://docs.moodle.org/en/User_pictures
- allauth verification deadlock blog: https://www.technetexperts.com/django-allauth-email-typo-fix/
- allauth views docs: https://django-allauth.readthedocs.io/en/latest/account/views.html
- allauth templates docs: https://docs.allauth.org/en/dev/common/templates.html
- allauth account management concepts (secondary): https://www.mintlify.com/pennersr/django-allauth/concepts/account-management
- django-mailman3 stale allauth templates: https://gitlab.com/mailman/django-mailman3/-/issues/84

status: ok
