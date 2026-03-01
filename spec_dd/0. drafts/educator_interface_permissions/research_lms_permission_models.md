# Research: LMS Permission Models for Educator Interface

## 1. Permission Models in Popular LMS Platforms

### 1.1 Moodle

Moodle uses a **capability-based RBAC (Role-Based Access Control)** system with contextual scoping. It is the most granular and flexible of the major platforms.

**Core concepts:**

- **Capabilities**: Over 350 individual permissions describing specific features (e.g., `mod/forum:replypost`, `moodle/course:update`).
- **Roles**: Named collections of capabilities. Each capability within a role has one of four permission states: Allow, Prevent, Prohibit, or Not Set (Inherit).
- **Contexts**: Hierarchical scopes where roles are assigned. The context hierarchy is: System > Category > Course > Module > Block. Permissions cascade downward -- a role assigned at the course level applies to all modules within that course.

**Permission resolution**: Lower contexts override higher contexts, except for "Prohibit" which cannot be overridden at any lower level.

**Default roles**: Manager, Course Creator, Teacher, Non-editing Teacher, Student, Guest, Authenticated User.

Key insight: The Non-editing Teacher role is widely used for teaching assistants who need to view grades and student work but should not modify course content. The Manager role gives administrative power across courses without full site-admin access.

References:
- [Roles and permissions - MoodleDocs](https://docs.moodle.org/501/en/Roles_and_permissions)
- [Managing roles - MoodleDocs](https://docs.moodle.org/501/en/Managing_roles)
- [Roles (Developer) - MoodleDocs](https://docs.moodle.org/dev/Roles)

### 1.2 Canvas (by Instructure)

Canvas uses a **two-tier role system** with account-level and course-level roles.

**Account-level roles**: Control institution-wide administrative features. Account admins can create custom account-level roles.

**Course-level roles**: Control what a user can do within a specific course. Canvas has five base course-level roles:

| Role | Purpose |
|------|---------|
| **Teacher** | Full course admin: grades, content, enrollment management |
| **TA (Teaching Assistant)** | Similar to Teacher but without SIS data access; permissions configurable per institution |
| **Designer** | Content creation (announcements, assignments, discussions, quizzes) but no access to grades |
| **Student** | Submits work, views content, participates in discussions |
| **Observer** | Read-only view of a linked student's experience (commonly used by parents or advisors) |

**Granularity**: Each permission is a boolean toggle per role. Admins can create custom course-level roles derived from the five base types. Permissions cascade through the account hierarchy -- sub-accounts inherit from parent accounts. A user can hold different roles in different courses simultaneously.

**Permission categories** in Canvas include: course content, grades, people, discussions, announcements, assignments, quizzes, files, and more. Each base role type has different default permission states, and institutions can customize these.

References:
- [What user roles and permissions are available in Canvas?](https://community.canvaslms.com/t5/Admin-Guide/What-user-roles-and-permissions-are-available-in-Canvas/ta-p/102)
- [Roles - Canvas LMS REST API](https://canvas.instructure.com/doc/api/roles.html)
- [List of Permissions - Instructure Developer Docs](https://developerdocs.instructure.com/services/canvas/permissions/file.permissions)

### 1.3 Blackboard Learn

Blackboard uses a **privilege-based role system** with separate system-level and course-level roles.

**System-level roles**: Control access to the Administrator Panel and institution-wide features.

**Course-level roles**: Control access within individual courses. Key roles:

| Role | Capabilities |
|------|-------------|
| **Instructor** | Full control panel access, grades, content, enrollment |
| **Teaching Assistant** | Nearly identical to Instructor but cannot remove users from courses |
| **Course Builder** | Content creation and management, no grading access |
| **Grader** | Grade management only, limited content access |
| **Student** | Standard learner access |
| **Guest** | Minimal, read-only access |

**Design philosophy**: Blackboard explicitly separates *course design privileges* from *teaching privileges*. This separation is important for institutions with strict role boundaries between faculty, instructional designers, and support staff.

**File permissions**: Instructor, TA, and Course Builder roles get read, write, remove, and manage permissions on course files by default. Students and Guests get read-only access.

References:
- [Course Roles - Blackboard Help](https://help.blackboard.com/Learn/Instructor/Ultra/Courses/Course_Roles)
- [Roles and Privileges - Blackboard Help](https://help.blackboard.com/Learn/Administrator/SaaS/User_Management/Roles_and_Privileges)
- [Course and Organization Roles - Blackboard Help](https://help.blackboard.com/Learn/Administrator/SaaS/User_Management/Roles_and_Privileges/Course_and_Organization_Roles)

### 1.4 Open edX

Open edX uses a **simpler role hierarchy** with inheritance, implemented directly in Django.

**Roles** (from the `student/roles.py` module):

| Role | Scope | Capabilities |
|------|-------|-------------|
| **Global Staff** | Site-wide | Full access to all courses, Studio, and admin |
| **Course Instructor (Admin)** | Per course | All Staff capabilities + manage course team roles, modify grades, add/remove beta testers, manage discussion moderation |
| **Course Staff** | Per course | Access Instructor Dashboard and Studio for that course only |
| **Limited Staff** | Per course | All Staff tasks except content editing; no Studio access |
| **Beta Tester** | Per course | Preview unreleased content |
| **Discussion Moderator** | Per course | Moderate discussion forums |

**Implementation**: Roles have a `ROLE` attribute and an optional `BASE_ROLE` for inheritance. The role check is typically a simple lookup -- does user X have role Y for course Z? This is closer to how django-guardian works than Moodle's capability system.

References:
- [Guide to Course Team Roles - Open edX Docs](https://docs.openedx.org/en/latest/educators/references/course_development/course_team_roles.html)
- [Roles and Permissions - EduNEXT Docs](https://public.docs.edunext.co/en/latest/external/course_creators/setup_course/roles_permissions.html)
- [roles.py source - GitHub](https://github.com/edx/edx-platform/blob/master/common/djangoapps/student/roles.py)


## 2. Common Roles Across LMS Platforms

Synthesizing the four platforms, these roles appear consistently:

| Common Role | Moodle Equivalent | Canvas Equivalent | Blackboard Equivalent | Open edX Equivalent |
|------------|-------------------|-------------------|-----------------------|--------------------|
| **Site Administrator** | Manager | Account Admin | System Administrator | Global Staff |
| **Course Creator** | Course Creator | (Account Admin) | (System Admin) | Global Staff |
| **Instructor / Teacher** | Teacher | Teacher | Instructor | Course Instructor |
| **Teaching Assistant** | Non-editing Teacher | TA | Teaching Assistant | Course Staff |
| **Content Designer** | (Teacher variant) | Designer | Course Builder | (Course Staff) |
| **Grader** | (Non-editing Teacher) | (TA variant) | Grader | (Course Staff) |
| **Student / Learner** | Student | Student | Student | Student |
| **Observer / Auditor** | Guest | Observer | Guest | (Audit track) |

**Key observations:**

1. Every platform distinguishes between *site-wide admin* and *course-level instructor*.
2. The TA / Non-editing Teacher role exists everywhere -- someone who can view student work and grades but has limited (or no) ability to modify course content.
3. The Designer / Course Builder role (content creation without grading) is present in Canvas and Blackboard but not standard in Moodle or Open edX.
4. The Observer role (read-only, often for parents or academic advisors) is a Canvas innovation that other platforms handle less formally.
5. Users commonly hold different roles in different courses simultaneously.


## 3. Granularity of Permissions

### 3.1 System-level (site-wide)

All platforms have some form of system-level permissions:
- Creating courses
- Managing users across the platform
- Configuring site settings
- Viewing analytics across all courses

### 3.2 Course-level

This is the most common permission scope across all platforms:
- Managing course content (create, edit, delete)
- Viewing and managing enrolled students
- Grading and viewing student progress
- Managing course settings
- Sending announcements

### 3.3 Sub-course level (cohort, module, activity)

This is where platforms diverge:
- **Moodle** is the most granular, allowing role assignment at the module/activity level within a course.
- **Canvas** operates primarily at the course level, with some section-level permissions.
- **Blackboard** operates at the course level with file-level permission overrides.
- **Open edX** operates at the course level with discussion-level moderation roles.

### 3.4 Relevance to FLS (Freedom Learning System)

Given that FLS uses cohorts as a key organizational unit (see the idea spec), **cohort-level permissions are essential**. The permission model should support:

- **System-level**: Who can create/manage cohorts, who can access the educator interface at all
- **Cohort-level**: Who can view/manage specific cohorts and the students within them
- **Course-level**: Who can view/manage progress for specific courses (especially relevant when a cohort studies multiple courses)

This maps closest to Moodle's contextual approach, but FLS should keep the hierarchy simpler:

```
System (site-wide)
  -> Cohort (who can see/manage which cohorts)
    -> Course (within a cohort, which courses can the educator interact with)
```


## 4. How django-guardian Fits LMS Permission Patterns

### 4.1 Overview

django-guardian is already installed and configured in FLS (`config/settings_base.py`). It provides per-object permissions on top of Django's built-in permission framework. It is listed in `INSTALLED_APPS` and its `ObjectPermissionBackend` is in `AUTHENTICATION_BACKENDS`.

### 4.2 Core API

```python
from guardian.shortcuts import assign_perm, remove_perm, get_perms, get_objects_for_user

# Assign permission on a specific object to a user
assign_perm('student_management.view_cohort', user, cohort_instance)

# Assign permission on a specific object to a group
assign_perm('student_management.view_cohort', educator_group, cohort_instance)

# Check permission
user.has_perm('student_management.view_cohort', cohort_instance)

# Get all objects a user has a specific permission on
viewable_cohorts = get_objects_for_user(user, 'student_management.view_cohort')
```

### 4.3 Mapping to LMS patterns

**Cohort-level permissions (primary use case for FLS)**:
- `view_cohort` -- can see the cohort and its student list
- `change_cohort` -- can modify cohort settings
- `manage_cohort_students` -- can add/remove students from the cohort (custom permission)
- `view_cohort_progress` -- can view student progress within the cohort (custom permission)

django-guardian handles this naturally. An educator is assigned permissions on specific cohort objects. When they access the educator interface, FLS queries `get_objects_for_user()` to determine which cohorts they can see.

**Group-based assignment**:
django-guardian supports assigning permissions to Django Groups, not just individual users. This enables role patterns like:

```python
# Create a group for lead educators
lead_educators = Group.objects.create(name='Lead Educators')

# Assign the group permission on a cohort
assign_perm('student_management.view_cohort', lead_educators, cohort)
assign_perm('student_management.change_cohort', lead_educators, cohort)

# Add a user to the group -- they inherit the permissions
user.groups.add(lead_educators)
```

### 4.4 Performance considerations

django-guardian stores permissions in database tables (`UserObjectPermission` and `GroupObjectPermission`). For listing views (e.g., "show all cohorts this educator can see"), use `get_objects_for_user()` which generates efficient SQL queries rather than checking permissions one object at a time.

For views that check permissions on multiple objects, use `ObjectPermissionChecker` to batch-prefetch permissions and avoid N+1 queries:

```python
from guardian.core import ObjectPermissionChecker

checker = ObjectPermissionChecker(user)
checker.prefetch_perms(cohort_queryset)
for cohort in cohort_queryset:
    if checker.has_perm('view_cohort', cohort):
        ...
```

References:
- [django-guardian documentation](https://django-guardian.readthedocs.io/)
- [Object Permissions - Assign](https://django-guardian.readthedocs.io/en/stable/userguide/assign/)
- [Performance guide](https://django-guardian.readthedocs.io/en/3.0.1/userguide/performance/)


## 5. Best Practices: Object-level vs Model-level Permissions in Django LMS Projects

### 5.1 Use model-level permissions for role gating

Model-level permissions (Django's built-in system) are best for coarse-grained access control:

- **Can this user access the educator interface at all?** Use a model-level permission or `is_staff` flag.
- **Can this user create new cohorts?** Model-level permission: `student_management.add_cohort`.
- **Can this user view any student progress?** Model-level permission on the progress model.

These permissions answer "can this type of user do this type of action?" without reference to a specific object.

### 5.2 Use object-level permissions for resource scoping

Object-level permissions (via django-guardian) are best for scoping access to specific resources:

- **Which cohorts can this educator see?** Object-level: `view_cohort` on each cohort instance.
- **Can this educator manage students in Cohort X?** Object-level: `manage_cohort_students` on Cohort X.

These permissions answer "can this specific user do this action on this specific object?"

### 5.3 Combine both layers

The recommended pattern is to use both layers together:

1. **Model-level** as a first gate: Does the user have the general capability?
2. **Object-level** as a second gate: Does the user have permission on this specific object?

Example flow for "view cohort progress":
```
1. Is user.is_staff? (basic educator interface access)
2. Does user have model-level 'view_cohort' permission? (can they view any cohort)
3. Does user have object-level 'view_cohort' on this specific cohort? (are they assigned to it)
```

### 5.4 Use Django Groups as roles

Rather than building a custom Role model, use Django's built-in `Group` model as the role mechanism. django-guardian supports group-based object permissions natively. This keeps the system simple and compatible with the Django ecosystem.

Suggested groups for FLS:

| Group | Purpose | Typical permissions |
|-------|---------|-------------------|
| **Educator Admin** | Full educator interface access, can manage all cohorts and assign other educators | Model-level: all educator permissions. Object-level: assigned per cohort as needed |
| **Educator** | Standard educator, can view and manage assigned cohorts | Model-level: view permissions. Object-level: assigned per cohort |
| **Teaching Assistant** | Can view assigned cohorts and student progress but cannot modify cohort settings | Model-level: view permissions only. Object-level: view-only per cohort |

### 5.5 Define custom permissions on models

Django allows defining custom permissions in model Meta classes. These work with both Django's built-in system and django-guardian:

```python
class Cohort(models.Model):
    class Meta:
        permissions = [
            ("view_cohort_progress", "Can view student progress in this cohort"),
            ("manage_cohort_students", "Can add/remove students in this cohort"),
            ("manage_cohort_educators", "Can assign educators to this cohort"),
        ]
```

### 5.6 Keep the permission set small and meaningful

A common mistake (and frequent complaint about Moodle) is having too many fine-grained permissions. Moodle's 350+ capabilities are powerful but overwhelming to configure. Canvas strikes a better balance with ~60 permissions organized into clear categories.

For FLS, aim for a focused set of permissions that cover the actual use cases described in the idea spec:
- Access the educator interface
- View specific cohorts
- View student progress within cohorts
- Manage students within cohorts
- Manage cohort settings
- Assign other educators to cohorts

### 5.7 Permission assignment should happen through the educator interface

Per the idea spec, "Build functionality for allowing permissions to be configured through the educator interface." This means building views where an Educator Admin can:
- See which educators have access to which cohorts
- Grant/revoke cohort-level permissions for specific educators
- Assign educators to role groups

django-guardian's `assign_perm` and `remove_perm` shortcuts make this straightforward to implement in views.

### 5.8 Avoid these anti-patterns

1. **Do not check permissions in templates alone** -- always enforce in views. Templates can hide UI elements, but the view must be the enforcement point.
2. **Do not use raw SQL for permission checks** -- use django-guardian's API which handles the joins correctly.
3. **Do not create a parallel permission system** -- use Django's permission framework with django-guardian rather than building custom permission tables.
4. **Do not assign permissions to individual users when groups would work** -- group-based permissions are easier to audit and manage at scale.

References:
- [Permissions in Django - TestDriven.io](https://testdriven.io/blog/django-permissions/)
- [Django Forum - Object level permissions with relations](https://forum.djangoproject.com/t/object-level-permissions-with-relations/21204)
- [Django Forum - Using django permissions with django guardian](https://forum.djangoproject.com/t/using-django-permissions-with-django-guardian-object-level-permissions/39243)
- [Django Guardian - Object-Level Permissions in 2025](https://searchcreators.org/search_blog/post/django-guardian-object-level-permissions-in-2025/)


## 6. Summary of Recommendations for FLS

1. **Use Django Groups as educator roles** (Educator Admin, Educator, Teaching Assistant) rather than building a custom role model.
2. **Use model-level permissions** for gating access to the educator interface and for broad capability checks.
3. **Use django-guardian object-level permissions** for cohort-scoped access control -- which educators can see which cohorts.
4. **Define a small, focused set of custom permissions** on the Cohort model (view progress, manage students, manage educators).
5. **Build permission management into the educator interface** so Educator Admins can assign cohort access without needing Django admin.
6. **Use `get_objects_for_user()`** for listing views to efficiently query only the cohorts an educator is permitted to see.
7. **Enforce permissions in views**, not just in templates.
