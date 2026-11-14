> This idea has been cut into 7 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Educator interface code layout" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

freedom_ls/educator_interface/views.py This file is MASSIVE and hard to read

Break it down. Have subfolders for each major part.maybe like this:

- panels
    - dashboard
    - cohort
    - learner
    - course_staff
    - audit_log
    - common #shared

Then have modules for different types of things. Eg

- learner
    - config.py (LearnerConfig)
    - data_table_panels.py (contains LearnerCohortsPanel, relevant non-common bulk actions)
    - instance_view (should this be a directory or a file?)


Make sure that the unit tests follow the same hierarchical structure
