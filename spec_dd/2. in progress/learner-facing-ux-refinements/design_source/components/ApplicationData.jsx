/* Application journey — shared data + small shared bits.
   One learner (Amara Okafor) applying to the Examiner Pathway cohort. */

const APP_META = {
  ref: "FC-EX-2026-0184",
  course: "Examiner Pathway",
  cohort: "Cohort 12 · starts 6 Oct 2026",
  closes: "Applications close 22 Sep 2026",
  fee: "$2,450",
  started: "2 Sep 2026",
  submitted: "3 Sep 2026, 09:14",
};

/* Field values used across review, read-only and status screens */
const APP_VALUES = {
  legalName: "Amara Okafor",
  preferredName: "Amara",
  dob: "14 March 1991",
  email: "amara.okafor@skylift.co",
  phone: "+61 412 887 220",
  address: "18 Grevillea St, Fitzroy VIC 3065",
  licence: "RePL 0091-4477 (CASA)",
  licenceExpiry: "31 Jan 2028",
  ratings: "Multirotor < 25 kg · Fixed-wing < 7 kg · Night VLOS",
  hours: "412 h total · 96 h in last 12 months",
  operator: "SkyLift Surveys Pty Ltd — Chief Remote Pilot",
  incidents: "None reported",
  motivation:
    "I have run SkyLift's internal check-flight programme for three years and currently sign off eight remote pilots a year against our own criteria. Becoming an accredited examiner would let me assess candidates outside the company and remove the bottleneck our regional clients hit when they need a flight test.\n\nI want the competency matrix and the appeal-proof documentation practice most of all — my current write-ups are consistent but they are mine, not the standard.",
  availability: "Weekdays, plus the 11–12 Oct assessment weekend",
};

const APP_DOCS = [
  { nm: "RePL-certificate.pdf", mt: "1.2 MB · uploaded 2 Sep", hint: "PDF, PNG or JPG · max 10 MB", req: "Remote pilot licence", ok: true },
  { nm: "aviation-medical.pdf", mt: "840 KB · uploaded 2 Sep", hint: "PDF or photo · max 10 MB", req: "Class 2 medical", ok: true },
  { nm: "logbook-extract-2026.csv", mt: "31 KB · uploaded 3 Sep", hint: "CSV or PDF export from your logbook", req: "Flight-hours evidence", ok: true },
  { nm: "", mt: "", hint: "Passport or driver licence · whole document visible", req: "Photo ID", ok: false },
];

const APP_STEPS = [
  { n: 1, label: "About you", sub: "Name, contact, address" },
  { n: 2, label: "Licences & experience", sub: "Ratings, hours, operator" },
  { n: 3, label: "Documents", sub: "4 files required" },
  { n: 4, label: "Why you're applying", sub: "Statement & availability" },
  { n: 5, label: "Review & submit", sub: "Check before sending" },
];

/* Status configuration — one entry per post-submission state */
const APP_STATES = {
  draft: {
    tone: "", icon: "pencil-simple", badge: "Draft · not submitted",
    head: "Your application is saved as a draft",
    blurb: "Nothing has been sent yet. Pick up where you left off — step 3 of 5, documents.",
    tl: [
      ["now", "Draft in progress", "Last edited 2 Sep, 21:40. Saved automatically.", "Step 3 of 5"],
      ["todo", "Submit application", "Applications close 22 Sep 2026.", ""],
      ["todo", "Eligibility check", "2–3 working days after submission.", ""],
      ["todo", "Assessment interview", "", ""],
      ["todo", "Decision", "", ""],
    ],
    primary: { label: "Continue application", icon: "arrow-right" },
    secondary: [{ label: "Delete draft", icon: "trash", variant: "ghost" }],
    note: "Drafts are kept for 90 days or until the cohort closes, whichever comes first.",
  },
  review: {
    tone: "review", icon: "clock", badge: "Under review",
    head: "Application submitted — under review",
    blurb: "Admissions has your application. Most decisions land within three working days of the eligibility check.",
    tl: [
      ["done", "Application submitted", "All five sections complete.", "3 Sep, 09:14"],
      ["now", "Eligibility check", "Admissions is verifying your licence and hours against CASA records.", "Started 3 Sep"],
      ["todo", "Assessment interview", "45 minutes, video call. You'll be offered three time slots.", ""],
      ["todo", "Decision", "", ""],
      ["todo", "Enrolment", "", ""],
    ],
    editable: false,
    secondary: [
      { label: "Request a change", icon: "note-pencil", variant: "secondary" },
      { label: "Withdraw application", icon: "x-circle", variant: "ghost" },
    ],
    note: "Your answers are locked while under review. A change request goes to your admissions contact.",
  },
  info: {
    tone: "action", icon: "warning-circle", badge: "Action needed",
    head: "We need one more thing from you",
    blurb: "Your reviewer has asked for a clearer copy of your photo ID before the eligibility check can finish.",
    callout: {
      tone: "warn", icon: "warning-circle", t: "Photo ID needs replacing",
      d: "“The ID you uploaded is cropped — we can't read the expiry date. A photo or scan of the full document is fine.” — Dana Whitmore, Admissions",
      acts: [{ label: "Upload replacement", icon: "upload-simple" }, { label: "Message Dana", icon: "chat-circle", variant: "secondary" }],
    },
    tl: [
      ["done", "Application submitted", "", "3 Sep, 09:14"],
      ["now", "Information requested", "Photo ID re-upload. Requested 4 Sep — respond by 11 Sep.", "4 Sep, 14:02"],
      ["todo", "Eligibility check", "Resumes as soon as you respond.", ""],
      ["todo", "Assessment interview", "", ""],
      ["todo", "Decision", "", ""],
    ],
    primary: { label: "Upload replacement ID", icon: "upload-simple" },
    secondary: [{ label: "Withdraw application", icon: "x-circle", variant: "ghost" }],
    note: "The rest of your application stays locked — only the requested section reopens.",
  },
  interview: {
    tone: "scheduled", icon: "calendar-check", badge: "Assessment booked",
    head: "Your assessment interview is booked",
    blurb: "Eligibility cleared on 5 Sep. Next is a 45-minute video assessment with a senior examiner.",
    callout: {
      tone: "info", icon: "video-camera", t: "Tue 15 Sep 2026, 10:00 AEST · 45 min",
      d: "With Peter Nkemelu, Senior Examiner. Bring your logbook and one assessment write-up you're proud of.",
      acts: [{ label: "Join call", icon: "video-camera" }, { label: "Reschedule", icon: "calendar-blank", variant: "secondary" }],
    },
    tl: [
      ["done", "Application submitted", "", "3 Sep, 09:14"],
      ["done", "Eligibility check passed", "Licence and hours verified.", "5 Sep, 11:20"],
      ["now", "Assessment interview", "Tue 15 Sep, 10:00 AEST · video call.", "Booked 5 Sep"],
      ["todo", "Decision", "Within 3 working days of the interview.", ""],
      ["todo", "Enrolment", "", ""],
    ],
    secondary: [
      { label: "Reschedule interview", icon: "calendar-blank", variant: "secondary" },
      { label: "Withdraw application", icon: "x-circle", variant: "ghost" },
    ],
    note: "Your answers are locked. Ask your contact if something material has changed.",
  },
  offer: {
    tone: "offer", icon: "check-circle", badge: "Offer made",
    head: "You've been accepted onto Cohort 12",
    blurb: "Accept your seat to start on 6 October. Seats not accepted by 20 Sep are released to the waitlist.",
    callout: {
      tone: "success", icon: "seal-check", t: "Offer expires 20 Sep 2026",
      d: "Accepting confirms your place and the $2,450 programme fee. You can pay in full or in three instalments.",
      acts: [{ label: "Accept seat", icon: "check" }, { label: "Decline offer", icon: "x", variant: "ghost" }],
    },
    tl: [
      ["done", "Application submitted", "", "3 Sep, 09:14"],
      ["done", "Eligibility check passed", "", "5 Sep, 11:20"],
      ["done", "Assessment interview", "Recommended by Peter Nkemelu.", "15 Sep, 10:00"],
      ["now", "Offer made", "Accept by 20 Sep to hold your seat.", "16 Sep, 08:30"],
      ["todo", "Enrolment", "Course opens 6 Oct 2026.", ""],
    ],
    primary: { label: "Accept my seat", icon: "check", variant: "accent" },
    secondary: [{ label: "Decline offer", icon: "x-circle", variant: "ghost" }],
    note: "Nothing is charged until you accept.",
  },
  payment: {
    tone: "payment", icon: "credit-card", badge: "Payment pending",
    head: "Seat held — payment outstanding",
    blurb: "You accepted on 16 Sep. Your seat is held for 7 days while the first instalment clears.",
    callout: {
      tone: "warn", icon: "credit-card", t: "$816.67 due by 23 Sep 2026",
      d: "Instalment 1 of 3. The course unlocks as soon as the first payment is received.",
      acts: [{ label: "Pay now", icon: "credit-card" }, { label: "Change plan", icon: "arrows-left-right", variant: "secondary" }],
    },
    tl: [
      ["done", "Assessment interview", "", "15 Sep, 10:00"],
      ["done", "Offer accepted", "You confirmed your seat.", "16 Sep, 12:05"],
      ["now", "Payment", "Instalment 1 of 3 — $816.67 due 23 Sep.", ""],
      ["todo", "Enrolment", "Course opens 6 Oct 2026.", ""],
    ],
    primary: { label: "Pay $816.67", icon: "credit-card", variant: "accent" },
    secondary: [{ label: "Download invoice", icon: "file-arrow-down", variant: "secondary" }],
    note: "Seats are released if the first instalment isn't received within 7 days of accepting.",
  },
  wait: {
    tone: "wait", icon: "hourglass-medium", badge: "Waitlisted",
    head: "You're on the waitlist for Cohort 12",
    blurb: "Your application met every requirement — Cohort 12 filled first. You're 3rd in line and carried forward automatically.",
    callout: {
      tone: "info", icon: "hourglass-medium", t: "Position 3 of 9",
      d: "Seats usually open in the two weeks before a cohort starts. You can also move your application to Cohort 13 (starts 2 Feb 2027) and keep your assessment result.",
      acts: [{ label: "Move to Cohort 13", icon: "arrow-right" }, { label: "Stay on waitlist", icon: "check", variant: "secondary" }],
    },
    tl: [
      ["done", "Application submitted", "", "3 Sep, 09:14"],
      ["done", "Eligibility check passed", "", "5 Sep, 11:20"],
      ["done", "Assessment interview", "Recommended.", "15 Sep, 10:00"],
      ["now", "Waitlisted", "Position 3 of 9 for Cohort 12.", "16 Sep, 08:30"],
      ["todo", "Offer", "If a seat is released before 6 Oct.", ""],
    ],
    secondary: [
      { label: "Move to Cohort 13", icon: "arrow-right", variant: "secondary" },
      { label: "Withdraw application", icon: "x-circle", variant: "ghost" },
    ],
    note: "We'll email and text you the moment a seat opens. You get 48 hours to accept.",
  },
  declined: {
    tone: "declined", icon: "x-circle", badge: "Not successful",
    head: "Your application wasn't successful this time",
    blurb: "Cohort 12 required 500 logged hours; your verified total is 412. Everything else met the standard.",
    callout: {
      tone: "err", icon: "info", t: "You can reapply for Cohort 13 from 1 Dec 2026",
      d: "Your assessment result and uploaded documents are kept on file, so reapplying is a short form. Fly the remaining 88 hours and log them in your extract.",
      acts: [{ label: "See what to do next", icon: "arrow-right" }, { label: "Talk to admissions", icon: "chat-circle", variant: "secondary" }],
    },
    tl: [
      ["done", "Application submitted", "", "3 Sep, 09:14"],
      ["done", "Eligibility check", "Hours below the 500 h cohort minimum.", "5 Sep, 11:20"],
      ["done", "Decision: not successful", "Reviewed by Dana Whitmore.", "8 Sep, 16:45"],
      ["todo", "Reapply", "Cohort 13 opens 1 Dec 2026.", ""],
    ],
    primary: { label: "Plan my reapplication", icon: "arrow-right", variant: "secondary" },
    note: "A full reviewer note is attached below. You may request a review of the decision within 14 days.",
  },
  withdrawn: {
    tone: "", icon: "x-circle", badge: "Withdrawn",
    head: "You withdrew this application",
    blurb: "Withdrawn on 9 Sep. Nothing was charged and your seat consideration ended.",
    tl: [
      ["done", "Application submitted", "", "3 Sep, 09:14"],
      ["done", "Eligibility check passed", "", "5 Sep, 11:20"],
      ["done", "Withdrawn by you", "Reason given: timing doesn't work this year.", "9 Sep, 10:02"],
    ],
    primary: { label: "Start a new application", icon: "arrow-clockwise", variant: "secondary" },
    note: "Your answers and documents stay on file for 12 months — a new application pre-fills from them.",
  },
};

const AppBadge = ({ state, sm }) => {
  const s = APP_STATES[state];
  return (
    <span className={`lxa-badge ${s.tone}${sm ? " sm" : ""}`}>
      <i className={`ph-fill ph-${s.icon}`}></i>{s.badge}
    </span>
  );
};

const AppCallout = ({ c }) => (
  <div className={`lxa-callout ${c.tone}`}>
    <i className={`ph-fill ph-${c.icon} lead`}></i>
    <div>
      <div className="t">{c.t}</div>
      <div className="d">{c.d}</div>
      {c.acts ? (
        <div className="acts">
          {c.acts.map((a, i) => (
            <button key={i} className={`fc-btn fc-btn-${a.variant || "primary"} fc-btn-sm`}>
              <i className={`ph ph-${a.icon}`}></i><span>{a.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  </div>
);

const AppTimeline = ({ items }) => (
  <div className="lxa-tl">
    {items.map(([st, t, d, when], i) => (
      <div key={i} className={`lxa-tl-item ${st}`}>
        <div className="lxa-tl-dot">
          <i className={`ph${st === "done" ? "-fill ph-check" : st === "now" ? "-fill ph-circle" : " ph-circle"}`}></i>
        </div>
        <div>
          <div className="t">{t}</div>
          {d ? <div className="d">{d}</div> : null}
          {when ? <div className="when">{when}</div> : null}
        </div>
      </div>
    ))}
  </div>
);

Object.assign(window, { APP_META, APP_VALUES, APP_DOCS, APP_STEPS, APP_STATES, AppBadge, AppCallout, AppTimeline });
