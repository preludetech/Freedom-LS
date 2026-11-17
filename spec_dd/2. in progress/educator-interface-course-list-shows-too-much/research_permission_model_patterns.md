# Research: cross-organisation permission patterns for owned content

Note: written from established documentation knowledge. URLs are canonical doc pages and were not re-fetched in this run. Verify specifics before quoting.

## 1. Patterns found

### Content licensing / marketplaces
- Go1, OpenSesame, LinkedIn Learning, Coursera for Business: the content owner (provider) keeps ownership. The licensee org gets a *licence* (subscription or per-seat or per-course). Rights attach to the licensee org and are commercial in nature: catalogue visibility, assignment to own users, consuming seats. The licensee never edits, and never sees other licensees' data. Typical rights: browse/see in catalogue, preview (often limited or time-boxed trial), assign/enrol own users (consumes seats or is covered by a plan), reporting on own users only.
  - https://www.go1.com/ (platform and integration docs)
  - https://www.opensesame.com/ (per-course/per-seat licensing)
  - https://learning.linkedin.com/ (LinkedIn Learning content integration)
  - https://www.coursera.org/business (Coursera for Business)
- SCORM Cloud Dispatch: a provider publishes a course once, then creates a *dispatch* to a named destination (a licensee account) with explicit limits: enabled/disabled, registration cap (seat count), expiry date. Provider can revoke. Licensee launches and registers its own learners; reporting for those registrations goes to the licensee. This is the closest analogue to a named, per-org grant with limits.
  - https://rusticisoftware.com/products/scorm-cloud/ and https://cloud.scorm.com/docs/v2/guides/dispatch/
- Common thread: the grant is *to a named party*, is *revocable*, may carry *quantity/expiry*, and enrolment on behalf of others is the thing that is licensed. It is not bypassing the commercial gate; it replaces the gate with a contract.

### Drive / SharePoint sharing
- Google Drive: ladder viewer < commenter < editor (< content manager, owner). Each role is a superset. Sharing is to a named principal (user/group/domain). "Anyone with link" is a separate, explicit, discouraged wildcard. Organisation admins can restrict external sharing by default.
  - https://support.google.com/drive/answer/2494822 (sharing roles)
  - https://learn.microsoft.com/en-us/sharepoint/external-sharing-overview (SharePoint external sharing; tenant-level default can be "off" or "named guests only")
- SharePoint uses permission levels (ladder: Read, Contribute, Edit, Full Control) built from underlying independent permission bits; custom levels recombine bits. So even ladder products are flags underneath.

### GitHub
- Org/repo ladder: Read < Triage < Write < Maintain < Admin. Plus custom repository roles built from independent permissions (added because the ladder did not fit, e.g. "read plus manage issues"). Outside collaborators are named and per-repo; default for non-members of a private repo is no access; public repos give everyone read.
  - https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization
  - https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/managing-custom-repository-roles-for-an-organization

### Zanzibar / ReBAC
- Permissions are *relations* between an object and a subject (`doc:1#viewer@org:B`). Relations are independent tuples; hierarchy is added by explicit *rewrite rules* (`viewer = viewer OR editor OR owner`). Subjects can be sets (`org:B#member`). So you get independent grants and an opt-in implication graph, rather than a hard-coded ladder. Absence of a tuple is deny.
  - https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/
  - https://openfga.dev/docs/modeling/getting-started
  - https://authzed.com/docs/spicedb/concepts/schema
- Composition for us: `course#owner@org:A`; `course#lister@org:B`; `course#enroller@org:B`; `course#previewer@org:B`; `enroller` implies `lister`; `previewer` implies `lister`; progress visibility derives from (learner in org B) AND (learner enrolled in course), not from a tuple.

### Least privilege / default deny
- OWASP Authorization Cheat Sheet: "Deny by default", "enforce least privileges", "validate permissions on every request", "prefer ABAC/ReBAC over RBAC for fine-grained and cross-tenant rules", centralise the check.
  - https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
  - OWASP Top 10 A01 Broken Access Control (incl. "accessing other tenants' data"): https://owasp.org/Top10/A01_2021-Broken_Access_Control/
- Multi-tenant guidance (e.g. AWS SaaS tenant isolation): cross-tenant access only via explicit, auditable grants.
  - https://docs.aws.amazon.com/whitepapers/latest/saas-architecture-fundamentals/tenant-isolation.html

## 2. Answers

**(1) Ladder vs independent flags.**
- Ladder is preferred when rights are genuinely nested, with one axis such as read < write < admin, and the audience is non-technical. Failure modes: it bundles unrelated rights, so granting one means over-granting another. GitHub and SharePoint both had to add custom roles or permission bits for this reason. Ladders also break when a new right does not fit in a position.
- Independent flags are preferred when rights are orthogonal. Failure modes: combinatorial states, some of them nonsensical (e.g. can register but cannot see), more config to get wrong, harder to explain. Mitigate with implication rules (ReBAC rewrite): `register` and `preview` each imply `see`, and validate this at parse time.
- Our rights: see, preview, register are not a clean line. Preview (content access) and register (enrolment) are orthogonal commercially, since a reseller may enrol but never see content, or a reviewer may preview but never enrol. So use independent flags with `see` implied by any other.

**(2) Default for non-granted orgs on publicly-joinable content.**
Deny-all in the educator interface. `audience: public` governs *learner* self-join through the gated access backend. It is not an educator-side right. Every comparable system keeps "anyone can acquire via the storefront" separate from "a partner org's admin tool lists/administers it". See-only as a default leaks listing and metadata, invites the exact bug (staff reach the course and its actions), and violates OWASP deny-by-default. An org's own learners can still self-join through the learner path. A grant of `see` is the explicit way to get listing.

**(3) Should enrol-on-behalf bypass the commercial/approval gate?**
No, not implicitly. In licensing models, enrolling on behalf of others *is* the licensed act, and it is granted by contract (seats, plan, dispatch cap). So `register` must be an explicit grant, and the grant is itself the owner's statement that the gate is waived for that org. Two defensible variants: (a) grant means gate waived (owner trusts partner, simplest); (b) grant is subject to the gate still, with a seat cap (SCORM Cloud dispatch style). Recommend (a) for v1, documented clearly, with an optional seat limit left for later. Without any grant, no bypass is possible.

**(4) Progress visibility: grant or automatic?**
Automatic, scoped. Seeing progress of your own learners is a property of the org-to-learner relationship (data about your people), not a right over the content. Dispatch, Go1 and LinkedIn all report to the licensee on its own users. Rule: an educator sees progress for learners of their own org who are enrolled, whatever the route of enrolment (including self-join). It requires no content grant, and it never exposes other orgs' learners. A grant would create a bad failure mode: a learner enrolled but their org unable to see their progress. A separate grant is only needed if the *owner* wants to see licensee learners' progress, which is out of scope.

## 3. Recommended model

- Grants are independent flags per named org in front matter (no wildcard): `see`, `preview`, `register`. Reasoning: rights are orthogonal; independent flags avoid over-granting.
- Implication: `preview` or `register` implies `see`; validate on load. Reasoning: avoids nonsensical states with the minimum of rules (ReBAC-style rewrite, not a ladder).
- Default for non-owner, non-granted orgs: deny-all in the educator interface (no list, no detail, no preview, no register), including for `audience: public`. Reasoning: OWASP deny-by-default; public describes learner self-join only.
- Owner orgs have all rights implicitly; site-wide courses (no owner) keep their existing behaviour. Reasoning: ownership is the root relation; do not require self-grants.
- `register` is an explicit grant and means the owner waives the price/application gate for that org's educator enrolments. Reasoning: the licensing norm is that on-behalf enrolment is a contracted right; without grant nothing bypasses the gate. Seat caps deferred.
- Progress for own learners is automatic and derived (learner in your org AND enrolled), never a grant. Reasoning: it is data about your own people, not a content right; avoids blind spots.
- One central permission function used by list, detail, preview, and enrol views, with the enrol action re-checked server-side. Reasoning: OWASP "validate on every request"; the bug came from list visibility and actions being checked separately.

status: ok
