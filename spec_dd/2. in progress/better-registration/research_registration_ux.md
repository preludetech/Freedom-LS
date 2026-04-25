# Research: Registration UX Best Practices

Research to inform the better-registration feature. Focused on practical recommendations.

---

## 1. What to Ask at Signup vs Later (Progressive Profiling)

### The core principle
Every additional field at signup reduces conversion. Research consistently shows:
- **Each extra field reduces conversion by ~5-10%** (HubSpot, Formstack studies)
- The optimal signup form has **3-5 fields** max
- Email + password is the minimum viable signup

### Progressive profiling
Collect essential info at signup, then gather more over time:
1. **Signup**: email, password (minimum viable)
2. **Onboarding**: name, role, preferences
3. **First use**: contextual data as needed

### When name IS worth asking at signup
- When the product immediately uses the name (e.g., "Welcome, Sarah!")
- When the name is needed for core functionality (certificates, educator displays)
- When social proof matters (showing real names in cohorts/forums)

### References
- [The Impact of Form Length on Conversions — HubSpot](https://blog.hubspot.com/marketing/form-length)
- [Progressive Profiling — Marketo/Adobe](https://business.adobe.com/blog/basics/progressive-profiling)

---

## 2. Name Field Patterns

### Single "full name" vs first/last split

| Approach | Pros | Cons |
|---|---|---|
| **Single "Name" field** | Simpler, fewer fields, culturally flexible | Hard to extract first/last for addressing, certificates |
| **First + Last** | Standard, easy to use in "Dear {first_name}", certificates | Culturally biased (not all cultures have given/family name split), more fields |

### Cultural considerations
- Many cultures don't follow the Western first/last pattern (e.g., Chinese, Icelandic, Indonesian)
- A single "Name" field is more inclusive but less structured
- **Compromise**: First name required, last name optional

### Recommendation for an LMS
**Use first + last name fields.** LMS platforms need structured names for:
- Certificates and credentials
- Educator-facing student lists
- Communication ("Dear {first_name}")

Make **first name required, last name optional** to balance usability with cultural flexibility.

---

## 3. Minimal Registration Trend

The industry trend is toward reducing signup friction:
- **Email-only** signup (password set later or use magic links)
- **Social login** (Google, GitHub, etc.)
- **Passwordless** auth (email codes, passkeys)

### For FLS
FLS already uses email + password (no username). This is already fairly minimal. Adding name fields is a reasonable addition given the LMS use case, but should be **configurable** so sites can choose their friction level.

---

## 4. Common UX Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| Too many fields | Abandonment | Only ask what's essential now |
| Unclear validation errors | Frustration | Show inline errors next to fields |
| Password requirements hidden until submit | Rage | Show requirements upfront |
| No password visibility toggle | Minor annoyance | Add show/hide toggle |
| Requiring email confirmation field | Friction with no real benefit (users copy-paste) | Consider dropping email2 |
| CAPTCHAs on every signup | Major conversion hit | Use invisible CAPTCHA or honeypots |
| No social login options | Missed conversions | Offer Google/GitHub where appropriate |

### Note on email confirmation fields
FLS currently requires `email2` (email confirmation). Studies show this field **does not meaningfully reduce typos** — users typically copy-paste. Consider making it optional or removing it. However, since FLS uses mandatory email verification, typos are caught during verification anyway.

---

## 5. LMS-Specific Registration Patterns

### What learning platforms typically collect

| Platform | Signup fields |
|---|---|
| **Coursera** | Name, email, password (or Google/Facebook) |
| **edX** | Name, email, password, country |
| **Udemy** | Full name, email, password |
| **Canvas LMS** | Configured by institution — varies widely |
| **Moodle** | Email, password, first name, last name, city, country |

### LMS-specific reasons to collect names at signup
1. **Certificates**: Must show the learner's legal name
2. **Educator views**: Educators need to identify students by name, not email
3. **Communication**: Personalised emails and notifications
4. **Cohort management**: Names are essential for educators managing groups

### Recommendation for FLS
Name collection at signup makes sense for an LMS, but should be **per-site configurable**:
- Sites used for formal education: require first + last name
- Sites used for casual/self-paced learning: name optional, collect later
- Default: require first name, last name optional

---

## Summary of Recommendations

1. **Keep signup minimal** but include name fields for LMS use cases
2. **First name required, last name optional** (configurable per site)
3. **Consider dropping email2** — email verification catches typos anyway
4. **Progressive profiling** for anything beyond email + password + name
5. **Per-site configuration** so each tenant can set their friction level
6. **Inline validation** and clear error messages
