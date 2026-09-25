> This idea has been cut into twelve specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Educator interface rebuild" section of `spec_dd/1. next/roadmap.md`.
> Start there. The text below is the original brief and is kept as written.

There is currently an educator interface in place, but it is very underpowered and it relies on the panels framework that needs a lot of work. Nothing currently in the Educator interface should be treated as sacred. We can throw away whatever we need to and build it up from scratch in order to get things to work. Even the learner tracking cohort progress review can be changed. It's probably the most complicated part at the moment, and it can go. Consider it an illustration of the things that we might want to do with tables though, because we can potentially use tables for all sorts of interesting things.

And our end goal is:

1. The panels framework should be complete and self-contained and should be powerful enough for everything that we need.
2. The educator interface should allow educators to do everything that they need. So they should be able to administer the learning process by adding learners, removing learners, adding and removing educators, registering people for courses, etc.
3. the Educator interface should report on learner progress. As mentioned earlier, the learner progress table can go. We recently built a cohort report mechanism that has proved to be quite useful and successful. So our reporting functionality can be based on that.

Note that we currently have a deadlines mechanism built but it is also something that we want to rework quite drastically and so don't worry about implementing anything deadlines related for now. We will add it in later.

Also note that the panel's framework should allow a quick view panel that slides in from the right on large devices. It should not block access to the content that is underneath it. People should be able to quickly view something and click on the next thing to repopulate the quick view panel. the Quick View panel should be able to be populated through HTMX. We will use it for things like communicating with learners and whatnot. learner facing coms have not been implemented yet, that'll happen later, so the panel might not be used a lot just yet, although if it is helpful for building out functionality now, then use it.

The first thing we need to do is a bunch of research on the code structure and best practices and whatnot and then we need to break this spec into multiple specs that need to be developed in a specific order. Some of them can happen in parallel.
