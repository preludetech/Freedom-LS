# Every signed-in user edits their account on panels

Spec 3 of 3 in the Account area on panels effort. Read the "Account area on panels" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The account page (`accounts:account_profile`) becomes a panel framework page in its own
account area, for every signed-in user: learners, educators and admins. It holds a name panel
and a profile picture panel. The account area has its own shell and sidebar, and allauth's email
and password pages sit in the same shell and sidebar, so a user moves between them without
changing layout.

## Why

Learners are about to get a public profile, work experience, completed courses and certificates
to manage (the "Learner public profiles" effort). On today's plain page, each of those would be a
new hand-built form, and the page would grow without a design to hold it. The panel framework
already settles how a page of panels, edit forms and dialogs looks and behaves. Putting the
account area on it now lets `learner-public-profile-2-profile-and-page` and the specs after it
add panels instead of pages.

## What is settled

- The profile picture upload already ships on today's plain account page, in its own form with its
  own Save (the owner chose to finish it there). This spec moves it onto a panel, using
  `learner-profile-use-panels-framework-1-file-upload-actions`, and keeps its validation, storage
  and removal behaviour.
- The page is the instance view of one object, the signed-in user (`ObjectViewConfig`). Only
  the user themselves can see or edit it. Any other request returns 404, and anonymous users go to
  login. This is tested in `accounts`, because the educator invariants walk only educator
  sections.
- The name panel edits first and last name with an inline Save, the way `LearnerNamePanel` does
  for educators. It replaces `edit_profile`'s plain form. Validation errors return 422.
- The URL name `accounts:account_profile` and its path keep working: the header user menu, the
  educator interface's account settings link, `EXEMPT_URL_NAMES` in `accounts/middleware.py` and
  existing tests all reverse it.
- The shell extends the general interface base (`_base_interface.html`), not the educator
  interface's `_shell.html`, because learners have no educator sidebar. It carries the panel
  framework's hosts (dialog, quick view, announcer) and follows the host contract
  `extract_panels_framework-4-template-contract` documents. If that spec has not landed, the
  shell follows the contract in `extract_panels_framework/research_coupling_audit.md` and is
  reconciled when it lands.
- The sidebar lists Profile, Email and Password, and has room for the public-profile sections
  later specs add.
- Email and password pages keep allauth's views, forms, URLs, rate limits, reauthentication and
  emails. Only their layout changes: the project's `allauth/layouts/manage.html` override puts
  them in the account area's shell. They are not rebuilt as panels.
- `complete_registration`, `legal_doc`, login, signup, password reset and email confirmation
  keep their current layout. They run before a user is fully set up.
- Self-edits here write no audit log entries: the audit log is organisation-scoped and a user's
  own account has no organisation.
- The code follows the `panels/<area>/` layout the "Educator interface code layout" effort uses,
  inside `accounts`.
- Tests for today's `edit_profile` behaviour are written first, since it has none, so the move
  is checked against them.
- The panel framework stays generic: nothing about accounts goes into it.

## Open until the spec

- The sidebar's labels and the page title, checked against `fls-dev:domain-glossary` and
  `brand-guidelines`. "Profile" is taken by the account page and must stay distinct from the
  coming "public profile".
- How the "Profile saved" message becomes the panel's own confirmation (announcer or refreshed
  panel).
- How a downstream project's theme override of `accounts/profile.html` or
  `allauth/layouts/manage.html` is flagged in the upgrade notes.
- Whether the page uses one panel stack or tabs, given the sections later specs add.

## Out of scope

- Public profile, work experience, completed courses and certificates panels: the
  `learner-public-profile-*` specs add them.
- MFA, sessions and social-account pages, which are not enabled.
- Any change to the educator interface's own pages.

## Resources

- `research_current_account_pages.md` in this directory (every account page today, its view,
  template, links and tests)
- `spec_dd/1. next/learner-profile-use-panels-framework/research_panel_framework_fit.md` (what a
  host must supply, the shell, authorisation)
- `spec_dd/1. next/extract_panels_framework/research_coupling_audit.md` T11 and J3 (host contract)
- Skills: `fls-dev:panel-framework`, `fls-dev:template`, `fls-dev:multi-tenant`,
  `fls-dev:domain-glossary`, `brand-guidelines`, `fls-dev:testing`
