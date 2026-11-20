# Answers: multi-step-course-applications-1-review-states

Asked by `/sdd:start` before the spec was written.

- Q: Is the reject message required when rejecting an application? → A: Required; the service refuses an empty message (asked up front)
- Q: Which states can approve and reject act on? → A: `submitted` only; a draft cannot be approved or rejected (asked up front)
- Q: The dashboard panel narrows to active applications; where does a rejected applicant see the reject message? → A: Also on the dashboard: the panel keeps closed (rejected and approved) applications visible as well, not only the status page via the course CTA (asked up front)
- Q: Should withdraw ask the applicant to confirm first? → A: Yes, a confirm dialog before the withdraw POST (asked up front)
- Q: Which closed states does the dashboard panel show? → A: Rejected and approved; a withdrawn application drops off (asked up front)
- Q: How long does a closed application stay on the dashboard panel? → A: Until superseded: shown until the applicant applies again for that course, then the new active application replaces it; no time cut-off (asked up front)
