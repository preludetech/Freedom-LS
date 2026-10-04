"""Domain event names the educator interface's panel actions fire.

All four names are declared here, including ones nothing listens for yet, so
every panel fires events from one fixed list instead of inventing names.
"""

from __future__ import annotations

LEARNER_CHANGED = "learnerChanged"
COHORT_CHANGED = "cohortChanged"
REGISTRATION_CHANGED = "registrationChanged"
EDUCATOR_CHANGED = "educatorChanged"
