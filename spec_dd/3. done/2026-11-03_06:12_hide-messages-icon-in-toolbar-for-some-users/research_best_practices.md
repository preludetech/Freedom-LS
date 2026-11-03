# Research: best practices for gating the Messages header icon

Note: URLs below are well-known references cited from prior knowledge; they were not re-fetched in this run.

## 1. Single source of truth for eligibility (server-side)
- Define ONE function, e.g. `can_use_messaging(user, site) -> bool` (or a richer "messaging capability" object), and use it in three places: the template/context processor that renders the icon, the messaging views/URLs (permission check, 403/404), and any sending/creating logic. UI must be a reflection of authorization, never the enforcement. Hiding the icon alone leaves the URL reachable (OWASP: forced browsing / broken access control).
  - https://owasp.org/Top10/A01_2021-Broken_Access_Control/
  - https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html (deny by default, enforce on every request)
- In Django, implement as a context processor or template tag that calls the same function the view's guard uses (mixin / decorator / `UserPassesTestMixin`). https://docs.djangoproject.com/en/stable/topics/auth/default/#limiting-access-to-logged-in-users-that-pass-a-test
- Return 404 (not 403) for a feature that is "off" for a tenant if you don't want to reveal its existence; 403 when the user is simply not entitled. Be consistent.

## 2. Flag vs configuration vs derived eligibility
Martin Fowler's feature-toggle taxonomy distinguishes release, ops, experiment and **permission** toggles by longevity and dynamism. A "messages on for this organisation" switch is a long-lived, per-request **permission/entitlement toggle**, i.e. configuration, not a release flag. https://martinfowler.com/articles/feature-toggles.html
- Tenant-level setting (site/organisation config field): coarse on/off, set by admins, durable. Best for "this organisation has comms".
- Role/relationship-derived eligibility: fine-grained, computed (e.g. "learner is in a cohort that has an educator", "user has at least one valid recipient"). Avoids stale manual flags and matches the real need (free-course learners have nobody to talk to).
- Recommended layering: tenant switch AND derived eligibility (AND-composed). Tenant off => hidden and blocked everywhere; tenant on => show only if the user has a conversation/recipient path, or already has existing threads (never strand someone with history/unread messages).
- Keep decision logic out of templates; templates ask one boolean. Keep the toggle "router" separate from toggle "configuration" (Fowler) so the check point is a single place.
- Avoid expensive queries per page render: cache per request (`cached_property` on a request-scoped object) or compute with a single `.exists()`; the header renders on every page. Consider caching unread-count and eligibility together.

## 3. Multi-tenant toggles in Django
- django-waffle: flags/switches/samples, per-user, group, percentage; supports custom flag model to scope by site/org. https://waffle.readthedocs.io/
- django-flags: condition-based flags (path, user, boolean, custom conditions). https://cfpb.github.io/django-flags/
- Many-tenant pattern without a library: a `SiteSettings`/`SiteConfig` model (OneToOne with `django.contrib.sites.Site`) with boolean fields, accessed via `request.site`. Sites framework: https://docs.djangoproject.com/en/stable/ref/contrib/sites/
- A library is justified for percentage rollouts, experiments, ops kill-switches; for a permanent per-site entitlement a plain model field is simpler and satisfies "don't build what isn't asked".
- Django's `django-guardian`/object permissions are overkill unless per-object ACLs needed.

## 4. Hide vs disable
- NN/g and common UX guidance: **hide** controls the user can never use in their context (reduces clutter, avoids confusion); **disable** (with explanation/tooltip) when the feature exists and the user may gain access via an action or when discoverability matters. https://www.nngroup.com/articles/modal-nonmodal-dialog/ is unrelated; relevant: https://www.nngroup.com/articles/progressive-disclosure/ and https://www.smashingmagazine.com/2021/08/frustrating-design-patterns-disabled-buttons/ (disabled buttons frustrate, especially without explanation).
- Here: free-course learners will never have messaging => hide. If a learner is in a messaging organisation but has no recipients yet, still prefer hide (or show an empty state only if they could be messaged by others/receive messages).
- Accessibility: if hiding via CSS, use real omission from the DOM (not `display:none` on a focusable item left reachable by AT inconsistently); if disabled, use `aria-disabled` and explain why. https://www.w3.org/WAI/ARIA/apg/
- Don't hide where it causes layout shift in a toolbar; render nothing and let flex layout reflow.

## 5. Consistency of related entry points
- Everything that deep-links to messages (notification emails, "message educator" buttons on cohort/course pages, unread badges, polling/HTMX endpoints, pane pickers) must use the same predicate. Otherwise users see a "Message" CTA that leads to a 404/403.
- Inbound messages: decide what happens when eligibility is lost after threads exist (read-only access, or still show icon when unread/existing threads). Fowler: toggles that flip state need defined behavior for existing data.
- HTMX: an endpoint hit when the feature is off should return a proper status (403/404), not a partial swapped into the header. Polling for the unread badge should not be rendered at all when the icon is hidden (avoids useless requests).

## 6. Testing practices
- Test matrix: tenant on/off x user with/without eligibility x existing threads. Assert both (a) icon absent/present in rendered header and (b) the view returns denial. Test that other sites' settings do not leak (multi-site isolation).
- Keep the predicate unit-tested separately from views; add one integration test per entry point.

## Recommendation summary
1. Per-site config flag as the outer gate (permanent entitlement, not a release flag).
2. Derived per-user eligibility (has a possible conversation partner, or has existing threads) as the inner gate.
3. One shared predicate used by header, views and all deep links; deny by default server-side.
4. Hide (omit from DOM) the icon when ineligible; no disabled state.
5. No feature-flag library needed unless gradual rollout is wanted.

status: ok
