# FreedomLS voice

How FreedomLS sounds, in UI text, error messages, docs, README and marketing.

## Personality

- More **technical** than friendly: developer-to-developer, and open to newcomers.
- More **confident** than humble: clear convictions about learner-first design.
- More **opinionated** than neutral: strong views on pedagogy and portability, flexible on implementation.
- Balanced between **serious** and **playful**: professional with dry wit.
- Slightly more **raw** than polished: substance over style, and still careful.

## Voice principles

1. **Show, don't tell**: back every claim with a specific (a technology, a code example, a number). Rather than calling FreedomLS "extensible", show the snippet that extends it.
2. **Direct over diplomatic**: "FreedomLS stores content as Markdown files", not "FreedomLS leverages an innovative content paradigm."
3. **Teach while you talk**: even marketing copy leaves the reader knowing something new.
4. **Respect the reader's time**: front-load the important information, and prefer a code example to a long explanation.

The tell of copy that has drifted off-voice is SaaS phrasing: "unlock potential", "empower learners", "drive engagement", "cutting-edge", "robust", "scale your learning". When one of those surfaces, replace it with the specific thing it was gesturing at.

## Tone by context

| Context             | Tone |
|---------------------|------|
| GitHub README       | Confident, concise, technical. Lead with what it does, then how. |
| Marketing site      | Slightly warmer, benefit-led, still grounded in specifics. Screenshots are of the real app. |
| Error messages      | Human, brief, helpful. Name the problem, suggest the fix, leave blame out. |
| Docs / tutorials    | Patient, thorough. Assume competence, not familiarity. Include the "why". Contributor docs are written for someone new to Django. |
| Community (Discord) | Casual, collegial, encouraging. Credit contributors by name and welcome first-timers warmly. |
| Conference talks    | Energetic but grounded. Open with a real problem, show real solutions. |

In every context, FreedomLS is a community open-source project: acknowledge its limitations honestly.

## Terminology

The words FreedomLS uses about itself in UI copy, docs and marketing. For the names of models, fields and other code concepts, `Skill(domain-glossary)` is canonical.

| Use this        | Instead of                | Why |
|-----------------|---------------------------|-----|
| extend          | customise                 | A foundation you build on, not a product you tweak |
| content         | curriculum                | Broader, less institutional, no rigid pedagogical assumption |
| learners        | students                  | Works across corporate, self-paced, and academic contexts |
| builders        | administrators            | People who deploy FreedomLS are building, not managing |
| learning system | LMS (where possible)      | Deliberately drops "Management": the system is for learning |
| fork it         | get started               | Culturally resonant, implies ownership from day one |
| foundation      | platform / solution       | Something you build on, not SaaS-speak |
| plain Markdown  | CMS / content management  | Explicit about the format |

## Error messages

Name the specific problem, suggest a specific fix, in plain language. Explain any code you show. Routine actions end on a full stop.

```
✅ "Could not find the course file. Expected a course.md in /courses/my-course/"
❌ "Error: Invalid course configuration detected."

✅ "This email is already registered. Try signing in, or use a different email."
❌ "Error 409: Duplicate entry."

✅ "Progress saved. You're 60% through this module."
❌ "Success! Your learning journey progress has been updated."
```

## Naming

- **Features and apps**: plain, descriptive Django app names like `learner_progress` or `content_engine`. The "freedom" metaphor stays with the product name; features get ordinary names.
- **Releases**: semantic versioning (`v1.2.0`). Optionally, a major release takes a short code name from a place known for learning or free expression ("Alexandria", "Timbuktu"). Keep it subtle.

## Co-branding

- **Powered-by badge**: organisations using FreedomLS may show "Powered by FreedomLS" in a footer or about page, with the logo mark in Ocean or Midnight, at least 120px wide.
- **White-label**: learner-facing UI carries the deploying organisation's brand. FreedomLS attribution belongs in the footer, admin, or about page only.
- **Forks**: use their own branding and show lineage with "built on FreedomLS". A fork's name leaves out "Freedom".

## Sample copy

**Homepage hero:**
> Teach the way your learners need.
>
> Most learning platforms are digital textbooks: linear, rigid, and full of opinions about how learning should work. FreedomLS is an open-source learning system built with Django that lets you shape the platform around your learners, not the other way around.

**GitHub description (one line):**
> An open-source learning system built with Django. Learner-first, Markdown-native, Git-friendly, and endlessly extensible. Not another digital textbook.

**Error page (404):**
> This page doesn't exist — but that's fine, you can build whatever you need. Head back to [your dashboard] or [browse courses].

**Empty state (no courses):**
> No courses yet. Drop some Markdown files into your content directory and add a course.md to get started. [See the docs →]
