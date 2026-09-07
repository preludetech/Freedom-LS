We need to keep track of where users came from. sometimes they will arrive because of an advert and sometimes they will arrive because of a specific referrer code.

If they come from an advert, then there will be a specific get parameter on the URL that identifies the advert.
Referrer codes will be given to different people and organizations so that they can link to the LMS. We can then keep track of who business comes from.

Possible implementation:

Middleware on any GET carrying parameters:

Capture v, ref, utm_source/medium/campaign/content/term, gclid, fbclid, landing_path, HTTP referrer, first_seen_at.
Store in a first-party cookie fc_attr (90 days) and the session.
Overwrite rules: UTMs and click IDs are last-touch; ref is first-touch and never overwritten.
Validate ref against ^[A-Z0-9]{3,10}(-[A-Z0-9]{2,6})?$ and against the referrer table; unknown codes are dropped silently (never stored, never prefilled).
v accepts only a or b; anything else is a.

On signup, in the same view that creates the account: copy cookie/session values into an attribution row keyed to the learner, plus _ga, _fbp, _fbc cookie values, client IP and user agent. Written once, never updated.
