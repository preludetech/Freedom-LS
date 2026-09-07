# Research: what makes a course-marketing landing page convert

Scope: evidence for FLS landing pages — public, per-campaign pages that turn advert/referral
traffic into one of four actions (sign up for the platform, apply to a course, register interest
in a coming-soon course, or leave contact details without an account). FLS vocabulary is used
throughout: **learner**, not student; **registration**, not enrolment; **content**, not
curriculum. Where a cited source uses "student," "lead," or "enrolment," that is the source's word,
quoted and translated at the point of recommendation.

A general caveat that applies to the whole file: landing-page "conversion optimisation" is one of
the most anecdote-polluted corners of UX writing. A large fraction of the publicly repeated
statistics ("increased conversions 304%", "212% lift") are single-company, single-test,
unreplicated case studies reported by vendors (Unbounce, CXL, HubSpot, WordStream, Formstack) who
sell tools built on the advice. They are marked **[anecdote]** below. Findings from Nielsen Norman
Group (NN/g), Baymard Institute, GOV.UK Service Manual, WCAG, and Google Search Central are
research-based or drawn from large aggregated datasets and are marked accordingly. Where marketing
folklore and a research body disagree, both sides are given.

---

## 1. Message match and dedicated per-campaign pages

**Sending paid or referral traffic to a generic page measurably underperforms a dedicated
page.** Dedicated landing pages convert several times better than sending the same traffic to a
homepage or course catalogue: cited figures range from "65% higher" to "3–5x" depending on the
report, and one aggregator gives a 2026 median of 4.02% for dedicated landing pages against 2.35%
for general website pages — roughly double
([Unbounce/industry benchmark summaries via digitalapplied.com](https://www.digitalapplied.com/blog/landing-page-statistics-2026-conversion-data-points),
[foundrycro.com benchmark report](https://foundrycro.com/blog/landing-page-conversion-rate-benchmarks-2026/)).
These are industry-benchmark aggregations rather than a single controlled experiment, so treat the
exact multiplier as **directionally reliable, numerically soft** — but the direction (dedicated
beats generic) is consistent across every source found and matches the underlying mechanism below,
so it is not treated as anecdote.

**The mechanism is message match**, not just "having a landing page." Continuity between what the
advert or referral link promised and what the page's headline says is the load-bearing variable.
Google's own Quality Score system penalises ad-to-landing-page mismatch directly, and a documented
case (Disruptive Advertising, reported via Moz) found aligning ad copy to landing-page headline
lifted conversion 212% and cut cost-per-conversion 69% — a real, named, single-case study,
**[anecdote]**, but consistent with the *mechanism* Google's Quality Score system formalises
([WordStream/Moz message-match summaries via webtonic.io](https://www.webtonic.io/blog/message-match),
[carnegiehighered.com on message match](https://www.carnegiehighered.com/the-importance-of-message-match-landing-pages-101/)).
A second, independently reported case (KlientBoost) found a 66% lift from headline-only alignment
with no other change — again **[anecdote]**, but directionally the same claim from an independent
source.

**Structural implication for FLS**: "one landing page per campaign" is not sufficient if a
campaign runs several distinct adverts (different audiences, different UTM creative variants,
different referral partners) each making a slightly different promise. The literature's
recommendation is one page per *distinct promise*, not one page per *campaign* — a campaign with
three ad variants aimed at three audience segments (career-changer, employer L&D buyer, existing
learner referred by a peer) plausibly needs three headline/subhead variants of the same underlying
page, addressable by URL parameter, rather than one page trying to speak to all three. This is
inference from the message-match evidence above, not a separately sourced claim.

**NN/g's framing generalises this beyond ads**: users spend the first seconds of any page deciding
whether it is relevant to the intent they arrived with; the page's job is to *confirm the promise
that got them there*, not to introduce a new one
([NN/g homepage usability guidelines, summarised](https://www.nngroup.com/articles/113-design-guidelines-homepage-usability/)).

---

## 2. Above the fold

NN/g eye-tracking aggregation puts roughly 57% of page viewing time above the fold — meaning the
first screen still gets the majority of attention even though users do scroll, and it must earn
the scroll rather than assume it. Users "scroll... only if what's above the fold is promising
enough" — the top of the page functions as a promise, not the whole pitch
([NN/g research on above-the-fold viewing time, summarised via secondary aggregation](https://cxl.com/blog/above-the-fold/)).
The primary NN/g articles on the underlying eye-tracking methodology were not independently
re-verified in this pass and this figure should be treated as **well-attributed but
secondhand** — it is consistently repeated across independent secondary sources, which raises
confidence but is not the same as reading the original NN/g report directly.

The converged structural pattern across sources — headline stating the primary benefit in plain
language, a subheadline adding the specificity the headline can't carry, a single visually
dominant CTA, and a supporting image or video that shows rather than illustrates abstractly — is
consistent across NN/g-adjacent and CXL summaries. The headline's job specifically is to answer,
without scrolling: *what is this, who is it for, what do I do next*. A headline that requires
interpretation (cleverness, wordplay, an abstract noun) forces cognitive work the visitor did not
come to do and is flagged repeatedly as a failure mode across sources.

**Mobile-first is not optional for this brief.** Given that most advert and referral traffic is
plausibly mobile (adverts served in social feeds, referral links shared via messaging apps), "the
fold" is a much shorter distance on a phone than on desktop — the headline, subhead, and CTA need
to fit a single mobile viewport without the visual "supporting image" pushing the CTA below it.
None of the sources found gave this as a distinct numeric finding, but it follows directly from
the mobile page-weight and load-time findings in §9, which are specifically about mobile.

---

## 3. One primary action — attention ratio

The dominant concept in landing-page practice is **attention ratio**: the number of clickable
things on the page (links, nav items, footer links, secondary CTAs) divided by the number of
campaign goals. Unbounce's stated ideal is 1:1 — one goal, one place to click
([Unbounce, Attention Ratio glossary entry](https://unbounce.com/conversion-glossary/definition/attention-ratio/)).
This concept is attributed to Oli Gardner (Unbounce co-founder) and framed as "conversion-centered
design" — it is **industry practitioner doctrine**, not a peer-reviewed or independently
replicated research finding. It is treated as trustworthy here because the underlying logic
(every link is a possible exit, and exits compete with the one action the page exists to produce)
is uncontroversial and consistent with NN/g's more general finding that reducing choices reduces
decision paralysis, but readers should know its provenance is a vendor's named framework, not a
lab study.

**The counter-argument is real and should be reported as contested, not dismissed.** Removing all
navigation optimises for warm, high-intent traffic that already trusts the sender (a specific
advert promise, a referral from someone the visitor already trusts). It actively works against
colder or more skeptical traffic that wants to verify the sender is a legitimate organisation
before acting — such a visitor, given no way to browse, may simply leave and search independently,
which is worse than losing them to an on-page link. The synthesised practitioner position across
several sources: keep navigation off for hot, high-commitment single-goal traffic; for colder or
higher-consideration traffic (plausible for FLS given "apply to a course" and "sign up for the
platform" are both higher-commitment asks than a SaaS trial), a stripped header — logo only, no
menu, maybe one "how it works" anchor link — is an acceptable middle ground
([summarised across seedprod.com, lilachbullock.com, cxl.com landing-page-navigation
discussions](https://www.seedprod.com/landing-page-navigation/)). None of these secondary sources
were independently verified against the original CXL data-driven article (it returned a 403 on
fetch); the claim about acceptable exceptions is reported as **practitioner consensus, not a
verified primary study**.

Applied to FLS: a course-application landing page is inherently higher-consideration than a
newsletter signup, so the honest position is that full nav removal is the more aggressive choice
and stripped-header-with-logo is the safer default, not the reverse.

---

## 4. Repeated CTA and page length

**Page length should be set by the size of the ask and the trust deficit, not by a fixed template.**
The converged position (CXL, and consistent with NN/g's general framing of persuasion): a
low-commitment action (leave contact details, register interest) converts fine on a short page; a
high-consideration action (apply to a paid course, commit to a start date) needs more room for
objection-handling, social proof and detail before the CTA is credible
([CXL, "Long Form or Short Form Landing Pages?", summarised via search index](https://cxl.com/blog/long-form-or-short-form/)).
This has a direct implication for FLS's four distinct actions: they should not share one page
template tuned to one page length. "Register interest in a coming-soon course" plausibly needs
less page than "apply to a specific course," which needs less than "sign up for the platform"
(a bigger, more open-ended commitment).

**The CTA should repeat at the end of each persuasive "chunk," not just once at the top and
bottom.** One frequently cited datapoint — a single page where moving/adding a CTA at the bottom
of a very long page lifted conversions 304% — is a **single named case, [anecdote]**, not a
general law, but it illustrates the underlying and much better-supported principle: a visitor who
has just been persuaded by a paragraph of evidence should not have to scroll back up to act on
that persuasion. This is a restatement of Fitts's-Law-adjacent proximity reasoning found broadly
across UX writing, not something requiring its own citation.

**Decision fatigue is the honest trade-off**, and none of the sources found quantify it well for
landing pages specifically — it shows up mostly as a qualitative caution ("some visitors are
persuaded by a simple page, others only after learning everything," per CXL) rather than as a
measured cost. The practical reading: repeat the *same* CTA (identical copy, identical action) at
each natural pause point; do not repeat it with escalating urgency or different offers, which is
where repetition tips into the scarcity/urgency anti-patterns in §8.

---

## 5. Trust and evidence for an education audience

General web-credibility research (Jakob Nielsen's four factors, still the basis of NN/g's current
material) gives four levers: design quality (no errors, coherent visual system), up-front
disclosure (price, terms, who's behind the offer), comprehensive and current content, and
connection to the rest of the web (third-party mentions, not just self-hosted claims)
([NN/g, "Trustworthiness in Web Design: 4 Credibility Factors"](https://www.nngroup.com/articles/trustworthy-design/)).

**Testimonials on the page itself are weaker evidence than testimonials off it, and users know
it.** NN/g's research found participants explicitly distrustful of on-site quotes and case
studies — "wondered if the stories were true," noted a site "would of course only include positive
reviews" — and trust external reviews more
([NN/g summary, same article](https://www.nngroup.com/articles/trustworthy-design/)). For FLS this
argues for linking out to (or embedding, attributed, verifiable) third-party review platforms or
alumni-controlled channels over hand-picked pull-quotes with no way to verify they are real
learners.

**Education-specific credibility signals repeatedly named across course-marketing sources**
(instructor/educator bio and credentials, curriculum/content overview, accreditation or
certification claims, start-date/cohort specificity, price transparency, FAQ addressing objections)
are consistently listed but the sourcing for this category is weaker than for the general
credibility research above — mostly vendor content-marketing round-ups (Kajabi, LearnWorlds,
Unbounce landing-page-example galleries), **flagged as weakly sourced** rather than research-backed
([e.g. LearnWorlds course-landing-page guide](https://www.learnworlds.com/blog/market-sell/course-landing-page-with-examples/)).
The one point that is not folklore and follows directly from the trust-factor research above:
**an accreditation or certification claim is only as credible as it is up-front and verifiable** —
naming the accrediting body, linking to it, and stating exactly what is and isn't certified is the
disclosure-factor principle applied to education specifically. A vague "certified" badge with no
named issuer reads as the opposite of trustworthy under the same research.

**"Who is this for / who is this not for"** does not have a dedicated citation in what was found,
but it is a direct application of the up-front-disclosure principle: telling a visitor they are
*not* a fit is itself a disclosure signal, and its absence (every course "is for everyone") reads
as evasive under the same logic that penalises hidden pricing.

**What reads as fake, per the same research**: unverifiable superlatives, testimonials with no
attribution, generic stock photography claimed as "our learners," and claims that could not survive
a link-out to their source.

---

## 6. Form design at the conversion moment

**Fewer fields converts better — this is Baymard's best-evidenced finding, though the numbers
come from e-commerce checkout, not lead capture, and should be read as directionally transferable,
not a direct fit.** Baymard's checkout research: forms average 14.88 elements when 7–8 are needed;
forms with 7+ fields see 67.8% abandonment; each extra field costs roughly 4.1% conversion; better
checkout form design alone can lift conversion up to 35%
([Baymard, "Checkout Optimization: From 16 Form Fields to 8 Fields"](https://baymard.com/blog/checkout-optimization-from-16-fields-to-8)).
Baymard also found labelling fields "optional" (rather than marking required fields with an
asterisk) lifted conversion ~25% in a 500-user B2B study, and single-column layouts are processed
15–22% faster than multi-column by eye-tracking
([Baymard, form usability findings, summarised](https://www.digitalapplied.com/blog/form-conversion-rate-benchmarks-2026-data-points)).
These are e-commerce-checkout studies; FLS's forms are shorter and pre-purchase, so treat the
qualitative direction (fewer fields, single column, "optional" labelling) as solid and the specific
percentages as belonging to a different context.

**Multi-step versus single-step is genuinely contested, and the marketing-blog literature on it is
weakly sourced.** Vendor-reported aggregate numbers (Formstack: 13.85% vs 4.53%, a 206% lift;
HubSpot: 86% higher for multi-step) are self-reported by companies selling multi-step form tools —
**[anecdote / vendor-interested, treat with real skepticism]**
([summarised via zuko.io and ivyforms.com round-ups](https://www.zuko.io/blog/single-page-or-multi-step-form)).
This sits in direct tension with GOV.UK Service Manual's much more carefully researched "one thing
per page" pattern, which recommends splitting complex forms into one-question pages specifically
because it helps low-confidence users, works better on mobile, and handles branching/errors/save-
and-resume better — but GOV.UK's own guidance is explicit that this is a starting hypothesis to
test, not a universal law, and that user research "will likely show some questions are best grouped
into a longer page"
([GOV.UK Design System / "one thing per page"](https://designnotes.blog.gov.uk/2015/07/03/one-thing-per-page/),
[GOV.UK Service Manual, question pages](https://design-system.service.gov.uk/patterns/question-pages/)).
**Honest synthesis**: for a form under ~3–4 fields, a single step is at least as good and simpler
to build; GOV.UK's one-thing-per-page pattern is well-evidenced for genuinely long, branching
forms (an application with eligibility questions, documents, multiple stages) — which "apply to a
course" plausibly is — but poorly evidenced as a rule for a short lead-capture form, where it adds
steps without adding clarity.

**Lead capture versus signup are different objects and should ask for different things.** This
distinction is implicit across the form-conversion literature rather than named as such by any one
source, but the mechanism is clear and consistent: a **lead capture form** (FLS's "register
interest" / "leave contact details" actions — no account created) should ask only for what is
needed to make the *next* human contact meaningful — typically name, email, and the specific thing
they're interested in; phone number specifically is flagged as a field that "significantly reduces
form completion rates" and should be optional unless the follow-up process genuinely depends on a
call
([summarised via multiple lead-gen-form round-ups](https://leadformhub.com/blog/best-lead-form-fields-for-high-conversion)).
A **signup form** (creates an account) has a different job — it needs enough to create a working
account (email, password or auth method) and can legitimately defer everything else (goals,
background, course interest) to a post-signup step, once the account exists and the visitor has
already committed. The general credibility-research principle in §5 — that asking for information
before delivering value reads as untrustworthy — argues for asking as little as possible at both
moments and pushing anything not strictly required to *after* the account or the lead record
exists, where it can be framed as "tell us more" rather than a gate.

---

## 7. Friction the visitor did not expect

None of the sources found addressed this directly as "landing page expectation setting for a
multi-step flow" as a named research topic — this section is closest to folklore-adjacent
practitioner advice, but it connects cleanly to two well-evidenced NN/g principles.

**Progress indicators exist specifically to manage the gap between what a visitor expected and
what the system is actually asking of them.** NN/g's research on progress indicators: they create
an expectation for how much is left, and violating that expectation (moving fast then stalling)
damages satisfaction more than not showing progress at all; showing all steps up front helps the
visitor form an accurate mental model before committing to step one
([NN/g, "Progress Indicators Make a Slow System Less Insufferable"](https://www.nngroup.com/articles/progress-indicators/)).
Applied to FLS: if a landing page's CTA leads to a multi-step application, a login wall, or a
verification email, the page should say so *before* the click — "apply in 3 steps," "we'll email
you a link to finish," "requires a short application" — rather than let the visitor discover the
scope mid-flow. This is the same logic as message match in §1: the click itself is a promise, and
the next screen is where that promise is either kept or broken.

**A login wall or verification email immediately after a promised action is a specific,
well-documented trust break**, per the general credibility research in §5 ("requesting personal
information before delivering value signals opacity... login walls or gated content before
offering any benefit damage credibility"). If "sign up for the platform" or "apply to a course"
necessarily routes through email verification, the honest fix is not to hide that step but to name
it on the landing page itself, before the click.

---

## 8. Common complaints and anti-patterns

**Regulatory-grade evidence exists for fake urgency and scarcity, and it is strong.** The US FTC's
2022 report "Bringing Dark Patterns to Light" names fake countdown timers, false urgency claims,
and fake low-stock messages specifically as deceptive practices actionable under Section 5 of the
FTC Act; a 2024 FTC review found 75.7% of 642 reviewed companies used at least one dark pattern,
66.8% used two or more
([FTC, "FTC Report Shows Rise in Sophisticated Dark Patterns"](https://www.ftc.gov/news-events/news/press-releases/2022/09/ftc-report-shows-rise-sophisticated-dark-patterns-designed-trick-trap-consumers)).
This is not contested advice — it is a finding with enforcement consequences, and it should be read
as a hard constraint rather than a stylistic preference. A countdown timer that resets on page
reload, or a "3 spots left" that has read "3" for weeks, is not a grey area.

**Named deceptive patterns directly relevant to a landing page/form flow**, per the
deceptive-design taxonomy (Harry Brignull's framework, now hosted at deceptive.design):
*confirmshaming* (guilt-based copy on a decline/close action — "No thanks, I don't want to learn"),
*roach motel* (easy to enter, hard to leave — relevant if "leave contact details" turns out to
create marketing-list obligations not disclosed), and *trick questions* (misleading checkbox or
consent wording)
([Mozilla, overview of deceptive design patterns](https://blog.mozilla.org/en/internet-culture/deceptive-design-patterns/)).
"Dead-end pages" and "back-button traps" specifically were not found in a primary taxonomy source
in this pass; they are real, commonly reported UX complaints but should be treated here as
practitioner-observed rather than independently verified against deceptive.design's own list.

**Interstitials and pop-ups have a direct SEO and UX cost, documented by Google itself.** Google
Search Central explicitly discourages intrusive interstitials that block content, recommends
banners over full-page takeovers, and disallows redirecting users to a separate consent page
([Google Search Central, "Avoid intrusive interstitials"](https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials)).

**Cookie/consent banners are a measured, real source of conversion loss and user annoyance**,
though the specific percentage figures found in this research pass came from marketing-analytics
vendors selling cookieless-analytics alternatives and should be read with that conflict of interest
in mind — **[weakly sourced, vendor-interested]**. The qualitative finding is more solid and
appears in academic "consent fatigue" literature referenced secondhand: banner interruption before
any value is delivered increases bounce, full-screen modal banners cost more engagement than
equal-weight bottom-bar Accept/Reject banners, and mobile screen real estate makes EU-style consent
modals disproportionately costly on the exact device most campaign traffic arrives on
([summarised via cookie-script.com and analytics-alternatives.com](https://cookie-script.com/news/consent-fatigue-strategies-to-improve-user-experience-and-boost-opt-in-rates)).
For FLS this argues for a minimal, equal-weight-buttons, bottom-bar consent pattern rather than a
blocking modal, and for keeping the number of non-essential tracking scripts small enough that the
banner can legitimately be small.

**"We'll be in touch" with no follow-up** was not found addressed as a named UX research topic in
this pass. It belongs more to CRM/lead-management practice than to landing-page design per se, and
is flagged here as a real, credible risk (it directly damages the up-front-disclosure trust factor
in §5 if the promise on the form isn't honoured operationally) rather than as a sourced finding.

---

## 9. Accessibility and performance as conversion factors

**Accessible forms convert better for everyone, not just assistive-technology users** — clear
labels, connected error messages, and logical tab order reduce abandonment across all users, and
missing form labels are the third most common accessibility failure, found on 45% of home pages in
the WebAIM Million dataset (a large-scale automated scan, the strongest empirical source in this
section)
([summarised via WebAIM Million findings, reform.app](https://www.reform.app/blog/wcag-guidelines-accessible-forms)).
WCAG's relevant success criteria are concrete and testable: 1.3.1 (programmatic labels), 3.3.1
(error identification — the field in error must be identified and described in text), 3.3.2
(instructions), 3.3.3 (error suggestion). These are not optional nice-to-haves for a form whose
entire purpose is capturing a lead or an application — a visitor who cannot tell which field failed
validation abandons regardless of ability.

**Page weight and load time have some of the best-evidenced numbers in this entire file**, because
they come from large-scale, methodologically described studies rather than single-case reports.
Google/Deloitte (2020): a 0.1-second mobile speed improvement lifted retail conversions 8.4% and
travel conversions 10.1%. Google (2017): 53% of mobile users abandon a page taking over 3 seconds
to load; bounce probability rises 32% as load time goes 1→3 seconds, and 123% as it goes 1→10
seconds (deep-neural-network model, ~90% prediction accuracy, Google's own methodology)
([Think with Google, mobile page speed research](https://www.thinkwithgoogle.com/_qs/documents/4290/c676a_Google_MobileSiteSpeed_Playbook_v2.1_digital_4JWkGQT.pdf)).
Page weight specifically: as page elements go from 400 to 6,000, conversion probability drops 95%;
70% of pages Google tested exceeded 1MB. This is directly relevant to a landing page brief that
explicitly assumes most traffic is mobile and some of that traffic is on a poor connection
(referral links shared over messaging apps, paid social ads served to a general audience, not just
broadband desktop users) — page weight is not a secondary technical concern for this feature, it is
load-bearing for the conversion numbers everything else in this file assumes.

**Heading structure and focus order** were not found addressed by a landing-page-specific source in
this pass; they follow directly from general WCAG conformance (1.3.1, 2.4.3) and from the
accessible-forms findings above, extended to the whole page rather than sourced separately.

---

## 10. Measurement

**UTM parameters are fragile and commonly broken in ways that quietly corrupt attribution.**
Documented failure modes: inconsistent naming (case, spelling — "Facebook" vs "facebook" splits
data into separate rows), UTMs stripped by in-app browsers, social platforms, email-client link
proxies, and URL shorteners/redirects; and — the failure most relevant to a landing-page-to-form
flow — **UTM parameters live in the browser session and do not automatically travel into a form
submission or CRM record unless explicitly captured and passed through**
([summarised via northbeam.io, dumbdata.co, and cometly.com UTM-mistakes round-ups](https://dumbdata.co/post/costly-utm-tracking-mistakes-that-can-ruin-your-data/)).
For FLS specifically, this means the landing page's job is not done when it records a page-view —
it must persist campaign/referral-source identifiers (UTM values, referral code) into whatever the
CTA leads to (an application, a signup, a contact record), or attribution is lost at exactly the
step that matters. A second documented failure — tagging *internal* links with UTM parameters
overwrites the original external source and creates false new "sessions," corrupting the very
attribution the campaign page exists to produce — is directly relevant if a landing page links to
another FLS page that itself carries tracking.

**The most consequential measurement mistake for this brief specifically is counting the wrong
event.** None of the sources found stated this as a landing-page-specific research finding, but it
follows directly from the UTM-persistence finding above and is uncontroversial: if the metric
counted is "CTA click" rather than "account created" / "application submitted" / "lead record
created," the page can appear to succeed while the underlying multi-step flow silently fails
(§7's login-wall/verification-email friction). Attribution that stops at the click cannot see the
drop-off between promise and delivery — which is precisely the gap this brief's four target
actions are trying to close.

---

## Where FLS brand voice conflicts with standard landing-page practice

This is a real finding, not a stylistic footnote — the idea needs it resolved before copy is
written.

FLS's brand guidelines (`.claude/skills/brand-guidelines/SKILL.md`) explicitly forbid vague
benefit language, unearned superlatives ("powerful", "robust", "cutting-edge" without evidence),
and "SaaS marketing" phrasing, and require every bold claim to have immediate, concrete evidence
("show, don't tell"). Standard landing-page copywriting — as reflected in nearly every source
above — leans on urgency ("limited spots"), superlatives ("the best course for..."), and
benefit-first headlines that assert value before demonstrating it. Three concrete points of
friction:

- **Urgency/scarcity copy, even honest urgency (a real cohort start date, a real application
  deadline), sits close to the FTC-documented dark-pattern territory in §8** if it is not
  scrupulously accurate. FLS's "direct over diplomatic" voice principle and its ban on hype
  actually protects against this failure mode rather than conflicting with it — a real, dated,
  verifiable "cohort starts 3 November, applications close 20 October" is both good brand voice and
  defensible urgency; a vague "enrolment closing soon" is neither.
- **Testimonials and social proof**, standard landing-page practice, need to clear a higher bar
  under FLS voice than under generic marketing practice — "show, don't tell" and the NN/g finding
  that on-site testimonials read as unverifiable (§5) point the same direction: attributed,
  verifiable, specific testimonials (named learner, named outcome, linkable if possible) rather
  than generic enthusiastic pull-quotes.
- **The FTC/deceptive-design findings in §8 and FLS's own brand guardrails ("don't use vague
  benefit language", "acknowledge limitations honestly") are aligned, not in tension** — the
  brand's existing rules already forbid most of what the anti-patterns research warns against. The
  one genuine tension is with the *volume* of persuasive repetition that CXL and Unbounce-style
  practice recommends (repeated CTAs, benefit-led headlines asserting value before evidence) against
  FLS's "teach while you talk" and evidence-first instinct — the resolution implied by the research
  above is achievable: repeat the CTA, but keep every repetition's surrounding copy factual and
  specific rather than escalating in enthusiasm, which is also what §4's "repeat the same CTA, not
  an urgency-escalated one" already recommends.

---

status: ok
