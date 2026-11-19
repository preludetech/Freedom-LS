# Reference implementations: account settings areas

Topic: how real products and projects structure a signed-in user's account area, and what that
means for the FLS Account area (sidebar of Personal details / Email / Password, later Public profile;
name and picture panels edit inline; allauth email and password pages wrapped in the same layout).

Items marked (unverified) come from general knowledge, not a fetched page.

## 1. django-allauth's layout contract (the part that binds us)

- Three layout templates exist: `allauth/layouts/base.html`, `entrance.html` (login, signup and
  other pre-auth pages) and `manage.html` (email, password and other account management pages).
  `entrance.html` and `manage.html` both extend `base.html`. Overriding means placing a copy in a
  project template directory that comes before app directories (`DIRS`). [1][2]
- `manage.html` itself is trivial: `{% extends "allauth/layouts/base.html" %}` plus an empty
  `{% block content %}{% endblock %}`. Every manage page (email, password change/set, and the
  disabled MFA, sessions and socialaccount pages) fills `content` and nothing else. [3]
- `base.html` defines `head_title`, `extra_head`, `body` (containing messages, the menu and
  `content`) and `extra_body`. The built-in menu links render only when the URL name resolves, so
  a project that does not enable MFA, sessions or social accounts shows no dead links. [4]
- Consequence for FLS: the override of `manage.html` can extend the account shell and map
  allauth's `content` block onto the shell's content block, and it must keep supplying the blocks
  the manage pages use. Allauth's own page templates stay untouched. Our override should not
  extend `allauth/layouts/base.html` (it would pull in allauth's own menu and messages). The page
  `head_title` block should still be mapped to our title block. The block set is stable and small,
  but is read from the installed version's `base.html`, which is what the upgrade notes should name.
- Allauth pages render their content through `{% element %}` tags (`allauth/elements/*.html`:
  h1, form, button, fields...). Restyling the forms to the project's look goes through element
  overrides, separately from the layout. Inside an element template `{{ origin }}` names the page
  (for example `account/login`). Slots (`{% slot body %}`, `actions`) are injected in any order. [1]
- Allauth's repository ships only two examples, `react-spa` and `regular-django`, both with plain
  Bootstrap-style templates and no sidebar layout. There is no official sidebar example. [5]
- Third-party wrappers: `django-allauth-ui` (Tailwind) re-skins login, signup and reset only, and
  its README does not describe a manage-page sidebar. [6] AdminLTE's Django package overrides all
  three layouts and the elements, which makes it a working example of a sidebar `manage.html`
  (not fetched in detail). [7] A search found no widely used project documenting "sidebar around
  allauth manage pages", so the FLS approach (one override of `manage.html` that extends the
  account shell) is the generic documented route rather than a copied pattern.

## 2. Product comparisons

| Product | Private vs public split | Sidebar labels | Pages or tabs | Save confirmation | Avatar |
|---|---|---|---|---|---|
| GitHub | One Settings area; "Public profile" is the first item, with Account, Appearance, Accessibility, Emails, Password and authentication, etc. as separate pages | Public profile, Account, Appearance, Accessibility, Notifications, Access: Emails, Password and authentication, Sessions... (labels partly unverified) | Separate pages in a left sidebar | Per-form button with a specific verb: "Update profile", "Update username", "Save changes", "Set status"; page reloads with a flash banner | Profile Picture "Edit" menu: Upload a photo, crop, "Set new profile picture"; "Remove photo" returns to the identicon (or "Revert to Gravatar") [8] |
| GitLab | User settings left sidebar: Profile ("Edit profile"), Account, Emails, Password, Access tokens, Preferences, etc. | Profile, Account, Billing, Applications, Chat, Access (Emails, Password...) , Preferences | Separate pages | Buttons: "Update profile settings", "Update username"; flash notice; dangerous edits need confirming (remove secondary email asks to confirm) [9] | Reached from Edit profile; page does not document remove, and the fetched doc says nothing on it |
| Discourse | One Preferences area, tabs across the top: Account, Security, Profile, Emails, Notifications, Tracking, Categories, Users, Interface, Apps | Account holds username, email, profile picture; Profile holds location, website, header image; Security holds 2FA | Tabs under one "Preferences" page, each tab its own URL (`/my/preferences/account`) | One explicit "Save Changes" button per tab; unsaved changes are not applied [10] | Click the picture frame to upload; trash can icon to remove [10] |
| Moodle | "Profile" page (public) vs "Preferences" (private: account, language, forum, notifications). Edit profile is one long form | General, User picture, Additional names, Optional, Interests (collapsible sections within one form); Preferences has User account / Roles / Preferences groups | Preferences: pages. Edit profile: one form with collapsible sections | A single "Update profile" at the bottom; redirects to the profile page [11] | File picker "Upload a file", cropped to a square and resized on save; doc does not describe deleting (Moodle has a "Delete" tick in the picker, unverified) [11] |
| Open edX | Account Settings (private) and a separate Profile page (public) with its own visibility setting. Account Settings has tabs "Account Information", "Order History"; profile photo is on the public Profile page (unverified) | Account Settings fields edit one at a time | Tabs | Inline: each field shows an "Edit" link, opens an input with Save and Cancel; a "Saved" banner appears on success (unverified) | Photo changed on the Profile page, not on Account Settings (unverified) |
| Canvas | "Settings" (private: email addresses, password, ways to contact) and "Profile" (the user's profile page) are separate links in the account menu. The Canvas guide page was not reachable | Account menu: Profile, Settings, Notifications, Files, ePortfolios, Settings | Separate pages | Page button "Update Settings"; avatar uses a click-the-picture dialog with upload and remove (unverified) | Click the photo, upload and crop (unverified) |

## 3. Patterns that matter for FLS

1. Private account and public profile are split in every product that has both (GitHub keeps them
   in one Settings area as separate sidebar entries; Moodle, Canvas and Open edX use separate
   pages or even separate sidebars). FLS's choice of one Account area with room for later public
   profile sections matches GitHub: a sidebar group for the private account (Personal details,
   Email, Password) and a later sidebar group for the public profile. GitHub also names the
   public item "Public profile" and the private one "Account", which keeps both words distinct.
   The idea notes "Profile" is taken, so the labels in this spec must keep "Public profile" for
   the coming feature, and name the current page something else ("Personal details" fits).
2. Sidebar entries are separate pages (GitHub, GitLab, Canvas) far more often than tabs. Tabs
   appear in Discourse (still one URL per tab) and Open edX. Because the allauth pages are
   separate server-rendered URLs that cannot become panels, separate pages with a sidebar is the
   natural structure. Each sidebar entry is a link, not a client-side tab. A "one page with panel
   stack" fits a single section (Personal details holds the name panel and picture panel),
   while later public-profile sections can either be panels on a second page or their own page.
3. Save confirmation: most products use an explicit verb button plus a flash banner after a
   reload. Open edX is the closest to inline-edit panels: edit one field, Save or Cancel, then an
   in-place "saved" message. For FLS panels, the equivalent is the panel returning to read state
   with an announcer message ("Name saved"), rather than a full-page flash. Specific button verbs
   ("Update profile", "Set new profile picture") read better than a generic "Save"; consider
   "Save name" (inline Save per the idea) and an upload button labelled for the picture.
4. Avatar: the common flow is click the picture or an Edit control, choose a file, (often crop),
   confirm with a specific verb, and a separate "Remove" action that falls back to initials or an
   identicon (GitHub, Discourse trash can). Removal is a one-click action beside upload, not a
   form field. GitHub and Moodle both keep avatar changes off the main "Update profile" button;
   Moodle ties them together. FLS's picture panel with its own upload and remove actions matches
   the GitHub and Discourse approach and keeps today's validation and storage behaviour.
5. Email and password stay on their own pages in GitHub and GitLab ("Emails", "Password and
   authentication"), under a security or access grouping, which fits wrapping allauth's views
   without turning them into panels. Both products also show the same page chrome on them as on
   native pages, which is what the shared `manage.html` override achieves.
6. Dangerous or reauthenticated actions (GitLab's remove-email confirmation, allauth's
   reauthentication) are confirmed on their own, outside the main save button. This matches
   leaving allauth's flows as they are.

## 4. Suggestions for the spec

- Sidebar labels: "Personal details", "Email", "Password" for now; reserve a later group
  "Public profile" (GitHub's wording) and check "Personal details" against the glossary.
- One URL per sidebar item, with the account shell rendering the sidebar and marking the active
  item; the `manage.html` override extends the same shell. No tabs.
- Mark the active sidebar entry from the request's URL name, which works for allauth pages without
  touching them.
- Confirmation through the announcer plus returning the panel to its read state, as Open edX does
  inline; keep the full-page message for allauth pages, since allauth's views use Django messages
  and the shell should show messages for them.
- Picture panel: upload with a specific verb, remove as a separate action, fallback to initials.
- Upgrade note: a downstream override of `allauth/layouts/manage.html` or `accounts/profile.html`
  must be reconciled with the new shell; name the blocks `head_title`, `content` and any shell
  block the override fills.

## References

1. django-allauth template docs: https://docs.allauth.org/en/latest/common/templates.html
2. Same docs, mirror with sample `manage.html`: https://django-allauth.readthedocs.io/en/latest/common/templates.html
3. `manage.html` source: https://raw.githubusercontent.com/pennersr/django-allauth/main/allauth/templates/allauth/layouts/manage.html
4. `base.html` source: https://raw.githubusercontent.com/pennersr/django-allauth/main/allauth/templates/allauth/layouts/base.html
5. allauth examples directory: https://github.com/pennersr/django-allauth/tree/main/examples
6. django-allauth-ui: https://github.com/hevans714/django-allauth-ui
7. AdminLTE Django allauth overrides: https://django.adminlte.io/docs/auth/
8. GitHub, personalizing your profile: https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/customizing-your-profile/personalizing-your-profile
9. GitLab user profile docs: https://docs.gitlab.com/user/profile/
10. Discourse, managing and understanding user preferences: https://meta.discourse.org/t/managing-understanding-user-preferences/327479
11. Moodle, edit profile: https://docs.moodle.org/en/Edit_profile
12. GitHub, managing user account settings: https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-user-account-settings

status: ok
