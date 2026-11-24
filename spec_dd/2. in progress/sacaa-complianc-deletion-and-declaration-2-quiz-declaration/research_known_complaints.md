# Research: known complaints about quiz declarations

Scope note: only two searches per theme were run. Direct learner complaints (Reddit, Canvas community) were NOT found. Most points below are documented behaviour or analogous problems, flagged as such. Treat the "design implications" as inference.

## Evidence found

### 1. Frequency is the contested choice (Moodle)
- Moodle core has an academic integrity statement, on by default for new quizzes, that students must accept before starting. Teachers turn it off under "Extra restrictions on attempts". Source: https://waikato.ac.nz/students/eresources/moodle/quizzes/create-a-quiz/academic-integrity-for-quizzes
- Tracker MDL-20574 proposed a per-attempt setting (No / Before first attempt / Before each attempt) with a checkbox "I confirm that this quiz attempt will be all my own work". Resolution: Won't Fix. Source: https://tracker-old.moodle.org/browse/MDL-20574
- Implication: "every attempt" versus "once per learner" is a real demand, and the idea's per-quiz two-value setting matches it.

### 2. Plugin `quizaccess_honestycheck` (Tim Hunt) user reports
Source: https://moodle.org/plugins/quizaccess_honestycheck
- Moodle 3.5: when the box was not ticked the form reloaded without a "must agree" warning, which confused students. Ticking worked. Design implication: show a clear validation error, and return it as HTTP 422 for HTMX.
- Moodle 4.1: the statement showed in English only to a German-language student. The maintainer's answer was to customise the language string. Implication: the text shown is a single string and is not translated per learner. The stored text must be the exact string shown.
- Teachers asked where the statement text is edited and could not find the setting (Moodle 3.11). Implication: authors need an obvious place for the text. Here that is front matter plus the app-setting default.
- Other users on Moodle 3.11 could not see the option at all (the thread had no resolution). Implication: not relevant beyond discoverability.

### 3. IP address evidence is weak behind proxies
- X-Forwarded-For is easy to forge. The left-most value is client-supplied. Source: https://en.wikipedia.org/wiki/X-Forwarded-For
- Guidance is to log both the connection address and the forwarded chain, and to trust forwarded values only from known proxies. Sources: https://openvpn.net/as-docs/v3/tutorials/tutorial--real-client-ip-proxy-load-balancer/ , https://www.opswat.com/docs/mdmft/configuration/trusted-forwarder
- Real audit-log failures: the reverse proxy's address was logged instead of the client's, and forwarded values were trusted from untrusted proxies (spoofing risk). Sources: https://www.github.com/AdguardTeam/AdGuardHome/issues/6978 , https://support.zabbix.com/si/jira.issueviews:issue-html/ZBX-23092/ZBX-23092.html
- Implication for FLS: check what `accounts.utils.get_client_ip` trusts. A shared NAT or campus address matches many learners, so the IP is corroboration only, not proof of identity. The spec should say so and not over-promise to auditors.

## Not found (hypotheses to design against, unverified)
Learner side:
- Friction on every retake.
- Losing progress.
- Being asked again on resume.
- Mobile layout problems.
- Confusion about name format (full name, legal name, case).

Teacher and admin side:
- Cannot find the record.
- Text changed after signing.
- Records lost on user deletion.
- IP privacy (personal data).

Auditor side:
- Whether the typed name matches the account name.

Design responses implied by the idea: store the text snapshot, make the record append-only, show it read-only in admin, guard resume and direct links without re-asking, and do not re-ask within `START_REUSE_WINDOW`. Open question for the spec: the deletion decision (the declaration is removed with `FormProgress`) is a stated product choice that conflicts with audit-retention expectations. This is the sibling spec's concern.

status: ok · reason: web evidence thin for learner complaints; Moodle, proxy-IP sources cited, rest labelled as hypotheses
