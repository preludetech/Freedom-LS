# Landing pages in a concrete project

A landing page is a public marketing page that turns advert or referral traffic into learners. One
page per promise, meaning one advert, audience or course, with a headline that continues whatever
the link said and a single primary action.

Landing pages are developer-authored and they live in your project, not in FLS. There is no page
model, no admin editing and no CMS. A page is a template, changed by a commit and a deploy.

| Layer | Owns |
|-------|------|
| FLS | The head metadata blocks in `_base.html`, the deferred-login CTA flow, the small cotton components |
| Your project | Routing, templates, copy, per-page metadata values, sitemap entries, images |

FLS ships nothing campaign-specific because there is no copy it could ship that would be right for
a campaign it knows nothing about.

`<c-page>`, `<c-button>`, `<c-callout>`, `<c-chip>` and `<c-media-card>` are available and cover the
small pieces. There are no hero, feature-grid, testimonial, FAQ or CTA-band components yet. Build
those in your own app for now. `<c-accordion>` and `<c-pull-quote>` look like matches but belong to
`content_engine`: they are tied to its sanitiser allowlist and expect a `content_instance`, so they
will not work in a plain template.

---

## Head metadata blocks

`freedom_ls/base/templates/_base.html` emits a canonical link, a robots directive and the Open
Graph and Twitter card tags. Every block has a working default, so a page only overrides what it
needs to change.

| Block | Default | Override when |
|-------|---------|---------------|
| `head_title` | empty | Always. This is the browser tab and the search result heading. |
| `meta_description` | `Learning management system` | Always. Also settable as a `meta_description` context variable. |
| `canonical_link` | `<link rel="canonical">` at the current path, query string stripped | Almost never. The default already collapses every `utm_*` variant onto one URL. |
| `meta_robots` | `index, follow` | The page should stay reachable by direct link without being ranked. Set it to `noindex`. |
| `og_type` | `website` | Rarely. `article` for something dated and authored. |
| `og_title` | `site_title` | Always on a landing page. This is the headline someone sees in Slack or WhatsApp. |
| `og_description` | the `meta_description` context variable, else the generic fallback | When the share blurb should differ from the search blurb. |
| `og_image` | empty | You have an image. Supply the whole `<meta>` tag, with an absolute URL. |
| `twitter_card` | `summary` | You set `og_image` and want the large format: `summary_large_image`. |
| `social_meta` | all of the Open Graph and Twitter tags | You want to replace the whole set at once. |
| `head_seo` | the canonical link, the robots tag and `social_meta` | Never on a landing page. The error pages replace it with a bare `noindex`, because a canonical URL echoes the request path back into the response. |
| `extra_head` | empty | Anything else, such as JSON-LD. |

A landing page that sets six of them:

```django
{% extends "_base.html" %}
{% load static %}

{% block head_title %}Learn Python in eight weeks{% endblock head_title %}
{% block meta_description %}An eight-week evening course in Python for working adults. Applications close 20 October.{% endblock meta_description %}
{% block meta_robots %}noindex{% endblock meta_robots %}

{% block og_title %}Learn Python in eight weeks{% endblock og_title %}
{% block og_image %}
    {% static 'landing/python-og.jpg' as og_path %}
    <meta property="og:image" content="{{ request.scheme }}://{{ request.get_host }}{{ og_path }}" />
{% endblock og_image %}
{% block twitter_card %}summary_large_image{% endblock twitter_card %}

{% block content %}
    ...
{% endblock content %}
```

Two things about `og_image`. It has to be an absolute URL, because the crawler fetching it has no
page to resolve a relative path against. And FLS does not re-encode it. The image pipeline covers
`content_engine.File` rows only, so a static asset arrives at the browser exactly as you committed
it. Optimise it before it goes in the repo.

`meta_description` also reads a `meta_description` context variable, and `og_description` falls back
to the same one. A view that computes the description once sets both.

---

## Tailwind will silently skip your templates

`tailwind.input.css` scans two globs:

```css
@source "./freedom_ls/**/templates/**/*.html";
@source "./freedom_ls/themes/*/templates/**/*.html";
```

A template directory outside `freedom_ls/` is not scanned. Nothing warns you. Every utility class
on the page compiles to nothing and the page renders unstyled. Add a glob for your app:

```css
@source "./your_project/landing/templates/**/*.html";
```

Then run `npm run tailwind_build`.

---

## The header competes with your CTA

`_base.html` renders `partials/header_bar.html` by default, which shows an anonymous visitor Login
and Sign Up buttons. That is right for the catalogue and wrong for a page whose one action is
already on the screen in a bigger button.

Do not drop the header. Applying to a course is a real commitment, and a visitor who arrived cold
and cannot confirm the organisation is real will leave and search instead of clicking. Override
`{% block header %}` with a stripped version, logo and name only:

```django
{% block header %}
    <header class="header">
        <a href="/" class="flex items-center gap-3 no-underline">
            {% if header_logo_static_path %}
                <img src="{% static header_logo_static_path %}" alt="{{ header_title }}" class="h-8 w-auto" />
            {% endif %}
            <span class="text-xl font-bold text-on-header">{{ header_title }}</span>
        </a>
    </header>
{% endblock header %}
```

`header_logo_static_path` and `header_title` come from the `site_config` context processor and are
available on every page.

---

## CTAs

A landing page asks for one of three things, and all three already work end to end for an
anonymous visitor:

| Action | Where the CTA points |
|--------|----------------------|
| Sign up for the platform | The allauth signup view |
| Apply to a course | `course_applications`, through the access backend's resolved CTA |
| Register interest in a coming-soon course | `course_interest` |

All three need an account, and the deferred-login flow already handles that. Link straight at the
`@login_required` view and let Django build `?next=`. For an action triggered by htmx, call
`redirect_to_auth` from `freedom_ls/accounts/utils.py`, which returns a 204 with `HX-Redirect` so
the browser navigates instead of swapping a login form into your button.

Three rules that are easy to get wrong.

**Do not put campaign data in `next`.** It conflates the redirect target with the traffic source
and widens the open-redirect risk that `next` is deliberately kept narrow to avoid. `next` is
where the visitor goes after logging in, nothing else.

**Every CTA is a server-rendered link or form.** htmx is enhancement, never the only path. This
page's whole audience arrives cold from an advert or a crawler, so it cannot afford a
JavaScript-only route to its one action.

**Say what is behind the button.** Signup runs under `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`,
so "sign up" really means "we email you a link to finish". Applying means filling in a form after
logging in. A page that hides the next step breaks its own promise one screen later, which is the
same failure as an advert that does not match its landing page.

---

## Indexing and the sitemap

A page's `meta_robots` setting and its sitemap membership are one decision. Keep them together in
whatever registry or config drives your pages, so the two can never disagree and you never list a
`noindex` page in your own sitemap.

`config/sitemaps.py` in this repo is the pattern to copy. Sitemap classes live in the composition
root, which is allowed to depend on any app, and the Sites framework supplies the right domain per
request. Add your landing pages as another `Sitemap` subclass there, or in the equivalent module in
your project.

If a page is scoped to one tenant, resolve the site through `get_cached_site(request)` from
`freedom_ls/site_aware_models/models.py`. Each `Site` is its own domain, so a page scoped to one
tenant stays out of another tenant's sitemap by construction.

---

## Copy

Conversion practice and the FLS brand voice mostly agree. Both rule out vague superlatives,
unattributed testimonials and manufactured scarcity. The last one is not a matter of taste. Fake
countdowns and stale "3 spots left" banners are documented deceptive practice with regulatory
consequences. Real dated urgency, "applications close 20 October", is both good voice and
defensible.

They disagree on volume. Conversion practice wants the CTA repeated at each pause point, and the
brand voice wants evidence before claims. Repeat the same CTA with the same words, and keep the
prose around it factual rather than getting more enthusiastic each time.

Two things carry real weight rather than being polish. Page weight is the first, because this
traffic is mobile and often on a poor connection, and load time is the best-evidenced conversion
variable there is. Form and heading accessibility is the second. A visitor who cannot tell which
field failed validation abandons the page.

See the `brand-guidelines` skill for tone and the `domain-glossary` skill before you invent a word
for something FLS already names.
