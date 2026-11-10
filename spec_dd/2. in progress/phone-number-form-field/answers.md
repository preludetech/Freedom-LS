# Answers: phone-number-form-field

Asked by `/sdd:start` before the spec was written.

- Q: Which signal should pick the default country code? → A: The browser locale (the region in the Accept-Language header, e.g. en-ZA → +27). No IP geolocation. (asked up front)
- Q: Where should a per-site default country live? → A: Superseded by the next answer. The user first chose a per-site record, then suggested an organisation setting, then dropped both. (asked up front)
- Q: As an organisation setting, what applies when the person filling the form has no organisation or several? → A: Use the browser locale only. There is no organisation or site setting for the phone number's default country. When the locale gives no region, no country is preselected. (asked up front)
- Q: How strict should phone validation be? → A: Strict. Accept only numbers that pass `phonenumbers.is_valid_number`, not merely possible ones. (asked while the research ran)
- Q: What should the phone question's country key and parameters be called? → A: `phone_country_<id>` (outside the `question_` prefix the exam runner counts), and "country" rather than "region" throughout. (spec review)
- Q: Accept letters (vanity numbers) in a phone answer? → A: No, reject them. (spec review)
- Q: Apply the feasibility review's other recommended fixes? → A: Yes, all of them. (spec review)
- Q: Trim duplication flagged by the cut-list review? → A: Yes, keeping both open questions as assumed defaults. (spec review)
