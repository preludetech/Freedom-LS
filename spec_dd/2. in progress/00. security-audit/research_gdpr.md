# GDPR Research for Freedom Learning System

This document covers GDPR (General Data Protection Regulation) requirements specifically relevant to FLS as an installable Django-based LMS. The focus is on practical, code-level requirements rather than organizational/legal process.

Reference: The full GDPR text is at https://gdpr-info.eu/

---

## 1. Data Subject Rights That Must Be Implemented in Code

GDPR Articles 15-22 define rights that require technical implementation. For an LMS handling student data, all of these are relevant.

### Right of Access (Article 15)

The data subject has the right to obtain a copy of all personal data being processed about them, along with metadata about the processing.

**What FLS must provide:**

- An endpoint where authenticated users can request a full export of their data
- The export must include ALL personal data across all models:
  - `accounts.User`: email, first_name, last_name, date_joined, last_login
  - `student_management.CohortMembership`: cohort assignments
  - `student_management.UserCourseRegistration`: course enrollments and timestamps
  - `student_progress.TopicProgress`: topic completion records, timestamps
  - `student_progress.FormProgress`: form attempts, scores, completion times
  - `student_progress.QuestionAnswer`: individual answers (text_answer, selected_options)
  - `student_progress.CourseProgress`: overall course progress percentages
  - `student_management.RecommendedCourse`: recommendations made for the user
  - `student_management.StudentDeadline`: individual deadlines
  - `student_management.UserCohortDeadlineOverride`: deadline overrides
  - `webhooks.WebhookEvent`: any webhook payloads that contain the user's data (user_email, user_id)
- The export must also include information about: purposes of processing, categories of data, recipients (e.g. webhook endpoints receiving user data), retention periods, and the source of the data
- Response must be provided "without undue delay" and within one month (extendable by two months for complex requests)

Reference: https://gdpr-info.eu/art-15-gdpr/

### Right to Erasure / Right to Be Forgotten (Article 17)

The data subject can request deletion of all personal data. This is the most technically complex right for an LMS because educational records have legitimate retention needs.

**What FLS must provide:**

- An endpoint to request account deletion
- Deletion must cascade through ALL related models (Django's `on_delete=models.CASCADE` on User FK handles much of this, but must be verified)
- Special considerations for FLS:
  - `QuestionAnswer.text_answer` contains free-text responses that are personal data
  - `FormProgress.scores` in JSONField may contain identifiable patterns
  - `WebhookEvent.payload` stores user_email and user_id - these must be scrubbed or the events deleted
  - `WebhookDelivery.last_response_body` might contain personal data reflected back from external services
- **Anonymization as alternative to deletion**: Where aggregate educational statistics need to be retained (e.g., course completion rates), anonymize rather than delete. Replace user FK with null (requires `null=True` on FK) or replace with a sentinel "deleted user" record
- Deletion may be refused when processing is necessary for compliance with a legal obligation, or for the establishment/exercise/defense of legal claims. Educational institutions often have legal retention requirements

Reference: https://gdpr-info.eu/art-17-gdpr/

### Right to Data Portability (Article 20)

The data subject has the right to receive their data in a "structured, commonly used and machine-readable format."

**What FLS must provide:**

- Export in JSON or CSV format (JSON is preferred for nested data like form answers with selected options)
- The export should be comprehensive enough that the data could theoretically be imported into another LMS
- This overlaps significantly with the Right of Access export, but portability specifically requires machine-readable format

Reference: https://gdpr-info.eu/art-20-gdpr/

### Right to Rectification (Article 16)

The data subject can request correction of inaccurate personal data.

**What FLS must provide:**

- Users must be able to edit their own profile data (email, first_name, last_name)
- For data they cannot directly edit (e.g., cohort assignments, course registrations made by educators), there must be a process to request corrections
- This is largely a UI/workflow concern rather than a new technical feature - profile editing views satisfy most of this

Reference: https://gdpr-info.eu/art-16-gdpr/

### Right to Restriction of Processing (Article 18)

The data subject can request that processing of their data be restricted (data kept but not used) in certain circumstances.

**What FLS must provide:**

- A mechanism to "freeze" a user's data - keep it stored but prevent it from being used in reports, analytics, or webhook payloads
- The simplest implementation is a boolean flag on the User model: `processing_restricted = BooleanField(default=False)`
- When set, the system should exclude this user from: educator progress reports, webhook event payloads, any aggregated analytics

Reference: https://gdpr-info.eu/art-18-gdpr/

### Right to Object (Article 21)

The data subject can object to processing based on legitimate interests or for direct marketing.

**What FLS must provide:**

- For an LMS, the main scenario is objecting to automated profiling based on assessment results (e.g., the `RecommendedCourse` feature that creates recommendations based on form responses)
- Users should be able to opt out of automated recommendation/profiling features

Reference: https://gdpr-info.eu/art-21-gdpr/

---

## 2. Consent Management Requirements

GDPR Articles 6-7 set strict rules on consent. For an LMS, consent is one of several possible legal bases for processing.

### Legal Basis for Processing

Not all LMS data processing requires consent. The six legal bases (Article 6) are:

1. **Consent** - freely given, specific, informed, unambiguous
2. **Contract** - necessary for performing a contract (e.g., providing the LMS service the user signed up for)
3. **Legal obligation** - required by law (e.g., educational record-keeping requirements)
4. **Vital interests** - protecting someone's life (rarely applicable to LMS)
5. **Public task** - necessary for a task in the public interest (may apply to public educational institutions)
6. **Legitimate interests** - necessary for legitimate interests of the controller (e.g., security logging)

**For FLS specifically:**

- Core LMS functionality (progress tracking, form completion, course access) can be justified under **contract** - the user signed up to use the LMS
- Analytics, profiling, and recommendations likely need **consent** or **legitimate interest** with a balancing test
- Sending user data via webhooks to third parties requires either **consent** or a clear **legitimate interest** with user notification
- Security logging can use **legitimate interest**

### Explicit Consent Requirements

When consent IS the legal basis, GDPR requires (Article 7):

**What FLS must provide:**

- A `ConsentRecord` model to track what the user consented to, when, and how
- Consent must be **granular** - separate consent for separate purposes. A single "I agree to everything" checkbox is non-compliant
- Consent must be **freely given** - cannot be a condition of using the core service. Users must be able to use the LMS without consenting to non-essential processing
- Consent must be as easy to withdraw as to give (Article 7(3))

### Withdrawal of Consent

- A settings page where users can view and toggle each consent type
- Withdrawal must take effect immediately - if a user withdraws consent for webhook data sharing, their data must stop being included in webhook payloads immediately
- Withdrawal must not affect the lawfulness of processing that already occurred before withdrawal

Reference: https://gdpr-info.eu/art-7-gdpr/

---

## 3. Data Protection by Design and by Default (Article 25)

This article requires that data protection is built into the system architecture, not bolted on afterward.

### By Design

Technical measures that must be embedded in the code:

- **Data minimization in queries**: Only select the fields you need. Use `.values()` or `.only()` where full model instances aren't needed
- **Purpose limitation**: Data collected for one purpose shouldn't be repurposed without a new legal basis. The data model should make the purpose of each field clear
- **Pseudonymization where possible**: For analytics and reporting, use user IDs rather than emails/names. The xAPI learning record store (currently stubbed out) should use pseudonymous agent identifiers
- **Access controls**: FLS's site-aware model pattern already provides data isolation between sites. Educator views should only show data for students in their cohorts
- **Automated data lifecycle**: Implement retention policies - old progress records, webhook events, and delivery logs should be automatically purged after a configured retention period

### By Default

The strictest privacy settings must be the default:

- New features that involve data sharing (webhooks, analytics) should default to OFF
- The minimum amount of personal data should be collected. FLS already follows this - the User model only has email, first_name, last_name
- Data should only be accessible to those who need it. Educator views should be scoped to relevant cohorts only

Reference: https://gdpr-info.eu/art-25-gdpr/

---

## 4. Data Breach Notification (Articles 33-34)

### The 72-Hour Rule

If a personal data breach occurs, the data controller must notify the supervisory authority within 72 hours of becoming aware of it, unless the breach is unlikely to result in a risk to individuals.

### What FLS Must Support

FLS is an installable library, not a hosted service, so the deploying organization is the data controller. FLS should provide:

- **Security event logging**: Log all authentication events (login success/failure, password changes, account lockouts), permission violations, and data access patterns
- **Anomaly detection hooks**: Provide signals or hooks that deployers can connect to their monitoring systems
- **Breach assessment data**: When a breach is suspected, the controller needs to know: what data was affected, how many data subjects, what the likely consequences are. FLS should provide management commands or admin views to quickly assess the scope of a potential breach
- **Documentation**: FLS should document what data it stores, where, and in what format, so deployers can complete breach notifications

### High-Risk Breaches (Article 34)

If a breach is likely to result in a high risk to individuals, the affected data subjects must also be notified directly. FLS should provide:

- A mechanism to send breach notification emails to affected users
- Template for breach notification that includes: nature of the breach, contact details of the DPO, likely consequences, measures taken

Reference: https://gdpr-info.eu/art-33-gdpr/ and https://gdpr-info.eu/art-34-gdpr/

---

## 5. Data Protection Impact Assessment (DPIA) - Article 35

A DPIA is required when processing is "likely to result in a high risk to the rights and freedoms of natural persons."

### When a DPIA Is Needed for an LMS

A DPIA is **likely required** when FLS is used for:

- **Systematic monitoring of students**: Progress tracking, time-on-task monitoring, quiz scoring with automated pass/fail decisions
- **Processing children's data**: If the LMS is used for learners under 16
- **Large-scale processing of educational data**: Deployers with many students
- **Automated decision-making**: If quiz scores or form results trigger automatic actions (e.g., `RecommendedCourse` generation, pass/fail determinations)
- **Combining datasets**: If FLS data is combined with other data sources via webhooks

### What FLS Should Provide for DPIA

Since the deploying organization performs the DPIA, FLS should provide:

- **Data inventory documentation**: A complete list of all personal data fields, their purposes, retention periods, and legal bases
- **Data flow diagrams**: How personal data moves through the system
- **Technical security measures documentation**: What FLS implements (encryption, access controls, site isolation)
- **Configuration options for risk mitigation**: Ability to disable features that increase risk (webhooks, profiling/recommendations)

Reference: https://gdpr-info.eu/art-35-gdpr/

---

## 6. Privacy by Design Patterns for Django Applications

### Pattern 1: Configurable Data Collection

```python
# settings.py - let deployers control what data is collected
FLS_PRIVACY = {
    "COLLECT_IP_ADDRESSES": False,  # Default to not collecting
    "WEBHOOK_INCLUDE_PII": False,   # Default to pseudonymous
    "PROGRESS_RETENTION_DAYS": 365 * 3,  # 3 years default
    "WEBHOOK_LOG_RETENTION_DAYS": 90,
    "ENABLE_RECOMMENDATIONS": True,
    "ANONYMIZE_DELETED_USERS": True,  # vs hard delete
}
```

### Pattern 2: Privacy-Aware Webhook Payloads

The current `UserCourseRegistration.save()` includes `user_email` in webhook payloads. This should be conditional:

```python
# Only include personal data in webhooks if configured
def build_webhook_payload(event_type, user, data):
    payload = {**data}
    if not getattr(settings, 'WEBHOOK_INCLUDE_PII', False):
        payload.pop('user_email', None)
        payload['user_id'] = str(user.id)  # UUID is pseudonymous
    return payload
```

### Pattern 3: Retention-Aware Models

```python
class RetentionMixin(models.Model):
    retention_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @classmethod
    def purge_expired(cls):
        cls.objects.filter(retention_expires_at__lt=timezone.now()).delete()
```

### Pattern 4: Audit Trail for Personal Data Access

```python
class DataAccessLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    accessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)
```

---

## 7. Cookie Consent and HTMX/Django Interaction

### Cookie Consent Requirements

The ePrivacy Directive requires consent before setting non-essential cookies. GDPR reinforces this.

**Cookie categories:**

1. **Strictly necessary** (no consent needed): Django session cookie (`sessionid`), CSRF cookie (`csrftoken`)
2. **Functional** (consent needed in strict interpretation): Language preferences, UI state
3. **Analytics** (consent always needed): Google Analytics, Matomo, etc.
4. **Marketing** (consent always needed): Not typically relevant for an LMS

### HTMX-Specific Considerations

- The `csrftoken` cookie is **strictly necessary** - no consent needed
- The `sessionid` cookie is **strictly necessary** for authenticated users - no consent needed
- HTMX itself does not set cookies, but it makes requests that carry cookies
- If analytics cookies are loaded, HTMX requests will also send those cookies. The cookie consent banner must be shown BEFORE any analytics scripts are loaded

**Key rule**: Do not load analytics JavaScript until the user has given consent. With HTMX, this means the analytics `<script>` tags should be conditionally rendered in the base template.

**Django packages for cookie consent:**
- `django-cookie-consent` (https://github.com/jazzband/django-cookie-consent) - mature, maintained by Jazzband
- Custom middleware approach is also viable given FLS's existing middleware patterns

Reference: https://gdpr-info.eu/art-6-gdpr/, Directive 2002/58/EC Article 5(3)

---

## 8. Data Processing Agreements for an Installable LMS

### FLS as Software, Not a Processor

Since FLS is an installable library (not a hosted service), FLS itself is **neither controller nor processor** - it is software. However:

### What FLS Must Document

Under Article 28, when a controller uses a processor, they need a Data Processing Agreement (DPA). FLS should provide:

1. **Data processing documentation** that deployers can use in their DPAs with hosting providers:
   - Complete inventory of personal data fields and their purposes
   - Data flows (what enters, what's stored, what leaves via webhooks)
   - Technical security measures implemented in code
   - Sub-processing: webhooks send data to third-party URLs, which constitutes sub-processing

2. **Configuration guidance for compliance**:
   - How to configure retention periods
   - How to disable features that increase processing scope (webhooks, analytics)
   - What environment variables control security settings

3. **DPA template language** that deployers can adapt

### Webhook-Specific DPA Concerns

FLS's webhook system sends personal data (user_email, user_id) to external URLs. This means:

- The organization receiving webhook data is either a joint controller or a processor
- The deploying organization must have a DPA with each webhook recipient
- FLS should provide clear documentation about what data is sent in each webhook event type
- FLS should provide configuration to control what personal data is included in webhook payloads

Reference: https://gdpr-info.eu/art-28-gdpr/

---

## 9. Specific GDPR Requirements for Educational/Student Data

### Children's Data (Article 8)

If FLS is used with learners under 16:

- **Parental consent is required** for information society services offered directly to children
- The controller must make "reasonable efforts" to verify that consent is given by the parent/guardian
- Privacy notices must be written in language a child can understand

### Special Category Data (Article 9)

Assessment results and learning progress can reveal information about a student's intellectual abilities, learning disabilities, or mental health. While not explicitly listed as "special category data" in Article 9, some interpretations consider detailed learning analytics to be sensitive.

**FLS implications:**

- `FormProgress.scores` and `QuestionAnswer` data should be treated as sensitive
- Access to this data should be restricted to educators with a legitimate need
- Extra caution with webhook payloads that include scores or assessment results

### Profiling Students (Article 22)

Automated decision-making that produces legal effects or similarly significant effects requires:

- Explicit consent, or necessity for a contract, or authorization by law
- The right to human intervention
- The right to contest the decision

**FLS implications:**

- The `RecommendedCourse` feature generates automated recommendations. If these have significant effects (e.g., determining educational pathways), Article 22 may apply
- Quiz pass/fail determinations that gate access to further content could be considered automated decisions
- Deployers should be able to configure whether automated decisions can be contested and reviewed by educators

### The Education Exception

Many EU member states have specific laws for educational data processing:

- Educational institutions can often process student data under **public task** (Article 6(1)(e)) without needing individual consent for core educational activities
- However, non-essential processing (analytics, third-party sharing via webhooks, profiling) still typically requires consent
- Retention periods for educational records are often set by national education law

---

## 10. Technical Measures Required

### Encryption in Transit (Article 32)

- **TLS/HTTPS is mandatory** for any system processing personal data
- Django settings: `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- HSTS headers: `SECURE_HSTS_SECONDS = 31536000`
- Webhook URLs must use HTTPS (FLS already enforces this in `WebhookEndpoint.clean()` when not in DEBUG mode)

### Encryption at Rest (Article 32)

- **Database-level encryption**: PostgreSQL 17 supports TDE via extensions (deployment concern)
- **Field-level encryption**: For highly sensitive fields, consider `django-encrypted-model-fields`. Candidates in FLS:
  - `QuestionAnswer.text_answer` (free-text student responses)
  - `WebhookEndpoint.secret` (stored in plaintext - should be encrypted)
  - `User.email` (if required by deployment context)
- **Backup encryption**: Document that database backups must be encrypted

### Pseudonymization (Article 4(5), Article 25)

- Use UUIDs as primary keys rather than sequential integers
- For analytics exports, replace user identifiers with pseudonymous IDs
- xAPI learning records should use pseudonymous agent identifiers by default
- Webhook payloads should use user_id (UUID) rather than user_email by default

### Access Controls (Article 32)

- **Role-based access**: Educators should only see progress data for students in their cohorts
- **Principle of least privilege**: API authentication keys should have scoped permissions
- **Session management**: Enforce session timeouts, invalidate sessions on password change

### Regular Testing (Article 32(1)(d))

GDPR requires "a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational measures."

- Security-focused test suite (test access controls, data export, deletion cascades)
- Pre-commit hooks for security scanning
- CI pipeline for automated security testing
- Documentation for deployers on running security assessments

Reference: https://gdpr-info.eu/art-32-gdpr/

---

## Summary: Priority Implementation for FLS

### Must-Have (legally required, high risk if missing)

1. **Data export endpoint** (Right of Access + Portability)
2. **Account deletion** (Right to Erasure) with proper cascade
3. **Privacy policy / data processing documentation**
4. **Consent management for non-essential processing** (webhooks, recommendations)
5. **Configurable webhook PII inclusion** (default to pseudonymous)
6. **Data retention management command**
7. **Security event logging**

### Should-Have (best practice, expected by DPAs)

8. **Cookie consent mechanism**
9. **Consent withdrawal mechanism**
10. **Data processing restriction flag**
11. **Audit trail for educator data access**
12. **Encrypted sensitive fields**

### Nice-to-Have (mature compliance, differentiator)

13. **DPIA template** for deployers
14. **Breach notification tooling**
15. **Automated data lifecycle**
16. **Anonymization utilities**
17. **Age verification / parental consent flow**

---

## Key References

- GDPR Full Text: https://gdpr-info.eu/
- Article 6 - Lawfulness of processing: https://gdpr-info.eu/art-6-gdpr/
- Article 7 - Conditions for consent: https://gdpr-info.eu/art-7-gdpr/
- Article 8 - Child's consent: https://gdpr-info.eu/art-8-gdpr/
- Article 15 - Right of access: https://gdpr-info.eu/art-15-gdpr/
- Article 17 - Right to erasure: https://gdpr-info.eu/art-17-gdpr/
- Article 20 - Right to data portability: https://gdpr-info.eu/art-20-gdpr/
- Article 22 - Automated decision-making: https://gdpr-info.eu/art-22-gdpr/
- Article 25 - Data protection by design: https://gdpr-info.eu/art-25-gdpr/
- Article 28 - Processor: https://gdpr-info.eu/art-28-gdpr/
- Article 32 - Security of processing: https://gdpr-info.eu/art-32-gdpr/
- Article 33 - Breach notification to authority: https://gdpr-info.eu/art-33-gdpr/
- Article 34 - Breach notification to data subject: https://gdpr-info.eu/art-34-gdpr/
- Article 35 - Data protection impact assessment: https://gdpr-info.eu/art-35-gdpr/
- EU Cookie Consent (ePrivacy Directive): Directive 2002/58/EC, Article 5(3)
- ICO (UK) Guide to GDPR: https://ico.org.uk/for-organisations/guide-to-data-protection/guide-to-the-general-data-protection-regulation-gdpr/
- Django Cookie Consent package: https://github.com/jazzband/django-cookie-consent
- Django Encrypted Fields: https://github.com/lanshark/django-encrypted-model-fields
