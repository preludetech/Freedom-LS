"""xAPI verb constants.

Each verb is a frozen dataclass carrying its ADL IRI and a human-readable display
string. Verbs are a closed, short list; domain apps pick from this module rather
than inventing new ones.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verb:
    """A single xAPI verb: IRI plus human-readable display."""

    iri: str
    display: str


# Verbs live in experience_api because ADL verb vocabulary is project-agnostic.
VIEWED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/experienced",
    display="viewed",
)
COMPLETED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/completed",
    display="completed",
)
ATTEMPTED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/attempted",
    display="attempted",
)
ANSWERED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/answered",
    display="answered",
)
REGISTERED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/registered",
    display="registered",
)
PROGRESSED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/progressed",
    display="progressed",
)
# Reserved for future event types — defined so wrappers may import them today.
SUBMITTED: Verb = Verb(
    iri="http://activitystrea.ms/schema/1.0/submit",
    display="submitted",
)
INTERACTED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/interacted",
    display="interacted",
)
VOIDED: Verb = Verb(
    iri="http://adlnet.gov/expapi/verbs/voided",
    display="voided",
)
