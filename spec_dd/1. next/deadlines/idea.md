> This idea has been cut into 7 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Deadlines" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

There is currently a deadline implementation in place, but it is not flexible enough and can be completely removed.

We need flexible deadline implementation that meets the goals of standard LMSs.  We need to be able to set deadlines on individual content items and we also need to give learners a specific amount of time to finish entire courses. We need to also be able to extend deadlines, so for example if somebody signed up for a course and they are only meant to have access for three months and they get sick we should be able to pause and unpause their stuff so they can continue later. We might want to pause things for a specific amount of time.

There might be comms involved as well or notifications so if somebody is reaching a deadline or about to Go over their deadline or something is due today, then we might want to notify the learner.

We might also want educators to know when people are in danger of missing their deadlines.

When a person misses a deadline then that can have different consequences and that might be different in differnt courses, cohorts or organisations.

 We need something that is both robust and flexible. If it makes sense to allow for different deadline backends to have different behaviour, then that is an option. But we'll need to be able to select different configuration for different things.

If a learner signs up for a 3 month course and they need to pause their subscription, we need a good way to manage that that is simple for both the learner and organisation staff
