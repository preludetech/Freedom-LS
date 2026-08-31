# Whole-system QA: split into three ideas

**This file has been split. It is a signpost, not an idea.** The work is three separate specs, in the
three files listed below.

## Why it was split

FLS has no way to answer "does the whole product still work?", and no QA plan can run anywhere except
a developer's own machine. Fixing both at once turned out to be three loosely coupled pieces: an
endpoint that puts a deployed environment into a known state, a durable suite of plans, and a way for
downstream projects to inherit that suite. Each is separately useful and separately shippable, and
building them as one spec would mean a long implementation run where nothing works until all of it
does.

## The order

| Order | Idea | Covers |
|---|---|---|
| 1 | `idea_1_staging_reset.md` | `setup_qa_data` as an HTTP endpoint in a new app, its three-lock gate, the system check, the staging settings module, and the seeded dataset |
| 2 | `idea_2_qa_whole_system.md` | The `qa_whole_system/` suite: journey and area plans, directory layout and manifest, report format, the `/fls-dev:do_qa` upgrade, and a new SDD step that keeps the suite current |
| 3 | `idea_3_downstream_propagation.md` | Pulling plans into a concrete implementation, linking rather than copying, and drift detection |

**1 before 2** for the staging half only. Idea 2's plans can be written and run against dev
immediately, because dev already has the local fixture machinery. They cannot run against a deployed
environment until idea 1 ships, so idea 2 is not finished without it.

**2 before 3** without exception. There is nothing to propagate until the plans exist, and idea 3
depends on idea 2 having moved base URLs and credentials out of plan bodies and into configuration.
A plan that hardcodes its environment cannot be inherited unchanged.

**1 before 3** as well: a downstream staging run needs an installable reset app to point at.

## Shared research

The five `research_*.md` files in this directory back all three ideas and stay here. Each idea names
the ones that matter to it.

If you move an idea into its own spec directory to start work on it, the research files it cites need
to come with it or be reachable from it. `/sdd:spec_from_idea` reads the directory the idea sits in.
