# Research: role assignment rules in comparable systems

Scope: "who may grant which role, to whom, at what scope" — a different question from "who may
do what with a role once held" (that's the capability matrix in `idea.md`). This file is about
the assign/remove utilities in `role_based_permissions/utils.py`
(`assign_object_role`, `remove_object_role`, `assign_site_role`, `remove_site_role`) and the rules
`idea.md` has already settled: site admins assign anything; organisation_staff assign `instructor`
and `ta` on cohorts in their organisation; nobody assigns to themselves; removing the last
`site_admin` on a site is refused.

## How comparable systems govern this

### Moodle — a separate matrix, not embedded in the capability table

Moodle keeps role-assignment rules in **three matrices distinct from the capability table**:
"Allow role assignments", "Allow role overrides", "Allow role switches"
(Site administration → Users → Permissions → Define roles). Each matrix answers "can a user
holding role X grant/override/switch-into role Y" — a role-to-role grid, not a
capability-to-role grid. By default a Teacher may only assign Non-editing teacher, Student and
Guest; Teacher-to-Teacher assignment must be turned on explicitly by an admin. Overriding a role
requires `moodle/role:override` or the narrower `moodle/role:safeoverride` (override only roles
with *less* access than your own — Moodle's one explicit escalation guard). Switching roles
requires `moodle/role:switchroles` and is time-boxed to the session.
[Managing roles](https://docs.moodle.org/502/en/Managing_roles),
[moodle/role:assign](https://docs.moodle.org/405/en/Capabilities/moodle/role:assign),
[Allow role assignments](https://docs.moodle.org/19/en/Allow_role_assignments).

Takeaway: assignability is naturally a **role × role matrix** ("who may grant whom"), separate
from the capability × role matrix. Trying to fold "may assign instructor" into the same row as
"may edit cohort" conflates two different questions (what you can do vs. what power you can
hand to someone else) and Moodle's own docs treat them as separate admin screens for that reason.

### Canvas — role type restricts which permissions a custom role can even carry

Canvas ties permissions to a `base_role_type` (`AccountAdmin`, `TeacherEnrollment`,
`TaEnrollment`, `DesignerEnrollment`, `StudentEnrollment`, `ObserverEnrollment`,
`AccountMembership`) and each permission declares which base role types it is `available_to`.
An account-level custom role can only ever be built on `AccountMembership` or `AccountAdmin`;
a course-level custom role must inherit `TeacherEnrollment` etc. This is the "assignment scope"
concept FLS already has (`object` vs `site` vs `system`) — Canvas enforces it the same way: you
cannot manufacture a role that mixes account-level and course-level permissions, because
assignability of a permission is gated on the base role type, not on who is doing the granting.
[Roles API](https://canvas.instructure.com/doc/api/roles.html),
[Permissions API](https://osu.instructure.com/doc/api/file.permissions.html).

### AWS IAM — permission boundaries: never grant more than you hold

IAM's permission-boundary pattern states the escalation rule precisely: a boundary sets the
*maximum* an identity can ever be granted, and the effective permission is the intersection of
the boundary and the attached policy — so a principal can create policies for others but those
policies can never exceed the principal's own boundary. This is the formal version of "nobody
assigns to themselves" plus "nobody grants a role with more power than they hold" — IAM doesn't
prevent self-modification by name, it prevents *escalation* structurally, by making the boundary
un-raisable by the entity it constrains (only a separate, more-privileged principal can attach or
change a boundary on you).
[Preventing IAM privilege escalation with permission boundaries](https://immrbhattarai.medium.com/preventing-iam-administrator-privilege-escalation-with-permission-boundaries-ac1815f685b0),
[IAM permission boundaries explained](https://securebin.ai/blog/aws-iam-permission-boundaries-explained/).

Takeaway for FLS: the roadmap's rule "organisation_staff assign instructor/ta only" is already an
IAM-style boundary expressed as a fixed allow-list rather than a computed "no more than you hold"
rule — simpler to implement and to explain, and adequate given there are only four roles in play.
A computed "can't grant more than you hold" rule is unnecessary machinery for four roles; keep
the explicit allow-list.

### GitHub, Slack, Microsoft 365 — the "last admin" pattern, applied consistently

All three enforce the same invariant with the same mechanics, worth naming because FLS's
"removing the last site_admin is refused" rule is this pattern exactly:

- **GitHub**: an organization must always have at least one Owner; GitHub blocks removing or
  demoting the last Owner (including removing *yourself*), and blocks the last Owner from leaving
  the org. Work-around is always "promote someone else first."
  [What happens when the single owner leaves](https://github.com/orgs/community/discussions/144932).
- **Slack**: a workspace must always have a Primary Owner; the Primary Owner cannot deactivate
  their own account without first transferring ownership to another member.
  [Understand the Primary Owner role](https://slack.com/help/articles/360038161033-Understand-the-Primary-Owner-role).
- **Microsoft 365 / Entra ID**: the last Global Administrator cannot delete or demote themselves,
  and a signed-in principal cannot delete itself — by design, to avoid an orphaned tenant.
  Microsoft's own guidance is to keep **at least two** Global Admins per tenant, not one, because
  a lone admin who is locked out (lost MFA device, etc.) is itself an outage.
  [Microsoft Q&A: removing the last global administrator](https://learn.microsoft.com/en-in/answers/questions/5637870/what-to-do-if-i-want-to-remove-the-last-global-adm),
  [Explore administrator roles in Microsoft 365](https://learn.microsoft.com/en-us/training/modules/manage-roles-groups-microsoft-365/4-explore-admin-roles-microsoft-365).

Common thread across all three: the check is phrased as "would this leave zero holders of the
top role **on this scope**", never "would this leave the *actor* without power" — i.e. it is a
property of the role population, evaluated at write time, and it blocks both *removal* and
*self-demotion* through the same guard. None of the three make an exception for "but an even
higher-level admin could fix it later" — the write is refused unconditionally, up front.

### Google Workspace — some privileges are structurally un-delegatable

Google Workspace's Super Admin is not just "has more permissions" — certain admin console
capabilities (creating/assigning admin roles, restoring deleted users, granting domain-wide
delegation, Secure LDAP) are hard-coded to Super Admin only and cannot be handed to a delegated
admin role at all, regardless of what permissions that role's console lets you tick.
[Prebuilt administrator roles](https://knowledge.workspace.google.com/admin/users/prebuilt-administrator-roles),
[Delegate administrator privileges](https://support.google.com/a/answer/6395507?hl=en).

Takeaway: "who may assign site_admin/organisation_staff" doesn't need to be *computed* from a
general rule — it is legitimate (and simpler) to hard-code "only site_admin, full stop", mirroring
Google's un-delegatable Super Admin actions, rather than trying to express it as "whoever holds a
role at least as powerful."

## Edge cases: what these systems do, and the FLS read

| Edge case | What comparable systems do | Read for FLS |
|---|---|---|
| **Self-removal of the role you're using to act** | GitHub/Slack/M365 block it outright when you're the last holder; none of the three block it merely because you're removing your *own* current role if another holder exists — self-removal is fine as long as someone else remains. | The roadmap's "nobody assigns to themselves" already blocks self-*assignment*. Self-*removal* isn't addressed by that line and needs its own answer (see open questions below). |
| **Self-assignment** | Not directly modelled by any of the six systems (admins don't typically "apply" for a role) — the closest analogue is IAM's structural ban on an identity raising its own boundary. | Matches the roadmap's explicit "nobody assigns to themselves" — treat as settled, applies to every role, including `site_admin` re-confirming their own grant (a no-op should still be refused, not silently accepted, so the rule stays legible). |
| **Escalation — granting a role more powerful than you hold** | Moodle's `safeoverride` capability limits overriding to roles below your own; IAM boundaries make it structurally impossible; Google hard-codes some grants to Super Admin only. | FLS doesn't need a computed "no more than you hold" rule for four roles — the roadmap's fixed allow-list (site_admin: anything; organisation_staff: instructor/ta only) already has the same effect and is far easier to audit. |
| **Assigning to a user from another organisation or site** | Canvas/Moodle roles are scoped to the account/course they're assigned on; assigning cross-scope isn't a "who may assign" question so much as a "does the target object belong to the actor's scope" question, enforced the same way object-scoped instance checks already work. | `assign_object_role` and `assign_site_role` take `target`/`site` directly with no check that the *target user* is a member of that organisation/site at all — worth an explicit guard: organisation_staff assigning instructor/ta must target a cohort *in their own organisation*; that's already the intent of "own organisation" in the matrix, but nothing in `utils.py` enforces it — the check has to sit in the view/service layer that calls these utilities, since the utilities are scope-blind about the caller. |
| **Assigning to an inactive/deactivated user** | None of the six systems block granting a role to a disabled account outright — Slack/GitHub instead prevent an inactive/deactivated account from *using* the grant, not from receiving it — but all treat it as a no-op rather than an error. | Recommend allowing the assignment to succeed (so it's ready when the user is reactivated) but the grant should not appear to have effect while the target is deactivated — this is a query-layer concern (`learners_visible_to`-style helpers already filter by active status) rather than an assignment-time refusal. |
| **Removing a grant from someone who holds several roles** | Guardian-style systems (and Canvas, Moodle) always operate role-by-role: removing `ta` on a cohort never touches an unrelated `instructor` grant on a different cohort, or `organisation_staff` on the organisation. | Already how `remove_object_role`/`remove_site_role` work — role, target and user are all part of the lookup, so this is a non-issue; worth stating explicitly in the spec so it's tested. |
| **The grant still in effect on an open page (mid-session revocation)** | Entra ID and Slack: an admin's session is not immediately invalidated when their role is downgraded elsewhere — permission is re-checked per request, not cached for the session; the *next* request the demoted user makes gets the new (lower) permission. GitHub: same — org-scoped API calls are re-authorized per request. | Matches `idea.md`'s "denied experience" section already: 403 with an explanatory fragment when an action they could see is no longer theirs to perform. No caching of role state beyond the request is needed; `sync_user_object_permissions` already runs at assignment/removal time, so guardian's per-request check is already correct — no extra work here beyond what spec 1's hook does. |
| **Cohort-scoped grant when the cohort is deactivated** | Not directly modelled (no comparable system has a "deactivate the container" concept quite like Cohort) — closest analogue is Canvas concluding a course, which does **not** delete enrollments/roles, it just makes the course read-only/inactive; the role rows survive dormant. | Recommend the same: deactivating a `Cohort` should not delete or auto-deactivate `ObjectRoleAssignment` rows pointing at it — the grant becomes inert because the cohort itself is unreachable/read-only, not because the grant was revoked. Reactivating the cohort should restore the grant's effect with no re-assignment needed. Needs product-owner confirmation (see below). |
| **User leaves the organisation while holding a cohort-scoped instructor/ta grant** | Canvas: removing a user from a course-affiliated account does not auto-remove course-level enrollments elsewhere; it's a manual/administrative cleanup step, sometimes automated by SIS sync but not by the permission engine itself. | FLS's `instructor`/`ta` grants are `ObjectRoleAssignment`s on a `Cohort`, independent of `learner_management` organisation membership records — nothing today ties the two together. Decide explicitly whether leaving an organisation should cascade-deactivate the person's cohort-scoped grants in that organisation, since the roadmap doesn't currently say (see open questions below). |
| **Concurrency on "last admin" checks** | GitHub/Slack/M365 all perform the "would this be the last one" check as part of the same transaction/request that performs the removal — race conditions between two simultaneous "remove the second-to-last admin" requests are handled by normal DB-transaction serialization on the membership table, not by application-level locking documented anywhere public. | `remove_site_role` today does a bare `.filter().update()` with **no check at all** for "is this the last active `site_admin` on this site" — the roadmap's "removing the last site_admin on a site is refused" rule isn't implemented yet. It needs to run the count-and-refuse check inside the same `transaction.atomic()` block already used by `assign_object_role`, with `select_for_update()` on the `SiteRoleAssignment` queryset (or a `SELECT ... FOR UPDATE` equivalent) to close the race between two concurrent removals of the second-to-last admin. |

## Should "who may assign" be a row in the capability matrix, or a separate table?

Moodle's own admin UI answers this: it is a **separate table**, keyed role-to-role
("actor's role" × "role being granted") rather than role-to-capability. The reasons that hold for
Moodle hold for FLS too:

- The capability matrix (`idea.md`'s table) answers "what can a role-holder *do*." Assignability
  answers "what power can a role-holder *hand to someone else*." These are different questions
  even when the answer looks similar (e.g. `organisation_staff` both *does* cohort/registration
  management directly *and* is separately allowed to *grant* `instructor`/`ta` — but it doesn't
  follow that every capability-row entry implies an equivalent assign-row entry, and vice versa:
  `organisation_staff` cannot do anything an `instructor` can do inside a specific cohort's
  content, yet can still grant the `instructor` role there).
  Folding both into one table produces a matrix where every cell needs a "do" flag and a "grant"
  flag, doubling its width for no readability gain, and it invites the exact conflation IAM's
  documentation is at pains to rule out (having a permission is not the same as being able to
  grant it).
  - With only two granting roles (`site_admin`, `organisation_staff`) and two grantable roles
    (`instructor`, `ta` — `site_admin`/`organisation_staff` grants are exhaustively described by
    "site_admin only") a separate table is tiny: 2 rows × 2 columns, not worth a fifth column on
    the existing capability table.

**Recommendation: a separate, small assignability table**, not a widened capability matrix.

## Implications for FLS

### Proposed assignability table

| Grantor role | May grant | May remove | Scope of the grant |
|---|---|---|---|
| `site_admin` | `site_admin`, `organisation_staff`, `instructor`, `ta` | same four | site (site_admin), organisation (organisation_staff), cohort (instructor/ta) — anywhere on the site |
| `organisation_staff` | `instructor`, `ta` | `instructor`, `ta` | cohorts within **their own** organisation only |
| `instructor` | none | none | — |
| `ta` | none | none | — |

Universal rules that sit beside the table, not inside it (mirrors the last-admin pattern and IAM
boundary reasoning above):

1. No one may assign a role to themselves (settled in `idea.md`).
2. Removing the last active `site_admin` on a site is refused (settled in `idea.md`) — **not yet
   enforced in `remove_site_role`**; needs a count-and-refuse check inside the existing
   `transaction.atomic()`, with row locking to close the concurrency race.
3. `organisation_staff` may only grant/remove on cohorts belonging to their own organisation —
   **not yet enforced anywhere in `utils.py`**; the utilities are scope-blind about the caller
   (they take `user`, `target`, `role`, `assigned_by` with no check that `assigned_by` is even
   entitled to touch `target`). This check belongs in the view/service layer spec 9 builds, calling
   `assign_object_role`/`remove_object_role` only after confirming scope — or, if this spec wants
   the guarantee closer to the data layer, a new `assigned_by`-aware wrapper that both utilities
   call through.

### Edge-case questions needing a product-owner decision, with a suggested default

1. **Self-removal.** May an `organisation_staff` remove their own `organisation_staff` grant
   (stepping down), and if they're the last one in the organisation, is that refused the same way
   the last `site_admin` is? *Suggested default: yes, self-removal is allowed like any other
   removal; extend the "last admin" refusal to `organisation_staff` too — an organisation with
   zero staff and only site_admin has no path back in without a site_admin lookup for that
   organisation, which is a real gap unless site_admin can always reach organisations they don't
   have a role on (per the settled "site admins assign anything").*
2. **Cross-organisation/site targeting.** Should `assign_object_role`/`remove_object_role` gain an
   explicit scope check, or is that entirely the caller's responsibility (view/service layer)?
   *Suggested default: caller's responsibility for this spec, since the utilities are shared by
   site_admin (unscoped) and organisation_staff (scoped) callers with genuinely different rules —
   but the spec should require a test that an organisation_staff attempt to assign onto another
   organisation's cohort is rejected somewhere, or it will only be caught by the UI, not the data
   layer, once the API/CLI exists.*
3. **Inactive/deactivated target user.** Should assigning a role to a deactivated user be blocked,
   allowed as a no-op, or allowed and simply invisible until reactivation? *Suggested default:
   allowed and inert — the grant persists so nothing needs re-doing on reactivation, and
   visibility helpers already filter by active status.*
4. **Cohort deactivation and existing grants.** Does deactivating a `Cohort` deactivate the
   `ObjectRoleAssignment`s pointing at it, or leave them dormant-but-intact for reactivation?
   *Suggested default: leave them intact; the cohort's own `is_active=False` already makes it
   unreachable, so a second deactivation of the grant is redundant and would need its own
   re-assignment step on cohort reactivation, which is unnecessary friction.*
5. **Organisation departure and cohort-scoped grants.** When a person's organisation membership
   ends, do their `instructor`/`ta` grants on that organisation's cohorts auto-deactivate, or is
   that a manual step for whoever manages the departure? *Suggested default: manual for now — the
   `ObjectRoleAssignment` model has no link to organisation membership today, and auto-cascading
   would require introducing that link; flag as a follow-on spec if the product owner wants
   automatic cleanup, rather than building it into spec 5's scope.*
6. **Concurrency on the last-admin check.** Confirm the count-and-refuse check for "last
   `site_admin`" (and, if #1 above is accepted, "last `organisation_staff` per organisation") runs
   inside a transaction with row-level locking (`select_for_update()`), not a plain count-then-update,
   to close the race between two simultaneous removals. *Suggested default: yes, lock — this is an
   implementation requirement, not a product decision, and should just be written into the spec.*

## Sources

- [Moodle: Managing roles](https://docs.moodle.org/502/en/Managing_roles)
- [Moodle: Capabilities/moodle/role:assign](https://docs.moodle.org/405/en/Capabilities/moodle/role:assign)
- [Moodle: Allow role assignments](https://docs.moodle.org/19/en/Allow_role_assignments)
- [Canvas: Roles API](https://canvas.instructure.com/doc/api/roles.html)
- [Canvas: Permissions API](https://osu.instructure.com/doc/api/file.permissions.html)
- [AWS: Preventing IAM privilege escalation with permission boundaries](https://immrbhattarai.medium.com/preventing-iam-administrator-privilege-escalation-with-permission-boundaries-ac1815f685b0)
- [AWS: IAM permission boundaries explained](https://securebin.ai/blog/aws-iam-permission-boundaries-explained/)
- [GitHub: what happens when the single owner leaves an org](https://github.com/orgs/community/discussions/144932)
- [Slack: Understand the Primary Owner role](https://slack.com/help/articles/360038161033-Understand-the-Primary-Owner-role)
- [Microsoft Q&A: removing the last global administrator](https://learn.microsoft.com/en-in/answers/questions/5637870/what-to-do-if-i-want-to-remove-the-last-global-adm)
- [Microsoft Learn: Explore administrator roles in Microsoft 365](https://learn.microsoft.com/en-us/training/modules/manage-roles-groups-microsoft-365/4-explore-admin-roles-microsoft-365)
- [Google Workspace: Prebuilt administrator roles](https://knowledge.workspace.google.com/admin/users/prebuilt-administrator-roles)
- [Google Workspace: Delegate administrator privileges](https://support.google.com/a/answer/6395507?hl=en)

## Code read for this research

- `freedom_ls/role_based_permissions/utils.py` — `assign_object_role`, `remove_object_role`,
  `assign_site_role`, `remove_site_role`: none of the four currently enforce scope-of-grantor
  (organisation membership) or a last-admin refusal; both are gaps against the settled rules in
  `idea.md`.
- `freedom_ls/role_based_permissions/models.py` — `ObjectRoleAssignment`, `SiteRoleAssignment`,
  `SystemRoleAssignment`: role grants are `(user, scope-object, role)` tuples with `is_active`,
  independent of any organisation-membership model — nothing cascades between them today.
- `freedom_ls/role_based_permissions/roles.py` — `instructor`/`ta`/`organisation_staff` are all
  `SCOPE_OBJECT`; `site_admin` is `SCOPE_SITE`; this matches the assignability table's scope
  column above.

status: ok
