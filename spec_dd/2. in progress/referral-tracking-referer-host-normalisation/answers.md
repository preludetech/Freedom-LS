# Answers: referral-tracking-referer-host-normalisation

Asked by `/sdd:start` before the spec was written.

- Q: Should the referer host helper strip mobile prefixes like `m.` and `mobile.` as well as a leading `www.`? → A: Only `www.`, as in the First-Class-LMS reference; the marketing-channel classifier matches domains by suffix, so `m.facebook.com` still lands on facebook there (asked up front)
