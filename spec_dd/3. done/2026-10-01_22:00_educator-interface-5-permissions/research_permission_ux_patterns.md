# Research: UX Patterns for Permission-Aware Interfaces

This document summarises best practices and established patterns for building UIs where different users see different things based on their permissions. The focus is on admin/educator interfaces in multi-role platforms.

---

## 1. Hiding vs Disabling UI Elements

The core decision: when a user lacks permission for an action, should the button/link be **hidden** entirely or shown in a **disabled** state?

### When to Disable (show but grey out)

- **The feature exists and the user should know about it.** Disabled elements teach users what the system can do. This is valuable for onboarding and for communicating upgrade paths (e.g. "this feature is available on a higher plan").
- **The action is temporarily unavailable.** For example, a "Submit" button that is disabled until a form is valid. The user can see the goal and understands what they need to do to unlock it.
- **Removing the element would cause confusing layout shifts.** If a toolbar has 5 buttons and one disappears based on role, users familiar with the layout will be disoriented.
- **The user might need to request access.** A disabled button with a tooltip saying "Contact your administrator for access" is more helpful than the button not existing at all.

**Always pair disabled elements with an explanation.** A tooltip, inline hint, or adjacent text should explain:
1. Why the element is disabled
2. How to enable it (if possible)

### When to Hide (remove from the UI entirely)

- **The feature is irrelevant to the user's role.** An educator does not need to see student-only navigation items. A student does not need to see admin controls. Showing these as disabled adds noise without value.
- **Security-sensitive controls.** Admin overrides, destructive operations, and system configuration should be hidden from users who cannot use them. Showing them disabled leaks information about system capabilities.
- **The feature would cause confusion.** If a user cannot understand what a disabled button does because the surrounding context is also hidden, hide the button too.

### Decision Framework

| Scenario | Recommendation |
|---|---|
| User could gain access (upgrade, request) | Disable with explanation |
| Feature is role-irrelevant (wrong user type) | Hide |
| Temporarily unavailable (form incomplete) | Disable |
| Security-sensitive admin controls | Hide |
| Layout would break if removed | Disable |
| Feature requires context user does not have | Hide |

### Key Rule

> "Disable if you want the user to know a feature exists but is unavailable. Hide if the value shown is currently irrelevant and can't be used."
> -- [Smashing Magazine: Hidden vs. Disabled In UX](https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)

**Never hide primary navigation or key filters** that users expect to persist. This creates a disorienting experience where the interface feels broken rather than restricted.

---

## 2. Progressive Disclosure Based on Roles

Progressive disclosure means revealing functionality incrementally based on the user's role, experience level, or current task.

### Patterns for Multi-Role Interfaces

**a) Role-Specific Navigation**

The most common pattern: the navigation itself changes based on role. An educator sees "Manage Cohorts", "View Progress", "Course Content". A student sees "My Courses", "My Progress". A superadmin sees everything.

- Use a single consistent navigation structure per role, not a universal nav with items flickering in and out.
- If a user has multiple roles, provide a clear **role switcher** (see below).

**b) Adaptive Labels**

Change labels based on what the user can actually do. For example:
- A user with edit permission sees "Edit Contact"
- A user with view-only permission sees "View Contact"

This is more honest and less frustrating than showing "Edit Contact" that opens a read-only view.

**c) Contextual Feature Sections**

Within a page, group features by permission level:
- Core information visible to all authorised users
- Action buttons visible only to users who can perform those actions
- Admin/configuration sections visible only to administrators

Use clear visual separation (headings, cards, dividers) so the page feels complete at every permission level rather than like something is missing.

**d) Role Switcher for Multi-Role Users**

For platforms where a single user may hold multiple roles (e.g. someone who is both an educator and an administrator):
- Provide a clear role context indicator showing which role is currently active
- Allow switching between roles via a dropdown or toggle in the header
- Change the interface immediately upon role switch -- do not require a page reload where possible

### Anti-Pattern: The "Sparse Page"

When progressive disclosure is done poorly, lower-permission users see a page that feels empty -- a heading, one or two items, and vast whitespace where hidden elements would be. Design each permission level's view to feel **complete in itself**.

---

## 3. Feedback When Permission Is Denied

Users will inevitably encounter permission boundaries. How the system communicates denial significantly affects trust and satisfaction.

### In-Context Denial (Preferred)

When a user tries an action they cannot perform:

- **Inline message near the action point.** "You do not have permission to edit this cohort. Contact your organisation administrator." This is the least disruptive and most helpful pattern.
- **Toast/notification.** A brief, non-blocking notification that appears and fades. Good for actions triggered by buttons. Keep the message specific: "Permission denied: only cohort managers can remove students" is better than "Permission denied."
- **Modal for destructive actions.** If a user somehow reaches a confirmation step for something they cannot do, a modal explaining why is appropriate.

### Full-Page Denial

For page-level access restrictions:

- **Use HTTP 403, not 404.** If the user knows the resource exists (e.g. they followed a link from within the app), showing 404 ("not found") is confusing and dishonest. Use 403 ("forbidden") with a helpful message.
- **Exception: security-sensitive resources.** If revealing that a resource exists is itself a security concern, 404 is appropriate. But in most admin/educator interfaces, the user already knows the resource exists.
- **Provide a clear next step.** The 403 page should include: what happened, why, and what to do next (go back, contact admin, request access).

### Permission Denial Message Anatomy

A good denial message includes three parts:

1. **What happened:** "You cannot edit this course."
2. **Why:** "Only course administrators have edit access."
3. **What to do:** "Contact [admin name] to request access, or go back to the course list."

### Anti-Patterns

- Generic "Access Denied" with no explanation
- Redirecting to the homepage silently
- Showing a 500 error page
- Showing a login page when the user is already logged in (suggests session issues rather than permission issues)

---

## 4. Role Assignment UX

How administrators assign and manage roles for other users.

### Proven Patterns

**a) Role Dropdown on User Profile/Detail Page**

The simplest pattern. On a user's profile or detail page, a dropdown or select element allows the admin to assign a role. Works well when:
- There are few roles (2-5)
- Roles are mutually exclusive
- Assignment is infrequent

**b) Role Cards with Descriptions**

Each role is presented as a card with:
- Role name
- Brief description of what the role can do
- Visual indicator of current selection

This is better than a plain dropdown when role names are not self-explanatory. Users can understand the implications of each role before assigning it.

**c) Permission Matrix (for Advanced Admin)**

A table/grid showing roles as columns and permissions as rows, with checkboxes at intersections. This is powerful but complex -- only appropriate for superadmin-level interfaces where custom roles are supported.

**d) Bulk Role Assignment**

For assigning a role to many users at once:
- Multi-select user list + role dropdown + "Apply" button
- Or: select users via checkboxes in a table, then choose an action from a bulk actions menu

**e) Role Assignment with Scope**

In multi-tenant or multi-cohort systems, roles often apply within a specific scope:
- "Educator **for** Cohort X" rather than "Educator" globally
- Use a two-step assignment: first select the role, then select the scope

### Best Practices

- **Show a confirmation step** before changing roles, especially for demotions or removals. "Remove educator access for Jane Doe? They will no longer be able to view student progress for Cohort A."
- **Show current role clearly** before offering a change. Do not make the user guess what role someone currently has.
- **Audit trail.** Show who assigned a role and when. This is both a security measure and a UX aid for administrators trying to understand the current state.
- **Principle of least privilege as default.** New users should start with the minimum role. The interface should not default to a high-permission role in dropdowns.
- **Real-time preview.** Where feasible, show what the user will be able to see/do after role assignment. This reduces errors from misunderstanding role definitions.

### Role Hierarchy Display

If roles form a hierarchy (e.g. Admin > Educator > Student), display this visually:
- Indented list showing inheritance
- Or a simple diagram showing that "Educator has all Student permissions plus..."

This helps administrators understand that assigning "Educator" implicitly grants "Student" capabilities.

---

## 5. Common Permission UX Mistakes

### Mistake 1: 404 Instead of 403

Showing "Page not found" when the real issue is "you don't have permission." This leaves users confused about whether they have the wrong URL or the wrong access level. Use 403 with a clear message unless there is a specific security reason to hide resource existence.

### Mistake 2: Inconsistent Hiding

Some pages hide elements the user cannot access; other pages show them disabled; still others show them fully active but fail on click. Pick one strategy per element type and apply it consistently across the entire application.

### Mistake 3: Silent Failures

The user clicks a button, nothing happens, no error message appears. The action was blocked by a permission check but no feedback was given. Always provide feedback when an action is denied.

### Mistake 4: Showing Disabled Buttons Without Explanation

A greyed-out button with no tooltip, no title attribute, and no adjacent text. The user has no idea why the button is disabled or how to enable it. Every disabled element needs a reason.

### Mistake 5: Leaking Information via Disabled Elements

Showing a disabled "Delete Organisation" button to a regular educator tells them the capability exists and hints at system architecture. For security-sensitive operations, hide rather than disable.

### Mistake 6: Permission Checks Only on the Frontend

Hiding a button in the UI but not enforcing the permission on the server. If a user crafts a direct request, the action succeeds. **All permission checks must be enforced server-side.** The frontend is for UX, not security.

### Mistake 7: Confusing Error Messages

"Error: insufficient privileges" tells the user nothing actionable. Better: "You need the 'Cohort Manager' role to add students. Contact your administrator to request this role."

### Mistake 8: Role Changes Without Confirmation

Accidentally changing someone's role because a dropdown changed on click with no confirmation step. Always require explicit confirmation for role changes, especially privilege escalation or removal.

### Mistake 9: No Graceful Degradation for Edge Cases

A user's role changes while they have the page open. They click a button that was available when the page loaded but is no longer permitted. The system should handle this gracefully (clear error message, suggest refreshing) rather than showing a cryptic server error.

### Mistake 10: Over-Hiding Creates "Empty" Experiences

Hiding so many elements that certain roles see nearly-blank pages. Each role's view should feel like a complete, intentional interface -- not a stripped-down version of someone else's interface.

---

## Summary: Key Principles

1. **Hide for irrelevance, disable for awareness.** If the user has no business knowing a feature exists, hide it. If they should know but cannot use it, disable with explanation.
2. **Always explain denial.** Every permission boundary the user encounters should include what happened, why, and what to do next.
3. **Enforce server-side.** Frontend hiding/disabling is a UX convenience, not a security mechanism.
4. **Be consistent.** Pick a strategy and apply it uniformly across the application.
5. **Design each role's view as a complete experience.** Do not design for the highest-permission role and then subtract.
6. **Confirm role changes.** Especially demotions and removals.
7. **Use 403 not 404** unless resource existence itself is sensitive.

---

## Sources

- [Smashing Magazine: Hidden vs. Disabled In UX (2024)](https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)
- [Smart Interface Design Patterns: Hidden vs. Disabled](https://smart-interface-design-patterns.com/articles/hidden-vs-disabled/)
- [Nielsen Norman Group: Disabled Accessibility - The Pragmatic Approach](https://www.nngroup.com/articles/disabled-accessibility-the-pragmatic-approach/)
- [Authress: Choosing the Right Error Code 401, 403, or 404](https://authress.io/knowledge-base/articles/choosing-the-right-http-error-code-401-403-404)
- [Ben Nadel: Handling Forbidden RESTful Requests: 401 vs. 403 vs. 404](https://www.bennadel.com/blog/2400-handling-forbidden-restful-requests-401-vs-403-vs-404.htm)
- [MDN Web Docs: 403 Forbidden](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/403)
- [Sukanya Sen: Case Study - Designing Roles and Permissions (Medium)](https://bootcamp.uxdesign.cc/designing-roles-and-permissions-ux-case-study-b1940f5a9aa)
- [Edwin Choate: Roles and Permissions Redesign](https://edwinchoate.com/articles/roles-permissions-redesign/)
- [Perpetual: How to Design Effective SaaS Roles and Permissions](https://www.perpetualny.com/blog/how-to-design-effective-saas-roles-and-permissions)
- [CreateBytes: Multi-Role UX - The 2026 Guide to Platform Design](https://createbytes.com/insights/designing-ux-for-multi-role-platforms)
- [Oso: 10 RBAC Best Practices (2025)](https://www.osohq.com/learn/rbac-best-practices)
- [Budibase: Role-Based Access Control Ultimate Guide](https://budibase.com/blog/app-building/role-based-access-control/)
- [Constant Contact: UI Design Guidelines for User Roles](https://v2.developer.constantcontact.com/docs/user-roles/ui-design-guidelines-user-roles.html)
- [Material Design: Permissions Patterns](https://m1.material.io/patterns/permissions.html)
- [Akis Apostoliadis: User Rights Management UX/UI Case Study (Medium)](https://medium.com/anothercircus/user-rights-management-redlink-ux-ui-case-study-part-i-8206885208b2)
- [TheStory: Custom Error Page Design (400, 403, 404, 500, 503)](https://thestory.is/en/journal/custom-error-page-design/)
