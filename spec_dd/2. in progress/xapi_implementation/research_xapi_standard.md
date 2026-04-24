# xAPI (Experience API) Standard - Research Notes

## 1. Core Data Model

An xAPI statement captures a learning experience as **"Actor Verb Object"** with optional Result, Context, and Timestamp. Statements are JSON objects.

| Property | Required | Description | Essential Fields |
|----------|----------|-------------|-----------------|
| **Actor** | Yes | Who did it | `account.homePage` + `account.name` (preferred for LMS; avoids exposing email) |
| **Verb** | Yes | What they did (past tense) | `id` (IRI, e.g. `http://adlnet.gov/expapi/verbs/completed`), `display` (human-readable) |
| **Object** | Yes | What they did it to | `id` (IRI you control), `definition.name`, `definition.type` (activity type IRI) |
| **Result** | No | The outcome | `score` (`scaled`/`raw`/`min`/`max`), `success` (bool), `completion` (bool), `duration` (ISO 8601, e.g. `PT8M30S`) |
| **Context** | No | Situational info | `contextActivities.parent` (e.g. course a topic belongs to), `platform`, `registration` (UUID) |
| **Timestamp** | No | When it happened (ISO 8601). Auto-set by LRS if omitted. Separate `stored` field tracks receipt time. |

Actor identification options: `mbox` (mailto:email), `mbox_sha1sum`, `openid`, or `account` (homePage + name). Use `account` for privacy.

## 2. Lightweight Implementation vs Full Spec

**What FLS needs:**
- Statement generation (emit JSON on events) stored in Django models, not a separate LRS
- Actor via `account` mapped to internal user IDs
- 5-8 standard verbs (see section 3)
- Result + duration for scored activities and time-on-page
- Stable activity IDs mirroring content hierarchy: `https://domain/courses/{slug}/topics/{slug}`

**What to skip:** Full LRS REST API, OAuth, statement forwarding, signed statements, voiding, activity/agent profile APIs, sub-statements, groups as actors.

**Practical storage:** A Django model with queryable columns (`actor_id`, `verb_id`, `object_id`, `timestamp`) plus a `raw_statement` JSONField for future LRS export.

## 3. Common Verbs and Activity Types for LMS

### Verbs (base IRI: `http://adlnet.gov/expapi/verbs/`)

| Verb | FLS Use Case |
|------|-------------|
| `experienced` | Viewed a topic/page |
| `completed` | Finished a topic, form, or course |
| `attempted` | Started a form/assessment |
| `answered` | Answered a specific question |
| `passed` / `failed` | Met or missed passing criteria |
| `interacted` | Engaged with interactive content |
| `registered` | Enrolled in a course |
| `progressed` | Progress percentage changed |

### Activity Types (base IRI: `http://adlnet.gov/expapi/activities/`)

| Type | FLS Mapping |
|------|------------|
| `course` | Course |
| `module` or `lesson` | Topic |
| `assessment` | Form |
| `cmi.interaction` | Individual form question |
| `http://activitystrea.ms/schema/1.0/page` | Content page view |

## 4. Minimal Valid xAPI Statement

```json
{
  "actor": {
    "objectType": "Agent",
    "account": { "homePage": "https://lms.example.com", "name": "user-42" }
  },
  "verb": {
    "id": "http://adlnet.gov/expapi/verbs/experienced",
    "display": { "en-US": "experienced" }
  },
  "object": {
    "id": "https://lms.example.com/courses/python-101/topics/variables",
    "definition": {
      "name": { "en-US": "Variables in Python" },
      "type": "http://adlnet.gov/expapi/activities/lesson"
    }
  }
}
```

**With result and context (form submission):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "actor": {
    "objectType": "Agent",
    "account": { "homePage": "https://lms.example.com", "name": "user-42" }
  },
  "verb": {
    "id": "http://adlnet.gov/expapi/verbs/completed",
    "display": { "en-US": "completed" }
  },
  "object": {
    "id": "https://lms.example.com/courses/python-101/forms/week-1-quiz",
    "definition": {
      "name": { "en-US": "Week 1 Quiz" },
      "type": "http://adlnet.gov/expapi/activities/assessment"
    }
  },
  "result": {
    "score": { "scaled": 0.85, "raw": 17, "min": 0, "max": 20 },
    "success": true,
    "completion": true,
    "duration": "PT12M30S"
  },
  "context": {
    "contextActivities": {
      "parent": [{
        "id": "https://lms.example.com/courses/python-101",
        "definition": { "type": "http://adlnet.gov/expapi/activities/course" }
      }]
    },
    "platform": "Freedom Learning System"
  },
  "timestamp": "2026-03-08T14:30:00Z"
}
```

## 5. Common Criticisms and Practical Issues

1. **Verb/vocabulary fragmentation.** The spec does not mandate specific verbs. Different vendors use different IRIs for the same concept, undermining interoperability. Stick to ADL vocabulary.
2. **IRI verbosity.** Every verb, activity type, and extension key must be an IRI. Creates boilerplate. Teams waste time debating verb choices instead of shipping.
3. **LRS overhead.** The spec assumes a separate LRS infrastructure. For an internal LMS, storing xAPI-shaped data in Django models avoids this cost entirely.
4. **Duration tracking is unreliable.** Browser-based time measurement is imprecise (idle tabs, background windows, crashes). Accept approximations.
5. **Data volume.** Fine-grained tracking generates enormous data. Batch and debounce -- do not emit a statement for every interaction.
6. **No standard analytics.** xAPI defines a data format, not reporting. You must build your own queries, aggregations, and dashboards.
7. **Extensions are a trap.** Tempting to dump custom data into `extensions`, but statements should be meaningful from Actor-Verb-Object alone.
8. **Privacy.** Statements contain PII (actor identity). GDPR requires ability to delete/anonymize. Using `account` with opaque IDs mitigates this.
9. **Limited adoption.** Despite being technically superior to SCORM, xAPI has not displaced it. SCORM's simplicity wins in practice for most use cases.

## References

- [xAPI Spec - Data Model (official)](https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Data.md)
- [xAPI Statements 101](https://xapi.com/statements-101/)
- [Deep Dive: Verbs](https://xapi.com/blog/deep-dive-verb/)
- [ADL xAPI Verbs Repository](https://github.com/adlnet-archive/xAPIVerbs)
- [xAPI Tech Overview](https://xapi.com/tech-overview/)
- [10 Best Practices for xAPI Statements](https://www.learningguild.com/articles/10-best-practices-for-xapi-statements)
- [xAPI in LMS Systems - Integration Guide](https://www.eleapsoftware.com/xapi-in-lms-systems-complete-integration-guide/)
- [OpenLearning xAPI Verbs and Objects](https://help.openlearning.com/t/63ax49/xapi-list-of-statements-verbs-and-objects)
- [Experience API - Wikipedia](https://en.wikipedia.org/wiki/Experience_API)
