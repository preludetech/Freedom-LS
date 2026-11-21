# Answers: faster-test-runs-3-permission-matrix-test

Asked by `/sdd:start` before the spec was written.

- Q: Which shape should the faster permission matrix test take: one test per capability that builds the world once and walks every role × scope cell, 763 separate tests reading a world built once per module, or pytest subtests? → A: Walk per capability. One test per capability builds the world once and checks every role × scope cell, failing with a list of every disagreeing (permission, role, object, relation); it works with pytest-django's per-test rollback and keeps no database state between tests (asked up front)
- Q: Should the spec cover the other tests in `test_permission_matrix.py` that rebuild the same world per case (the StaffMember-deactivation test, the visibility tests and the import-gate tests), or only the 763 matrix cases? → A: The whole file. Every world-building test in the file gets the same treatment, so the measured saving covers the file (asked up front)
