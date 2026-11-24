# Answers: referral-tracking-marketing-channels

Asked by `/sdd:start` before the spec was written.

- Q: Should the marketing-channel classifier show anywhere in FLS (e.g. an admin column or filter on `SignupAttribution`), or ship only as a Python module that projects call? → A: Module only. A pure classifier in `referral_tracking`, with no UI. (asked up front)
- Q: When a first touch has a `referral_code` (or `advert_code`) but no UTM, click ID or referer, which channel does it get? The First-Class-LMS classifier ignores both codes and returns Direct. → A: `referral_code` → Referral. `advert_code` is still ignored, because it names an advert, not a channel. (asked up front)
- Q: Can projects extend the classifier's source and host tables (their own newsletter host, a regional search engine)? → A: No. The tables are fixed module constants, as in the reference. A project that needs more wraps the classifier. (asked up front)
