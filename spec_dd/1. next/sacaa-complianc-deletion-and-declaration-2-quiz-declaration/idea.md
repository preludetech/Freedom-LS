# Learners sign a declaration before a quiz

Spec 2 of 2 in the SACAA record retention and declarations effort. Read the "SACAA record
retention and declarations" section of `spec_dd/1. next/roadmap.md` first: it holds the build
order, what this spec depends on and may run beside, the decisions already taken and the
assumptions every idea in the effort makes.

## What

A content author can make a quiz require a declaration. Before the learner sees the first page,
FLS shows the declaration text, a tick box and a field for the learner's name. The learner ticks the
box and types their name. FLS stores the declaration text as shown, the typed name, the time and
the IP address against the attempt, and nobody can change them afterwards. The declaration shows
read-only on the attempt in the Django admin.

## Why

An auditor checking a SACAA training organisation's quiz results needs evidence that the learner
attested to doing the quiz themselves. A signed declaration with time and IP address gives them a
record to match against the learner.

## What is settled

- The declaration applies to quiz forms (`strategy` QUIZ) only. The validator rejects the
  declaration settings on any other strategy.
- The author sets it in the form's front matter, beside `submit_on_exit`: whether a declaration is
  required, the declaration text, and how often it is signed. Off by default; existing quizzes
  behave exactly as today.
- Frequency is per quiz, one of two values: every attempt, or once per learner. With "once per
  learner", the first attempt asks for the declaration; later attempts of the same form by the same
  learner go straight to the first page.
- A quiz that requires a declaration but gives no text uses a default declaration text from a new
  `form_engine` app setting.
- The declaration step sits between "Start Form" or "Try Again" and the first page. Every route into
  an attempt's pages is guarded, including resuming an open attempt ("Continue Form") and a direct
  link to a fill page, so no page is shown before the declaration is signed.
- The typed name must be non-empty after trimming. It is stored as typed and is not compared with
  the account name.
- The stored record is the declaration text exactly as shown, the typed name, the time and the IP
  address. It is tied to the `FormProgress` it was signed for, and is written once and never
  updated.
- The IP address comes from `accounts.utils.get_client_ip`, the sanctioned source for evidence
  trails such as `LegalConsent`.
- The declaration is for signed-in learners. Anonymous sittings (`FormProgress.user` null) never
  require one.
- Starting twice in quick succession (the `START_REUSE_WINDOW` reuse) does not ask for or store the
  declaration twice.
- `FormProgressAdmin` shows the declaration read-only.
- Force deleting the learner removes their declarations with their `FormProgress`; nothing in this
  spec blocks that.

## Open until the spec

- Whether the declaration lives in fields on `FormProgress` or in its own append-only model, and so
  how "never updated" is enforced.
- Which record "once per learner" checks to find an earlier signature (any signed attempt of the
  same form by that user, or only within the same course).
- Whether the declaration columns ride in the form export with the attempt-level columns
  `sacaa-compliance-4-attempt-review` plans.

## Out of scope

- Declarations on surveys, applications or other non-quiz forms.
- Checking the typed name against the account name.
- A site-level declaration text editable in the admin. The default is an app setting.

## Resources

- `research_quiz_declaration.md` in this directory: authoring options, the quiz start flow,
  `LegalConsent` and `get_client_ip`, attempts and retakes, collisions with other SACAA specs.
- `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md`: how a form-level option flows
  from front matter through `content_save` to the `Form` model.
