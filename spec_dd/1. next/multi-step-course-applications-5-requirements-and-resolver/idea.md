# Application requirements and the requirement resolver

Spec 5 of 12 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An applicant with a claimed account sees one requirements page for their `CourseApplication`. It lists
each application requirement and its status, and they work on the requirements in any order. A form
requirement opens its own sitting, and the applicant can reopen it until the application is approved.
Which requirements an application has is decided by a requirement resolver, a class a deployment names
in a setting. The default resolver reads a fixed list from the course's content. Reviewers see the
list, read-only, on the review screen. A demo course in `demo_content/` shows a fixed list.

## Why

A course's application is a set of steps whose number and kind depend on the course and, for a
deployment with real rules, on what the applicant has said. FLS owns the machinery and the
deployment owns the rules. This spec is the foundation: the requirement model, the resolver seam,
and the one function that keeps stored requirements in step with the resolver. Verdicts, uploads and
choices are built on it.

## What is settled

**Application requirement** is a new term, to be added to the glossary. It means one thing an
applicant has to do or provide for one `CourseApplication`. "Requirement" is not a model, field or
function name in FLS today.

A requirement has:

- a stable key, which is its identity. The fixed-list resolver takes it from the content, and a
  downstream resolver chooses its own.
- a kind: form, upload or staff verification. The upload kind is declared here, but it only becomes
  workable in `multi-step-course-applications-7-upload-requirements`.
- a status: outstanding, submitted, accepted, turned down or superseded.
- what it holds back: approval, registration or nothing.
- optional options, and the option the applicant picked. FLS stores the pick and the deployment
  supplies the options.

**The resolver** follows the house pluggable pattern. A setting names the class. A loader returns it.
A decision value lists the requirements wanted. A boot check verifies the setting, and a conformance
probe goes in `freedom_ls/contrib/conformance/` for a downstream to prove its resolver honours the
contract. The default is the fixed-list resolver, so an install works out of the box. The resolver
is a pure function of the application's current data and has no side effects.

**The fixed list** lives in the course's `access_config` under a new `requirements:` key. Each entry
gives the requirement's key, kind, title, description, what it holds back, and for a form kind a
form path relative to `course.md`. The list is validated at content load and at boot, and form
references are resolved to loaded forms the way `application_form` is, so a missing form is
rejected at load. Only the fixed-list resolver reads this key. No view or template reads
`access_config`.

**Reconcile** is one function. It runs the resolver, creates each wanted requirement that is not
stored as outstanding, and marks each stored requirement no longer wanted as superseded. Superseded
requirements are kept, never deleted. It never touches an accepted requirement. It is idempotent: when
nothing changed it writes nothing, so `updated_at` does not move. It locks the application so
concurrent events serialise. There is no workflow graph.

Reconcile is called explicitly from each event site, not through signals: an answer saved (once per
page submission, not per answer row), a sitting completed, and, as later specs add them, an upload and
a verdict. A verdict is atomic with the reconcile that follows it.

**Sittings.** `CourseApplication.form_progress` stays as the application form and every existing
reader of it is unchanged. Further form requirements own their own sittings. Merging the two is not
done here.

**Claimed accounts only.** Requirements start only for a claimed application. An unclaimed applicant
sees the application form as today, and is asked to claim their account to continue. This also
avoids the anonymous session reaching only a draft sitting, which would make a completed form
unreachable.

**The requirements page.** The applicant sees one page listing each requirement and its status. Form
requirements open their own sitting. An applicant can reopen a form requirement until the application
is approved, using the mechanism from `multi-step-course-applications-4-reopen-form`. Reopening an
accepted form puts the requirement back to submitted, so a reviewer sees the new answers before they
count. Each reopen is audited.

**Reviewers** see the requirement list read-only on the review screen. Accepting or turning down is
`multi-step-course-applications-6-reviewer-verdicts`.

**Content versus Python.** Anything an author changes per course without a deploy is content: forms,
branching and a course's fixed requirement list. Anything computed from applicant data with domain
rules is Python behind the resolver seam. The downstream project keeps its qualification rules, its
exam centres and examiners and their ranking, its document types and its wording.

## Open until the spec

- What a resolver failure does to the request: fail loudly, or keep the stored list. The project
  avoids silent failures and logging unless asked, which leans to failing loudly. The spec decides it
  for production.
- Whether the content list is validated by the access backend whenever the key is present, or by the
  resolver's own validation hook. A downstream resolver may ignore the list.

## Out of scope

- Accepting and turning down requirements, rejection reasons and the "the applicant will be asked to"
  preview, and holding back approval or registration: `multi-step-course-applications-6-reviewer-verdicts`.
- Upload requirements working: `multi-step-course-applications-7-upload-requirements`.
- Either-or groups of requirements: `multi-step-course-applications-8-choices`.
- Requirements for an unclaimed applicant.
- Merging `CourseApplication.form_progress` into the requirements model.

## Resources

- `research_requirements_and_forms.md`, in this directory: the house pattern for the resolver, the
  `access_config` validation chain, how the application sitting is created and driven today, and
  where the reconcile calls hook in.
