Create a cloud command for git rebase main. This command should get the rebase done and run tests.  If there are any changes to any code that touches the front end, then we need to not only run the unit tests, but also do a type of QA run on those components. We need to open the browser and look around and make sure that it is okay, on multiple screen sizes.

 if we are doing a spectrum development workflow and we're rebasing that branch, Then there is likely a QA plan in place. that can be run. If there is no relevant QA plan, then just open up a browser and poke around.  Get an idea of what the functionality should be by looking at previous Specs that have been completed if needed. This should be something that we only do need it, if we do a full QA run of the whole process, then that will be expensive and slow.

 This command would be used during the spectrum and development workflow, so we need to update that. we will need to rebase  when we are finishing up the work tree.

  This work is currently being done because we did a git rebase that broke a lot of front-end functionality.  The workflow command we create now should be demonstrated by fixing what is broken.
