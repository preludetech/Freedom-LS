# Research: Common Complaints and Pain Points with LMS Permission Systems

Date: 2026-02-27

## 1. Common Complaints About LMS Permission Systems

### Overwhelming Complexity

The most universal complaint across LMS platforms is that permission systems are too complex for the people who need to use them. Moodle, for example, has over 350 individual capabilities that an administrator can configure per role. Administrators report resorting to "ticking every capability in desperation" when they cannot figure out the correct combination needed for a specific use case.

Sources:
- [Managing roles - MoodleDocs](https://docs.moodle.org/501/en/Managing_roles)
- [Best practices: Customizing permissions in Moodle](https://www.openlms.net/blog/products/best-practices-customizing-permissions-enhance-courses-moodle/)

### Poor Discoverability of What Permissions Do

Educators and admins frequently cannot predict the effect of enabling or disabling a permission. In Moodle, multiple capabilities may need to be enabled for a single user-facing feature to work (e.g., forum posting requires both the posting capability AND the "Access all Groups" capability). The interaction effects between permissions are not obvious and often require trial-and-error or forum searches to resolve.

Sources:
- [Moodle Forums: Students can't reply to forum](https://moodle.org/mod/forum/discuss.php?d=187354)
- [Moodle Forums: Students can't post to forum](https://moodle.org/mod/forum/discuss.php?d=137219)

### Delayed Permission Propagation

In Canvas LMS, permission changes can take 30 minutes or longer to take effect. Administrators making changes cannot immediately verify whether their configuration is correct, leading to confusion about whether the permission was set correctly or simply has not propagated yet.

Source:
- [How do I set permissions for an account-level role - Instructure Community](https://community.canvaslms.com/t5/Admin-Guide/How-do-I-set-permissions-for-an-account-level-role/ta-p/213)

### Hidden and Uncontrollable Privileges

Blackboard has "hidden" privileges that always remain active regardless of UI settings. Custom course roles copied from base roles (instructor, TA, grader) retain certain privileges even when all privileges are removed via the UI. For example, a custom role copied from instructor/TA/grader always has full gradebook access, and a role copied from instructor/TA always gets forum manager privileges in new forums. Administrators cannot override these hidden behaviours.

Source:
- [Course and Organization Roles - Blackboard Help](https://help.blackboard.com/Learn/Administrator/SaaS/User_Management/Roles_and_Privileges/Course_and_Organization_Roles)

### Third-Party Tool Incompatibility with Custom Roles

In Blackboard, certain roles (Course Builders, Graders) cannot use third-party integrations like Turnitin. Users receive cryptic errors about their role when attempting to create assignments through these tools. The permissions appear correct from the admin's perspective, but the integration layer has its own role expectations that do not align with the platform's role system.

Source:
- [Course and Organization Roles - Blackboard Help](https://help.blackboard.com/Learn/Administrator/SaaS/User_Management/Roles_and_Privileges/Course_and_Organization_Roles)

---

## 2. What Frustrates Educators and Admins About Managing Permissions

### The TA/Assistant Problem

Teaching assistants commonly need to perform grading tasks but lack the necessary permissions. Granting them a broader role (like instructor) gives them too much access, but the available intermediate roles do not include the specific permissions needed. This is a recurring theme across Moodle, Canvas, and Blackboard. Administrators end up creating one-off custom roles to bridge the gap, which then need to be maintained.

Sources:
- [Moodle Forums: Assignments, Groups & Teaching Assistants](https://moodle.org/mod/forum/discuss.php?d=447381)
- [How do I edit Gradebook permissions for Teaching Assistants - UVACollab](https://collab-help.its.virginia.edu/m/assessments/l/1028458-how-do-i-edit-gradebook-permissions-for-teaching-assistants)

### Delegating Administration Is Dangerous

In Moodle, some administrators report being hesitant to allow teachers to override permissions because "capabilities cannot be restricted, and staff may inadvertently override capabilities they don't understand and open areas that students should not have access to." The system gives all-or-nothing delegation: either teachers can modify permissions (with the risk of misconfiguration) or they cannot (creating bottlenecks at the admin level).

Source:
- [Forum permissions - MoodleDocs](https://docs.moodle.org/19/en/Forum_permissions)

### The Manager Role Problem

In Moodle, the default Manager role grants access to the entire Site Administration menu, including Security, Server, and Plugins settings. Some administrators report never assigning the Manager role to anyone because there is no clean way to restrict it to just course/user management without also granting infrastructure-level access.

Source:
- [Moodle Forums: How to restrict Manager role from access to full Site Admin menu](https://moodle.org/mod/forum/discuss.php?d=262319)

### Sub-Account Permissions in Canvas

Canvas sub-account administration is a documented "point of frustration." Because all user accounts exist at the root account level, sub-account admins are limited in what they can actually do. A sub-account admin with "View All Users" and "Modify Login Details" permissions enabled may still be unable to exercise those permissions because the users technically belong to the root account. This architectural mismatch means permissions appear to be granted but do not function as expected.

Sources:
- [Sub-account admins being denied permissions - Instructure Community](https://community.canvaslms.com/t5/Canvas-Question-Forum/Prevent-sub-account-admins-from-acting-as-specific-user-top/m-p/589150)
- [Sub-Account Admins and "Start a New Course" Permission](https://community.canvaslms.com/t5/Canvas-Question-Forum/Sub-Account-Admins-and-quot-Start-a-New-Course-quot-Permission/m-p/523590)

### Simple Tasks Require Admin Intervention

Teachers commonly need "read-only forums" in Moodle but cannot configure this themselves. The permission override required is considered too complex for teachers, and administrators hesitate to grant override capabilities. This creates a bottleneck where simple pedagogical decisions require admin involvement. If many teachers need custom configurations, the admin workload becomes unmanageable -- "you would need an army of administrators."

Source:
- [Forum permissions - MoodleDocs](https://docs.moodle.org/19/en/Forum_permissions)

---

## 3. Too Simple vs Too Complex: What Goes Wrong

### When Permissions Are Too Simple

- **Cannot model real organizational structures.** A system with only "admin," "teacher," and "student" roles cannot accommodate TAs, course designers, department heads, external examiners, or auditors.
- **Forced over-privileging.** When the available roles do not match needs, administrators are forced to assign a role with more access than necessary (e.g., making a TA an instructor) because there is no intermediate option.
- **Cannot scale.** As organizations grow or start offering training to external learners, basic permission structures break down. Users who should have different access levels all get the same role.
- **No delegation path.** Simple systems typically have a single admin role, creating a bottleneck for all configuration tasks.

Source:
- [5 top challenges LMS administrators face - Absorb LMS](https://www.absorblms.com/blog/lms-administrator-challenges)
- [Managing Users and Permissions in Enterprise LMS](https://www.thelearningos.com/enterprise-knowledge/managing-users-and-permissions-in-enterprise-lms)

### When Permissions Are Too Complex

- **Role explosion.** Excessive granularity leads to an unmanageable number of roles. Each department or use case gets its own custom role, and the system becomes impossible to audit or understand. This is formally known as the "role explosion" problem in RBAC literature.
- **Configuration paralysis.** With 350+ individual capabilities (Moodle), administrators cannot confidently make changes. The interaction effects between capabilities are unpredictable.
- **Context/inheritance confusion.** Moodle's context system (system > category > course > activity) means permissions at different levels can conflict. A "Prohibit" at the system level overrides "Allow" at the course level, but other settings flow differently. This creates confusing debugging scenarios.
- **Maintenance burden.** Complex permission systems require ongoing maintenance. When new features are added, each existing custom role needs to be evaluated for whether it should include the new capabilities.
- **Training cost.** New administrators need significant training before they can safely manage permissions, and mistakes can expose sensitive data.

Source:
- [Role-Based Access Control in LMS: A Comprehensive Guide](https://www.thelearningos.com/enterprise-knowledge/role-based-access-control-in-lms-a-comprehensive-guide)
- [Roles FAQ - MoodleDocs](https://docs.moodle.org/22/en/Roles_FAQ)

---

## 4. Security Incidents and Data Exposure from Poor Permission Design

### Documented Incidents

- **UK college data leak:** A college experienced a cross-tenant data leak where one student's final exam results appeared in another school's portal, resulting in approximately GBP 120,000 in legal fees. The root cause was missing tenant ID enforcement in database queries.
- **Scottish college ICO fine:** A Scottish college was fined GBP 85,000 by the Information Commissioner's Office after an administrator accidentally exported data containing multiple schools' staff and student information. The system did not enforce tenant boundaries on bulk export operations.
- **URL-based access vulnerability:** Multiple reports of users being able to access other tenants' data by manipulating URLs, indicating that authorization checks were happening at the UI level but not at the data access level.

Source:
- [Multi-Tenancy Considerations for LMS Implementations](https://midlandsinbusiness.com/multi-tenancy-considerations-for-lms-implementations)

### Systemic Security Risks

- **Weak access control as a breach vector:** Approximately 63% of educational institutions using LMS faced at least one security breach in 2022 (Cybersecurity Insiders). Weak access control mechanisms, including insufficient RBAC and overly permissive roles, are identified as contributing factors.
- **Offboarding failures:** Delayed or incomplete offboarding of users leaves accounts with elevated permissions active after people have left the organization. Former staff retaining access to student data is both a security and compliance risk.
- **Over-privileged defaults:** Systems that grant broad access by default (rather than following least-privilege principles) create standing risk. Users accumulate permissions over time but rarely have them revoked.

Sources:
- [LMS Security: Problems and Solutions - eLearning Industry](https://elearningindustry.com/lms-security-problems-solutions)
- [LMS Cybersecurity: 3 Serious Risks - Talented Learning](https://talentedlearning.com/lms-cybersecurity-3-serious-risks-how-to-avoid-them/)
- [Managing User Roles and Permissions in Your LMS - eLearning Industry](https://elearningindustry.com/best-practices-for-managing-user-roles-and-permissions-in-your-lms)

---

## 5. What LMS Admins Wish Was Different

### Clear, Predictable Permission Effects

Admins want to understand what enabling a permission actually does in practice, without needing to test every scenario. The current state in complex systems like Moodle requires a debugging script (rolesdebug.php) to understand the effective permissions in a given context.

### Sensible Defaults with Easy Customization

Admins want pre-built roles that cover common use cases (teacher, TA, course designer, department head) that work out of the box, with the ability to make targeted adjustments without understanding hundreds of individual capabilities.

### Safe Delegation

Admins want to delegate specific administrative tasks (e.g., enrolling students, managing a cohort) without granting broad system access. The current all-or-nothing approach to delegation forces admins to choose between doing everything themselves or granting too much access.

### Bulk Operations That Respect Boundaries

The ability to make bulk changes (enrolling users, updating roles, exporting data) that automatically respect organizational boundaries (departments, cohorts, tenants) rather than requiring manual filtering.

### Audit and Visibility

The ability to quickly answer "who has access to what?" and "what changed and when?" Current systems often lack clear audit trails for permission changes, making it difficult to investigate issues or demonstrate compliance.

Sources:
- [Panopto Community: LMS Permissions Improvements](https://community.panopto.com/discussion/2504/lms-permissions-improvements-june-2025)
- [LMS Administrator Guide - iSpring](https://www.ispringsolutions.com/blog/lms-administrator)

---

## 6. Challenges Specific to Multi-Tenant LMS Platforms

### Data Isolation

The fundamental challenge is ensuring that one tenant's data is never visible to another tenant. This requires tenant-aware filtering at the database query level, not just the UI level. A single missing `WHERE tenant_id = ?` clause becomes a data leak.

Three architectural approaches exist, each with trade-offs:
1. **Shared database, shared schema** (tag records with tenant ID) -- most resource-efficient but highest risk of data leaks
2. **Shared database, separate schemas** -- better isolation but more complex schema management
3. **Separate databases per tenant** -- highest isolation but highest resource cost

### Permission Boundaries vs Tenant Boundaries

Traditional identity and access management tools focus on application-level permissions rather than tenant-specific boundaries within applications. An admin in one tenant should have full admin access within their tenant but zero access to other tenants. Support staff may need cross-tenant access but only for specific operations. Modelling these overlapping boundary types in a single permission system is architecturally challenging.

### Customization Without Contamination

Each tenant may need different role definitions, permission configurations, grading scales, and branding. Changes for one tenant must not affect others. Feature deployments and migrations must be tenant-aware.

### Performance Isolation

Heavy operations by one tenant (large exports, bulk enrollments, report generation) can degrade service for other tenants. Permission-related operations like "list all users I can manage" become expensive queries when tenant filtering is complex.

### Compliance Across Jurisdictions

Different tenants may operate under different regulatory frameworks (GDPR, FERPA, HIPAA, national data protection laws). The permission system must be flexible enough to enforce different compliance requirements per tenant.

Source:
- [Multi-Tenancy Considerations for LMS Implementations](https://midlandsinbusiness.com/multi-tenancy-considerations-for-lms-implementations)
- [Multi-Tenant Security: Definition, Risks and Best Practices](https://qrvey.com/blog/multi-tenant-security/)
- [Multi-Tenant LMS Guide 2026 - ProProfs](https://www.proprofstraining.com/blog/multi-tenant-lms/)

---

## Key Takeaways for FLS Permission System Design

1. **Find the right granularity.** Too few roles forces over-privileging; too many capabilities creates configuration paralysis. Aim for a small number of well-defined roles with clear, predictable behaviours rather than hundreds of individual toggles.

2. **Make permissions predictable.** Every permission should have a clear, observable effect. Avoid context inheritance hierarchies that create surprising override behaviours.

3. **Support safe delegation.** Educators should be able to manage their own courses and cohorts without needing system-wide admin access. The permission system should make it easy to delegate specific responsibilities.

4. **Enforce tenant boundaries at the data layer.** In a multi-site system, site filtering must be enforced at the query level (which FLS already does via site-aware models), not just at the view level.

5. **Provide sensible defaults.** Pre-built roles for common use cases should work correctly out of the box. Customization should be additive rather than requiring users to understand the entire permission matrix.

6. **Avoid hidden or implicit permissions.** All effective permissions should be visible and configurable. Avoid Blackboard's pattern of hidden privileges that cannot be controlled.

7. **Support the TA/assistant use case natively.** This is the most common "role gap" reported across all platforms. A system that cleanly handles the "can grade but cannot edit course structure" use case will avoid a major category of complaints.

8. **Make bulk operations safe.** Export, enrollment, and role assignment operations should automatically respect organizational boundaries.

9. **Provide clear audit capabilities.** Admins need to quickly determine who has access to what and how that access was granted.

10. **Ensure permission changes take effect immediately.** Delayed propagation (Canvas's 30-minute delay) creates confusion and prevents administrators from verifying their changes.
