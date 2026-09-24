# Permission matrix on existing roles

Type: grilling
Status: open
Blocked by: 01

## Question

Using only the existing roles (`site_admin`, `organisation_staff`, `instructor`, `ta`; see `freedom_ls/role_based_permissions/roles.py`), which role may perform each capability in the map's list, and at which scope (site, organisation, cohort)? What has to change in the permission machinery to make that work? This includes the known blocker in the `organisation_staff` FUTURE note: object-aware checks for creation, and role permissions being filtered to the assigned object's content type. Also decide which roles may assign which other roles.

Start by settling which of the candidate capabilities from [Comparable systems: learner-management actions](01-comparable-systems-learner-management.md) join the list (reactivate, audit log, pending and revocable invites, roster export, learner detail editing, registration access dates), then update the capability list in the map's Notes.
