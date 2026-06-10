We need to make a concrete implementation of FLS. This will be a fresh Django project where FLS is included as a submodule as reference. We will need the FLS claude plugin set up and available.  This implementation will possibly have custom code and configuration, and might implement its own theme.

We need a file in docs/how-tos that explains the setup
We also need tools/scripts/templates that will make it easy to set up a new concrete implementation
We also need good ways to keep the concrete implementation up to date with the latest FLS changes

Concrete implementations will have a main branch. This is where FLS updates and new development will land.
It then needs a env/stage and env/prod branch for staging and prod environments. We will need to develop CI/CD on those branches in future.
