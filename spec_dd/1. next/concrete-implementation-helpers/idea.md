FLS is designed to be included in other Django projects. We need to make this easy. We need:

- a template repo (seperate from this repo) that has a django project and fls included as a submodule and installed
- helpers for applying updates if FLS updates

There are some existing tools and plugins already that help with this, they might need to be fixed and edited.

In the simplest case, FLS concrete implementations will simply be FLS with the concrete project's configuration (eg it's own theme, icons, password stuff). In more complicated implementations, it'll have its own set of django apps and what not

Concrete implementations will use Claude Code. Claude should not make edits to the freedom_ls submodule, it's only there as a reference.

In future work we will add deployment/infrastructure helpers to fls or to a seperate repo. This is future work, it's not to be done now. But it is something we will need to handle. See the deployment-phase-1 spec as one example of how we might deploy fls. Deployment stratergies dont need to be implemented right now, they are future work.
