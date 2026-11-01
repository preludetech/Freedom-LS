> This idea has been cut into 6 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Lead monitoring API" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

Currently, we export data from the admin panel in order to track marketing progress and leads and referrals and whatnot. It would be better to access this through an API.

Initially, this API will be only used by automatic processes. It isn't for any kind of user interface interaction. It's just for exporting data.

We need to be able to pull data about:
- users
- course applications (both anon and authenticated)
- referral links
- any other referral data
- course registrations
- course progress

Use Django Rest framework.

We need to make sure that the api is secure and we can access it from Python scripts automatically

Make sure the api is neat and tidy
