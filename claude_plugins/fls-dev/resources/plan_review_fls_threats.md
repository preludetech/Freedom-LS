# Plan review brief: FreedomLS threats

Inputs from the caller: `<plan-path>`, `<spec-path>`, `<output-path>`.

Read the plan and the spec. Check only what the plan adds or changes, one narrow check per
trigger. Read the skill file each trigger names before judging it.

- A new model extends `SiteAwareModel` (or `SiteAwareModelBase` with a custom primary key) or the
  plan says why not, and never sets `site_id` by hand
  (`claude_plugins/fls-dev/skills/multi-tenant/SKILL.md`).
- A query or view that bypasses the manager's automatic site filtering states why (the same file).
- A new `FileField` or `ImageField` names its storage alias and keeps learner-identifying or
  user-supplied files out of the `public` and `course_media` aliases
  (`claude_plugins/fls-dev/skills/file-storage/SKILL.md`).
- A registration form obeys the field and `?next=` rules in
  `claude_plugins/fls-dev/skills/registration/SKILL.md`: no field named `user`, `user_id` or
  `email`, and a `?next=` redirect checked with `url_has_allowed_host_and_scheme`.
- A consent read or write keeps `LegalConsent` append-only: no update of an existing row, and no
  write on behalf of a user id from the request (the same file).
- An HTMX validation failure returns 422 and relies on the global CSRF header rather than adding
  a token to the request (`claude_plugins/django-stack/skills/htmx/SKILL.md`).
- An educator-side view resolves access through
  `learner_management.queries.organisations_accessible_to`, the mechanism
  `claude_plugins/fls-dev/skills/testing/SKILL.md` documents for every `educator_interface`
  view, not through a staff or group check.

Write `<output-path>` in a single `Write`. Its first line is `callout: Security concern`. Then
one line per hit, `<plan step>: <trigger>: judgement call: <options, recommended first>`, then
the `status:` footer. No hits is `status: ok` with `no FLS threats`.
