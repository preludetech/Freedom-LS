"""Domain event names the educator interface's panel actions fire.

Specs 6 to 9 add REGISTRATION_CHANGED and EDUCATOR_CHANGED consumers; this
spec declares all four names now so later specs have nothing left to name.
"""

from __future__ import annotations

LEARNER_CHANGED = "learnerChanged"
COHORT_CHANGED = "cohortChanged"
REGISTRATION_CHANGED = "registrationChanged"
EDUCATOR_CHANGED = "educatorChanged"
