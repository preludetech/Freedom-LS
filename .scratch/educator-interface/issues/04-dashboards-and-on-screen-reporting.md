# Dashboards and on-screen reporting

Type: grilling
Status: open

## Question

What do educators see when they log in to check how things are going, and what can they download? Decide:

- dashboard levels (organisation, cohort, course-within-cohort, learner) and what each shows;
- which parts reuse the cohort report's gathered data (`freedom_ls/reports/gather.py`, `report_data.py`: summary table, at-risk flags, attention list, per-learner detail, quiz confusion) and which need new queries;
- what replaces the deleted progress matrix for drilling into a learner's progress;
- downloads: which reports, at which levels, and whether existing generation (async task, `GeneratedReport`) covers them;
- live data vs gathered report data.
