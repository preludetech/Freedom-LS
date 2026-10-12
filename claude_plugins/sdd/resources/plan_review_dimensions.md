# Plan review dimensions

`/sdd:plan_from_spec` spawns one `sdd:sdd-worker` per row, each writing
`.sdd-work/plan_review_<id>.md`. The worker contract, the finding line and the definition of a
clear fix are those in the preamble of `spec_review_dimensions.md`; the worker reads the plan and
the spec. A `new_threats` finding is always a judgement call written as a `> **Security concern:**`;
every other row's judgement call is a `> **Review concern:**`.

| id | checks | evidence it may cite | clear fixes |
| --- | --- | --- | --- |
| `success_criteria` | every spec success criterion is met by a plan step | the criterion and the step | a criterion with no step, when an existing step covers it once named; otherwise judgement |
| `vertical_slices` | each slice runs end to end and is tested; the first is the thinnest; no step groups by layer | the slice text | none; all judgement |
| `skills` | no step contradicts a skill the brief names by path | the skill line | the contradicting line replaced by the skill's rule when the skill states one |
| `generic_plugin` | no project name, path, app or value in a plugin whose README says it is generic | the README and the config file | moving the value into the project's config section |
| `junk_files` | no step leaves a file that needs manual cleanup | the step | a missing delete-by-name step |
| `clean_code` | proposed code is clean and simple | the snippet | none; all judgement |
| `comments` | no proposed comment or docstring points at the spec, plan, a slice, a phase, the QA plan or a section number | the snippet line | the pointer replaced by the fact it stood for |
| `vocabulary` | every noun and identifier matches the spec's vocabulary and the codebase's | the spec or source line | a term replaced by the spec's or source's term |
| `new_threats` | only what the plan adds or changes, one narrow check per trigger (list below) | the step | none; every hit is a judgement call |

The `skills` worker's brief passes the `SKILL.md` paths of the project's skills, since a worker
reads files and cannot load a skill by name.

## `new_threats` triggers

- A new view or endpoint: an explicit permission check, and the object looked up in a way that
  scopes it to the user or site, not fetched by id alone.
- A state-changing request, including a GET that changes state or an HTMX partial with weaker
  checks than its page: CSRF, and the same permission as the page.
- User input: a validating form; no `ModelForm` that takes owner, role or site fields from POST.
- Rendered user content: escaped, or its sanitiser named.
- A redirect target from input: `url_has_allowed_host_and_scheme`.
- A file upload: size, type and content checked; filename not user-controlled.
- An outbound call: credential from the environment.
- A role, permission or act-as parameter: checked server-side; no user id from the request acted on
  as that user.
- An ORM escape hatch: rejected unless the plan says why the ORM cannot do it.
- A user-controlled string used as a path, template name or format string.
- Deserialisation of untrusted data, or a subprocess with user-derived arguments.
- A settings change that weakens a security default.

No hits is `status: ok` with `no new threats`, and the worker produces nothing else. Rate limiting,
audit logging, dependency reputation and severity scales are out of scope.
