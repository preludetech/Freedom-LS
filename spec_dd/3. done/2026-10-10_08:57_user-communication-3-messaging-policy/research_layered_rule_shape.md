# Research: how a layered messaging rule is expressed

Question from the idea: should each level (site, organisation, cohort or course registration,
learner) carry individual flags with an unset/open/closed value, or name one of a small set of
named policies? This builds on `research_flexible_configurable_comms.md`, which covers settings
versus database configuration and the dotted-path backend. That is not repeated here.

## 1. Prior art

### Moodle capability overrides (inherit / allow / prevent / prohibit)

- Four values per capability per context. Inherit is the default. Allow and Prevent set a value
  that a lower context may override. Prohibit is a Prevent that no lower context or other role can
  override. If two roles in one context disagree, Allow beats Prevent, but Prohibit beats everything.
- Why Prohibit exists: a higher-level admin needs a way to say "never, whatever is configured
  below". Without it, the "most specific wins" rule lets a lower-level admin undo a higher-level
  safeguard.
- What worked: inherit as the explicit stored default means "unset" is a first-class, visible
  value.
- What hurts: four values plus multi-role conflict plus context depth make "why can this user do X"
  hard to answer. Moodle ships a separate Check permissions page for that. This is the strongest
  evidence that an "explain" path is needed once there is layering.
- Relevance to FLS: the idea has most-specific-wins with no lock. That is fine now, but the stored
  value should be a choice field, not a boolean, so a later "closed and locked" (Prohibit-like) value
  can be added without a migration or a rework. Stricter safeguarding modes are out of scope, and
  this is the seam they will want.

### Moodle messaging

- A site setting (`messagingallusers`) controls whether users can message anyone on the site. Each
  user also chooses who may message them: "my contacts and anyone in my courses" (the default) or
  "my contacts only".
- The capability `moodle/site:messageanyuser` lets manager and teacher roles bypass the recipient's
  privacy preference.
- What worked: staff-to-learner bypasses the recipient preference. This matches the FLS default
  that educators may start a conversation with any learner they can see.
- What admins and users complain about: the Message button silently missing on a profile. The
  cause is the recipient's preference, which the sender cannot see.
- Relevance to FLS: a sender-side and a recipient-side rule both apply to a pair, which is the
  idea's open question "whose context decides a pair". A per-recipient preference is the same shape
  as a learner-level flag.

### Canvas

- Account to sub-account to course. Most settings are a default that a lower level may change. A
  lock on a setting or feature option stops sub-accounts and courses from changing it. If it is
  unlocked, the parent value is only a default.
- Canvas messaging is a role permission. Revoking student "send messages to course members"
  leaves students able to reply but not to start. This is the same start-versus-reply split the
  idea has.
- Admins have asked for account-setting inheritance to behave like feature options and permissions,
  because the levels behave inconsistently. Locking in a sub-account has also caused known issues.
  The lesson is to use one inheritance model for every flag, not different rules per flag.

### Discourse

- `personal_message_enabled_groups` names the groups allowed to start a personal message.
  Admins and moderators can always message. Anyone can reply to a message someone else started.
- The setting is documented as confusingly titled. Admins read it as "who can use messages" but it
  means "who can start one". Staff proposed clearer wording and a separate
  `disallow_personal_message_groups` setting.
- Lesson: name flags by the action ("may start a conversation with") and never by the feature. An
  allow-list with no deny-list could not express "everyone except these", so people asked for a
  second setting. Tri-state per flag gives both from the start.

### Microsoft Teams policies

- A named policy package is assigned directly to a user or to a group. Direct assignment beats
  group assignment (by group rank), which beats the org-wide global policy. Each user has exactly
  one effective policy per policy type.
- What worked: presets are easy for admins to reason about and to audit, because a user has one
  named policy.
- What hurts: precedence between group assignments needs a rank number. Admins have to ask the
  platform which policy is effective, and changes take time to apply. A preset is all or nothing:
  to change one switch, the admin makes a new custom policy. This is the preset approach's cost in
  the FLS case, where one learner needs one extra permission.
- Slack has a similar org-level "who can DM / which channels" model. Policy there is mostly
  per-workspace on/off rather than layered, so it is weak prior art for layering.

### Summary

| System | Value model | Precedence | Debug aid |
|---|---|---|---|
| Moodle capabilities | inherit/allow/prevent/prohibit per capability | context depth, prohibit absolute | Check permissions page |
| Canvas settings | value + lock per setting | account to sub-account to course | none for locks; admins ask for parity |
| Discourse PM | group allow-list per action | staff always allowed | none |
| Teams policies | named package | user, then group rank, then global | PowerShell for effective policy |

Common finding: per-flag values compose and are explainable per flag. Presets are easy to read
but do not compose across layers. Every system that layers needs a way to say why. The one real
difference between the systems is whether a higher level can lock a value.

## 2. Django modelling options

Existing FLS precedent:

- `SiteSignupPolicy` (`freedom_ls/accounts/models.py`) is a `SiteAwareModel` with one row per site
  (`UniqueConstraint(fields=["site"])`). It uses plain `BooleanField(default=...)`, with no
  tri-state, and the settings value is the fallback only for `allow_signups` when no row exists.
  That works because it has one layer. The idea's site row must be different in one respect: every
  flag must be nullable, otherwise a row cannot "leave a value unset" and fall through to the
  settings default.
- `AppSettings` (`freedom_ls/base/app_settings.py`) treats `None` and `""` as unset and returns
  the declared default. A `False` value is kept. So a settings default of `False` for a flag
  reads correctly. A dict-valued setting would be deep-copied, which is safe. The settings layer
  can therefore be a declared setting such as a dict of flag name to bool. It can also be a
  dotted-path preset name if that is wanted.
- The done notifications spec keeps its categories in code (a registry of `NotificationCategory`
  values from a setting) and stores no per-level configuration. There is no tri-state or layered
  precedent in FLS yet. The nearest existing code is `SiteSignupPolicy`.
- `SiteAwareModelAdmin` just sets `exclude = ["site"]`. Messaging admins inherit that.

### Option A: nullable flags as columns (`BooleanField(null=True)`)

- One column per flag, `None` means inherit.
- Admin: Django renders `BooleanField(null=True)` as a select with "Unknown / Yes / No". "Unknown"
  is a poor label for "inherit", and a bare list column shows an icon for None. Fixing it needs a
  custom form field or widget, or `choices`.
- Variant: a `CharField` or `IntegerField` with `TextChoices` `inherit / open / closed` gives
  correct labels in the form, `list_filter` and `list_display`, and can gain a fourth value later
  (locked closed) with no schema change. Worth the small cost over a nullable boolean.
- Adding a flag is a migration. With four flags and a closed list, that is acceptable.
- Typing and resolution are plain: `getattr(row, flag)`.

### Option B: one row per set value (flag name + value), absence means inherit

- `(scope, flag, value)` with `UniqueConstraint(scope..., flag)`. Only values that are set exist.
- Admin: an inline on the scope with the flag as a choice. It shows only what is set, which is
  closest to "most specific level that sets a value wins". "Unset" needs no label.
- Adding a flag needs no migration, but a typo or stale flag name can sit in the table, so it
  needs a validator against the flag list.
- More joins at resolution (one query per level, or one query filtered by all scopes). Admin
  editing is clumsier for an admin who wants to see all four flags at once, and a constraint
  that exactly one scope is set is still needed.

### Option C: JSON field of flags

- One `JSONField(default=dict)`. Keys present means set. Flexible, no migrations, but no
  admin widget beyond a text box, no per-flag labels or filters, and validation has to be hand
  written. `SiteSignupPolicy` already uses a JSONField for `additional_registration_forms`, but
  that is a list of references, not switches. This is the weakest option for the Django admin,
  where the site admin is the only editor.

### Option D: named policy per level (`CharField(choices=...)` or a `policy` FK)

- Each level has `policy = "closed" | "learner_to_educator" | "cohort_peers" | ...` or blank to
  inherit. Teams-style.
- Admin: one dropdown per row. Very simple to read and to filter on.
- Composition is the problem. A level sets one name, so the learner level naming
  `learner_to_educator` would also need to say what it does about peers. Either the preset
  replaces everything beneath it (the learner loses the site's peer opening), or presets must be
  additive, in which case they are really bundles of flags.
- To avoid that, the number of presets grows by combination. With four flags and two effective
  values each, there are 16 combinations, and more once locking is included.

### Where the scope lives (all options)

- One table per scope (`SiteMessagingConfig`, `OrganisationMessagingConfig`,
  `CohortMessagingConfig`, `CourseRegistrationMessagingConfig` for each registration type,
  `LearnerMessagingConfig`): plain foreign keys, referential integrity, and a natural admin inline on
  `Organisation`, `Cohort`, `Learner`. It means repeated field lists, because the repo says not
  to add abstract bases unless asked. The repetition can be kept small by generating the fields
  from the single flag list, or by accepting the repetition.
- One table with nullable foreign keys to each scope model plus a check constraint that exactly
  one is set: one place for the fields and the resolver, but the `comms` base app would import
  cohort and registration models, which the idea forbids. A generic foreign key (content type and
  object id) avoids the import and also avoids integrity, but is awkward in the admin (a free
  object id) and cannot be queried with joins. The idea says the base `comms` app imports no cohort
  model. The generic foreign key fits that, but it gives up integrity and joins.
- Middle path: the site and learner rows live in `comms` (site and learner are always present).
  Organisation, cohort and registration rows are the ones that need the cohort models, so they sit in
  the policy implementation's app or use the generic scope. This matches the idea's rule that
  cohort-aware logic sits in the policy implementation.

### Is an "explain why" display worth having?

Yes, but as a function first and a screen second. Prior art says the pain is debugging
(Moodle's Check permissions, Teams effective-policy queries, Moodle's missing Message button).

- Build the resolver to return the value and its source: `Resolution(value, source)` where the
  source is the level and row, or the settings default. The policy needs the value only. The
  source is free to keep, and a test or a management command can print it.
- An admin "why can A message B" screen is a new feature the idea does not ask for, and the
  project rule is not to build unrequested functionality. Recommend deferring the screen but
  returning the source from day one so adding it later is trivial.
- A cheap, in-scope admin aid is a read-only column or field on each level's admin showing the
  effective value one level up. This is optional.

## 3. The finite list of flags this spec needs

From the idea:

| Flag | Meaning | Default |
|---|---|---|
| `learner_may_start_with_educator` | a learner may start a conversation with one of their educators | closed |
| `peers_in_cohort_may_start` | a learner may start a conversation with a peer who shares a cohort | closed |
| `peers_in_course_may_start` | a learner may start a conversation with a peer who shares a course | closed |
| `educator_may_start_with_learner` | an educator may start a conversation with a learner visible to them | open |

Notes:

- Reply is not a flag. The idea says the learner may reply to an educator's conversation, and
  Discourse and Canvas treat reply separately from start. Whether a closed rule blocks replies in
  an existing conversation is a separate open question in the idea, so keep reply out of the
  flags and decide it in the spec.
- Whether to make `educator_may_start_with_learner` a flag at all: it is open by default, but
  the idea says a level "can open messaging or close it again". A site serving a learner who
  asked not to be contacted needs to close it per learner. Including it costs one column. It
  should be named for the pair direction and the verb, as Discourse's confusing naming showed.
- Peer flags are split by shared cohort and shared course because the idea's two relationship
  queries are distinct. A single "peers" flag with a scope setting would be a fifth value type.
- Levels only meaningfully carry some flags. Cohort-level `peers_in_cohort_may_start` is natural.
  A cohort registration for a course carries `peers_in_course_may_start`. At the learner level,
  the flag is about that learner as sender or as recipient, which is the pair question.
  The spec must pick one reading per flag, because "sender's configuration, recipient's, or both"
  is already an open question. A simple rule that matches the safe default is "both sides must
  not be closed", but that is for the spec.
- Role selection (which of `organisation_admin`, `site_admin`, `cohort_admin`, `cohort_viewer` is
  offered) is not a flag. It is a filter in the composer or the policy implementation.

Can presets express every combination? With four independent flags there are 16 effective
combinations at any one level, and presets express only those that are named. Real installs
want arbitrary mixes ("cohort peers yes, course peers no, learner to educator yes"). Presets
can cover the common ones (closed, educator-led, cohort community, open), but a custom mix needs a
custom preset or flags. Presets also cannot express "inherit part of this": a level that wants
to open just one thing must restate the rest.

## 4. Room for a platform-wide per-user level of service

What it needs: a later paid tier should open or close flags for a user (for example
`learner_may_start_with_educator` is open for a subscriber) without a rework.

- Flag columns or rows with tri-state values: a level of service is one more layer in the same
  resolution. The resolver takes an ordered list of layers, each returning "open", "closed" or
  "unset" for a flag. A new layer is another function, not a schema change to the existing rows.
  The layer can read from anything, such as a subscription table in another app.
  Where it sits is a decision for that later spec. It most likely sits between organisation (or
  registration) and learner, or beside learner. This is clearest when layers are resolved by
  iteration rather than by hard-coded field lookups.
- Presets: a level of service would be "the plan names a preset", but it then competes with the
  learner level's single preset. The preset model needs a rule for combining two names. This is
  the rework the idea fears.
- In both cases, keep the level order in one list in code, so inserting a layer is one line.
- Do not have the learner row stand for "paid": the idea says the learner level is how a paid
  arrangement is expressed today. A later plan should be able to replace that without migrating
  rows, which works if the plan only supplies a layer and the learner row stays a plain override.

## Recommendation

Use per-flag tri-state values, not named policies as the stored shape. Treat named presets as
an optional, code-only convenience.

1. Stored shape: one choice field per flag (`inherit / open / closed`, a `TextChoices` or
   small integer enum) on each level's row. Prefer this over a nullable boolean because the
   admin labels are correct ("Inherit", not "Unknown"), filters read well, and a locked
   value can be added later without a rework. Keep the four flags above as the closed list.
2. Resolver: a single function that walks an ordered list of layers (settings default, site,
   organisation, cohort or registration, learner) and returns the value together with the layer
   that supplied it. The `MessagingPolicy` uses the value. Tests and a later admin screen use the
   source. Closed by default means the settings default for each flag is closed, except
   `educator_may_start_with_learner`, which is open. Declare these defaults through `AppSettings`.
3. Rows: put the site and learner rows in `comms` and keep cohort, registration and organisation
   knowledge out of the `comms` base app, as the idea requires. Choose between one table per scope
   (integrity and inlines, more repetition) and a generic scope (one table, no integrity). Per-scope
   tables are the better admin experience and the better fit for `SiteAwareModelAdmin` inlines.
4. Presets, if wanted: a settings-declared dict of name to flag values that the admin form uses to
   fill in the flags, or that documentation names. They never get stored as the rule, so the level
   still falls through per flag. This keeps the readability of Teams without its all-or-nothing
   cost. It is not needed for the spec to ship. Per the project rule not to build unrequested
   functionality, treat it as a follow-up.
5. Explain: return the source from the resolver now. Defer an admin "why" screen.
6. Future level of service: add a layer function to the ordered list. No migration of existing rows.

Trade-offs at a glance:

| | Per-flag tri-state (recommended) | Named policy per level | JSON flags |
|---|---|---|---|
| Admin screen | clear per-flag fields, 4 dropdowns per row | one dropdown, simplest to read | free-form text, weakest |
| Composes across levels | yes, per flag | no, or needs additive presets | yes, per key |
| Partial override (open one thing) | one field | needs a new preset | one key |
| Adding a flag | migration | new preset and meaning change | no migration, no validation |
| Debugging "why" | per-flag source is exact | name only, hides which part matched | per-key source |
| Future level of service | one more layer | combining two names needed | one more layer |
| Locked / prohibit later | add a choice value | new preset | custom values |
| Risk | more fields in admin, more repetition across scope tables | combinatorial presets or all-or-nothing replace | typos, no admin UX |

Open items the spec still has to decide, which the shape does not settle: whose row governs a pair
(sender, recipient or both), how a cohort's and an individual registration's rows combine, whether
a closed flag blocks replies in an existing conversation, and whether a lock is wanted at the
organisation or site level.

## References

- Moodle, Override permissions: https://docs.moodle.org/405/en/Override_permissions
- Moodle, Override permissions (earlier version, same model): https://docs.moodle.org/27/en/Override_permissions
- Moodle, Messaging and privacy preferences: https://docs.moodle.org/39/en/Messages
- Moodle capability `moodle/site:messageanyuser`: https://docs.moodle.org/39/en/Capabilities/moodle/site:messageanyuser
- Canvas settings inheritance and locking (Instructure Community): https://community.canvaslms.com/t5/Canvas-Themes/Bring-account-settings-inheritance-into-parity-with-feature/idi-p/552893
- Canvas, how to manage new features for an account (lock option): https://community.canvaslms.com/docs/DOC-3095
- Canvas, account hierarchy: https://community.canvaslms.com/docs/DOC-2963
- Discourse, "personal message enabled groups" is confusingly titled: https://meta.discourse.org/t/personal-message-enabled-groups-is-confusingly-titled/290414
- Discourse, allow personal messages to staff for specific groups: https://meta.discourse.org/t/allow-personal-messages-to-staff-for-specific-groups/175513
- Microsoft Teams, assign policies, precedence: https://learn.microsoft.com/microsoftteams/policy-assignment-overview
- Django ticket 744 (NullBooleanField admin display): https://code.djangoproject.com/ticket/744
- NullBooleanField deprecation, use `BooleanField(null=True)`: https://codereviewdoctor.medium.com/nullbooleanfield-is-dead-7d3fc286ed6e

FLS code read: `freedom_ls/accounts/models.py` (`SiteSignupPolicy`), `freedom_ls/accounts/admin.py`,
`freedom_ls/base/app_settings.py`, `freedom_ls/course_access/config.py`,
`freedom_ls/site_aware_models/admin.py`, `claude_plugins/fls-dev/skills/app-settings/SKILL.md`,
`spec_dd/3. done/2026-09-27_00:24_user-communication-1-notifications-core/1. spec.md`.

status: ok
