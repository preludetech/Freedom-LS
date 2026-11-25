---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - FORM_DECLARATION_DEFAULT_TEXT  # optional: has a default
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: sacaa-complianc-deletion-and-declaration-2-quiz-declaration

A quiz can now require learners to sign a declaration before each attempt. Authors turn it on with
`requires_declaration: true` in the quiz's `form.md` front matter, and can set their own wording
with `declaration_text`. Each signature is stored as a `FormDeclaration` record (the text shown,
the typed full name, the time and the learner's IP address), and staff see it on the form progress
record in the Django admin. Quizzes without the key behave as before.

## Breaking changes

None.

## Manual steps

- Run `manage.py migrate`. Migration
  `freedom_ls/form_engine/migrations/0017_form_declaration_text_form_requires_declaration_and_more.py`
  adds `Form.requires_declaration`, `Form.declaration_text` and the `FormDeclaration` table.
- Rebuild Tailwind. The new learner page template
  `freedom_ls/learner_interface/templates/learner_interface/form_declaration.html` uses utility
  classes your CSS bundle must include.
- Optional: set `FORM_DECLARATION_DEFAULT_TEXT` in your settings to change the wording shown for a
  declaration quiz whose `form.md` leaves `declaration_text` empty. The FLS default lives in
  `freedom_ls/form_engine/config.py`. No system check enforces it.
- If your privacy policy lists the places your site records a person's IP address, add quiz
  declarations to that list.
- If your project overrides the learner quiz views or the `learner_interface` URLconf, note the new
  URL `courses/<course_slug>/<index>/declaration` (name `learner_interface:form_declaration`):
  starting a declaration quiz, or opening a page of an unsigned sitting, now redirects there.
