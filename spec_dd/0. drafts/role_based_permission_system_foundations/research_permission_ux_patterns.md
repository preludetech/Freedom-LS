# Research: Permission Management UX Patterns for Education Platforms

## 1. Common UX Patterns for Assigning Roles and Permissions

### 1.1 Role-Based Dropdowns

The simplest and most widely used pattern. A user is assigned a single role from a dropdown (e.g., "Teacher", "TA", "Observer"). This is the primary pattern used by Canvas LMS, where each user gets one of five base course-level roles: Student, Teacher, TA, Designer, or Observer.

**When to use:** When roles are few, well-defined, and mutually exclusive. Works well for education contexts where "Educator", "Admin", and "Observer" cover most needs.

**Strengths:**
- Instantly understandable by non-technical users
- Fast to assign --- single click
- Minimal room for misconfiguration

**Weaknesses:**
- Cannot express "Educator X has full access to Cohort A but read-only access to Cohort B"
- Forces creation of many micro-roles if granularity is needed

### 1.2 Permission Matrices

A grid where rows are permissions/actions and columns are roles. Each cell is a checkbox or toggle. Canvas LMS uses this pattern in its admin interface: admins can see a full matrix of what each role can do and toggle individual permissions on/off.

**When to use:** When admins need to create custom roles or fine-tune what a predefined role can do. Useful as an advanced/admin-only view.

**Strengths:**
- Complete visibility into what each role allows
- Supports custom role creation
- Good for audit and compliance review

**Weaknesses:**
- Overwhelming for non-technical users --- a matrix with 50+ permissions across 5 roles creates cognitive overload
- Easy to make mistakes (one wrong checkbox can open a security hole)
- Moodle is often criticised for having an overly complex permission matrix that intimidates educators

### 1.3 Group-Based Assignment

Users are placed into groups, and groups are granted access to resources. For example, an "English Department" group gets access to all English cohorts. Salesforce uses "Permission Set Groups" that bundle multiple permission sets into one assignable unit.

**When to use:** When organisational structure maps cleanly to access needs. Ideal for schools with departments, year groups, or programme teams.

**Strengths:**
- Scales well --- adding a new educator to a department automatically grants appropriate access
- Reduces repetitive per-user configuration
- Maps to how educators already think about their teams

**Weaknesses:**
- Requires upfront organisational modelling
- Can become confusing if a user belongs to many overlapping groups

### 1.4 Resource-Scoped Role Assignment (Recommended for FLS)

A hybrid pattern: assign a user a role *in the context of a specific resource*. For example, "Sarah is an Educator for Cohort A" and "Sarah is an Observer for Cohort B." Canvas uses this at both course and account levels.

**When to use:** When the same user needs different access levels for different cohorts or courses. This is the most flexible pattern for an LMS.

**Strengths:**
- Precise control without role explosion
- Intuitive mental model: "Who can do what, where?"
- Matches how education actually works (an educator may teach one cohort and mentor another)

**Weaknesses:**
- More assignments to manage (mitigated by bulk assignment, see Section 6)

## 2. How Major Platforms Handle Permission Management

### 2.1 Google Workspace

- Uses a **tiered admin role** system: Super Admin, Groups Admin, User Management Admin, Help Desk Admin, and custom roles
- Admins assign roles from a simple dropdown on the user's profile page
- Custom roles are created by selecting from a categorised list of privileges (grouped by product: Gmail, Drive, Calendar, etc.)
- Key pattern: **Role descriptions in plain language** --- each role shows a one-line summary of what it grants
- Non-technical admins rarely need to create custom roles; the predefined ones cover most cases

### 2.2 Slack

- Four-tier hierarchy: Primary Owner > Workspace Owners > Workspace Admins > Members/Guests
- Channel-level permissions are separate from workspace-level roles
- Permissions are managed through a **settings panel** with toggle switches, not a matrix
- Key pattern: **Sensible defaults with opt-in granularity** --- most workspaces never touch default permissions
- Guest accounts (single-channel and multi-channel) are a distinct concept, not a role with reduced permissions

### 2.3 GitHub

- Repository-level roles: Read, Triage, Write, Maintain, Admin
- Organisation-level roles: Member, Owner, Billing Manager
- Teams act as groups for bulk repository access
- Key pattern: **Role names describe capability level**, not job title. "Write" is clearer than "Contributor" for understanding what someone can do
- "Effective permissions" are visible on a per-repository basis, showing exactly what a user can do and why

### 2.4 Canvas LMS

- Five base course roles: Student, Teacher, TA, Designer, Observer
- Account-level admin roles with full permission matrix customisation
- Key pattern: **Base roles with optional customisation** --- institutions start with sensible defaults and only customise when they have a specific need
- Custom roles are created by cloning a base role and modifying specific permissions
- Permissions cascade down through account hierarchies
- Pain point: Permission changes can take 30+ minutes to propagate, creating confusion

### 2.5 Moodle

- Extremely granular permission system with hundreds of individual capabilities
- Roles can be assigned at system, category, course, and activity levels
- Key pattern: **Context-scoped role assignment** (a user can have different roles at different levels)
- Common complaint: The granularity is overwhelming. Most Moodle administrators use default roles and avoid customisation because the permission matrix is too complex

## 3. Best Practices for Non-Technical Educators

### 3.1 Use Plain Language, Not Technical Jargon

- "Can view student progress" instead of "READ permission on student_progress entity"
- "Can edit course content" instead of "WRITE access to content_engine objects"
- Group permissions by *what educators actually do*: "Teaching", "Grading", "Administration" --- not by database table or API endpoint
- Perpetual NY recommends "plain language role descriptions to eliminate ambiguity around permissions"

### 3.2 Provide Sensible Defaults That Require Minimal Configuration

- A newly created "Educator" should immediately be able to do everything a typical educator needs
- Only require configuration for *exceptions* to the default
- Canvas succeeds here: the "Teacher" role works out of the box for 95% of instructors
- Slack succeeds here: default permissions work for most teams without any configuration

### 3.3 Show the Effect of Changes Before They Are Applied

- When an admin changes a role or permission, show a summary: "This will allow Sarah to view grades for 45 students in Cohort B"
- Preview what the user will see after the change
- This is the "effective permissions" pattern used by GitHub and Azure DevOps

### 3.4 Make "Who Has Access" Visible from Both Directions

Two complementary views:
1. **User-centric:** Select a user, see everything they can access ("Sarah can access Cohort A as Educator, Cohort B as Observer")
2. **Resource-centric:** Select a cohort, see everyone who can access it ("Cohort A: Sarah (Educator), James (Observer), Admin Team (Admin)")

Both views are essential. Without them, the answer to "who can see this student's data?" requires mental assembly of multiple screens.

### 3.5 Use Progressive Disclosure

- Show simple role assignment by default (dropdown: Educator / Observer / Admin)
- Hide granular permission editing behind an "Advanced" or "Customise" link
- Most educators will never need the advanced view
- This avoids the Moodle problem of presenting hundreds of checkboxes to someone who just wants to add a co-teacher

### 3.6 Provide Contextual Help

- Next to each role name, show a brief description of what it includes
- Use tooltips or expandable sections, not separate documentation pages
- Example: "Educator --- Can view and manage students, track progress, and update content for assigned cohorts"

## 4. Common UX Mistakes in Permission Management

### 4.1 Too Much Granularity Upfront

Moodle's permission system has hundreds of individual capabilities. Most administrators never customise them because the interface is overwhelming. The result: everyone uses defaults, and the granularity serves no practical purpose.

**Fix:** Start with roles. Only expose individual permissions in an advanced view. Design so that 90% of users never need to go beyond role assignment.

### 4.2 Confusing Terminology

Using terms like "RBAC", "ACL", "principal", "subject", or "capability" in the UI. Educators do not think in these terms.

**Fix:** Use action-oriented language: "Can view", "Can edit", "Can manage". Use resource names educators recognise: "cohorts", "students", "courses" --- not "entities" or "objects".

### 4.3 No Visibility into Effective Permissions

The most common complaint across all platforms: "I changed a permission but I can't tell what the user can actually do now." When permissions come from multiple sources (role + group + per-resource override), it becomes impossible to reason about the end result without a summary view.

**Fix:** Provide an "Effective Permissions" view that resolves all sources and shows the final result. GitHub does this well on repository settings pages. Azure DevOps provides a dedicated "Effective Permissions" tab per user.

### 4.4 No Feedback on Permission Changes

Changing a permission and seeing no confirmation, no summary of impact, and no indication of when it takes effect. Canvas permissions can take 30+ minutes to propagate, and the UI does not communicate this.

**Fix:** Immediate feedback. Show what changed, who is affected, and when it takes effect. If there is a delay, communicate it explicitly.

### 4.5 All-or-Nothing Access

Systems that only offer "Admin" and "User" with no middle ground. This forces organisations to either over-provision (giving everyone admin access) or under-provision (blocking educators from tools they need).

**Fix:** Provide at least three tiers: a full admin, a functional role for educators/managers, and a basic user role. For an LMS: Admin, Educator, Observer (read-only).

### 4.6 Hiding Who Has Access

Many systems let you assign permissions but provide no easy way to audit them. The question "who can see this student's data?" should be answerable in one click, not by examining each user's profile individually.

**Fix:** Resource-centric access lists (see Section 3.4).

### 4.7 Irreversible or Hard-to-Undo Changes

Removing a user from a role and losing all their per-resource assignments, with no way to restore them.

**Fix:** Confirmation dialogs for destructive permission changes. Consider soft-revocation (disable access but preserve the assignment record for easy restoration).

## 5. Handling "Who Can See What" Clearly in a UI

### 5.1 The Two-View Pattern

Provide two complementary entry points:

**From a User Profile:**
```
Sarah Johnson --- Educator
├── Cohort: Introduction to Python (Educator) --- Can view students, track progress, manage content
├── Cohort: Advanced Data Science (Observer) --- Can view students and progress (read-only)
└── Cohort: Web Development 101 (Educator) --- Can view students, track progress, manage content
```

**From a Cohort/Resource Page:**
```
Cohort: Introduction to Python
├── Sarah Johnson --- Educator
├── James Smith --- Educator
├── Admin Team --- Admin (via group)
└── Dr. Williams --- Observer
```

### 5.2 Effective Permission Summary

When displaying a user's access, resolve all permission sources and show the final result:

```
Sarah Johnson's access to "Introduction to Python"
  Role: Educator
  Source: Direct assignment

  Effective permissions:
  [check] View enrolled students
  [check] View student progress
  [check] Edit course content
  [check] Send announcements
  [x] Manage other educators    (requires Admin role)
  [x] Delete the cohort          (requires Admin role)
```

### 5.3 Inline Permission Indicators

On lists and tables, show permission level inline rather than requiring navigation to a separate page:

```
My Cohorts
| Cohort                    | Your Role  | Students |
|---------------------------|------------|----------|
| Introduction to Python    | Educator   | 32       |
| Advanced Data Science     | Observer   | 18       |
```

### 5.4 Visual Differentiation

Use distinct visual treatments for different access levels:
- Full access (Educator): standard/default appearance
- Read-only (Observer): muted colours or a visible "read-only" badge
- Admin: subtle admin indicator (not alarming, just informative)

This makes it immediately apparent *how* you are interacting with a resource, reducing "can I edit this?" confusion.

## 6. Recommended Patterns for Bulk Permission Assignment

### 6.1 Multi-Select with Action Bar

The most intuitive bulk pattern for web applications:

1. Show a list of cohorts (or users) with checkboxes
2. User selects multiple items
3. An action bar appears: "Assign Role" dropdown + "Apply" button
4. Confirmation shows exactly what will change

```
Select cohorts to assign Sarah Johnson:
[x] Introduction to Python
[x] Web Development 101
[ ] Advanced Data Science
[ ] Machine Learning Fundamentals

[Assign as: Educator v] [Apply to 2 cohorts]
```

### 6.2 Invite/Add Multiple Users to a Resource

From a cohort's settings page, allow adding multiple educators at once:

1. Type-ahead search for users (by name or email)
2. Selected users appear as chips/tags
3. Choose a role for all selected users (with option to customise per-user)
4. Submit with a confirmation summary

Google Workspace and Slack both use this pattern for adding members to groups/channels. Loomio's UX research found this pattern works well for both single and bulk additions (1 to 100 users).

### 6.3 Group-Based Assignment

Create named groups ("English Department", "Year 1 Tutors") and assign entire groups to cohorts:

- Adding a new educator to the group automatically grants them access to all the group's cohorts
- Removing them from the group revokes access
- Changes are immediate and predictable

Salesforce Permission Set Groups demonstrate this pattern at scale: bundle permissions into a group, assign the group to users, and any changes to the group propagate to all members.

### 6.4 Copy Permissions from Another User

When onboarding a new educator who should have the same access as an existing one:

1. Select the new user
2. Choose "Copy access from..." and select the source user
3. Review the proposed assignments
4. Confirm

This is faster than manually recreating assignments and reduces errors.

### 6.5 Bulk Import/CSV Upload (Advanced)

For large institutions onboarding many educators:

- Upload a CSV with columns: email, cohort, role
- System validates and previews changes before applying
- Error rows are highlighted for correction

This is an advanced feature that should not be the primary workflow, but is valuable for institutions managing hundreds of educators.

## 7. Recommendations for FLS Implementation

Based on this research, the following patterns are most suitable for the Freedom Learning System:

### Start Simple
1. **Three predefined roles:** Admin, Educator, Observer
2. **Resource-scoped assignment:** Assign a user a role in the context of a specific cohort
3. **Role dropdown on cohort settings page:** The simplest possible interface for the most common task

### Provide Visibility
4. **User access summary:** A page showing everything a user can access and their role for each
5. **Cohort access list:** On each cohort's page, show who has access and their roles
6. **Inline role badges:** Show role information on cohort lists and user lists

### Enable Bulk Operations
7. **Multi-select cohort assignment:** When managing a user, select multiple cohorts at once
8. **Multi-select user assignment:** When managing a cohort, add multiple educators at once

### Keep It Extensible
9. **Design the data model to support custom roles later**, but do not expose custom role creation in the initial UI
10. **Design the data model to support groups later**, but start with direct user-to-cohort assignment

### Avoid Common Mistakes
11. **No permission matrix in the default UI** --- only in an admin-only advanced section if ever needed
12. **Plain language throughout** --- "Can view students" not "READ student_management"
13. **Immediate feedback** on all permission changes
14. **Confirmation for destructive changes** (removing access)

## Sources

- [How to Design a Permissions Framework -- Rina Artstain](https://rinaarts.com/how-to-design-a-permissions-framework/)
- [How to Improve Your Permissions UX -- Adam Lynch](https://adamlynch.com/improve-permissions-ux/)
- [Best Practices for Managing User Roles and Permissions in Your LMS -- eLearning Industry](https://elearningindustry.com/best-practices-for-managing-user-roles-and-permissions-in-your-lms)
- [How to Design Effective SaaS Roles and Permissions -- Perpetual NY](https://www.perpetualny.com/blog/how-to-design-effective-saas-roles-and-permissions)
- [Best Practices for Effective User Permissions and Access Delegation -- Permit.io](https://www.permit.io/blog/best-practices-for-effective-user-permissions-and-access-delegation)
- [What User Roles and Permissions Are Available in Canvas? -- Instructure Community](https://community.instructure.com/t5/Admin-Guide/What-user-roles-and-permissions-are-available-in-Canvas/ta-p/102)
- [Canvas Course Role Permissions -- Cornell Learning Technologies](https://learn.canvas.cornell.edu/canvas-course-role-permissions/)
- [LMS User Roles: Responsibilities of Administrators, Instructors, and Learners -- Teachfloor](https://www.teachfloor.com/blog/lms-user-roles)
- [Types of Roles in Slack -- Slack Help](https://slack.com/help/articles/360018112273-Types-of-roles-in-Slack)
- [Permissions by Role in Slack -- Slack Help](https://slack.com/help/articles/201314026-Permissions-by-role-in-Slack)
- [Introducing Permission Set Groups -- Salesforce Admins](https://admin.salesforce.com/blog/2019/introducing-the-next-generation-of-user-management-permission-set-groups)
- [Case Study: Designing a Better Experience for Permissions -- Wix UX](https://wix-ux.com/case-study-designing-a-better-experience-for-permissions-9cda05ecc8e7)
- [Case Study: Designing Roles and Permissions -- Sukanya Sen / Bootcamp](https://medium.com/design-bootcamp/designing-roles-and-permissions-ux-case-study-b1940f5a9aa)
- [Mastering User Management and Permissions in Your Enterprise LMS -- TheLearningOS](https://www.thelearningos.com/enterprise-knowledge/mastering-user-management-and-permissions-in-your-enterprise)
- [How to Manage User Roles in Your LMS -- LearnUpon](https://www.learnupon.com/blog/manage-user-roles-lms/)
- [Managing Roles and Permissions User Flow Examples -- NicelyDone](https://nicelydone.club/flows/manage-roles-and-permissions)
- [Best Practice for Designing User Roles and Permission System -- Aalpha](https://www.aalpha.net/blog/best-practice-for-designing-user-roles-and-permission-system/)
- [Access Control Matrix: Key Components and Best Practices -- Frontegg](https://frontegg.com/blog/access-control-matrix)
- [View Permissions and Effective Access -- Azure DevOps / Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/organizations/security/view-permissions?view=azure-devops)
