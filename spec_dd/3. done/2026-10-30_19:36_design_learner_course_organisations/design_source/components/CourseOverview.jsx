/* Course Overview — shown when a learner opens a course they have NOT enrolled in.
   Surfaces: basic info, what you'll learn, a read-only table of contents, and an
   enrol / apply call-to-action. Two intents:
     mode="enroll" → free / open course, start immediately
     mode="apply"  → cohort-based / advanced course with prerequisites
   Desktop, tablet, and mobile renderers all read from the same COURSE_DATA. */

const OVERVIEW_GRADIENTS = {
  airspace:  "linear-gradient(135deg, #00A8A4 0%, #007570 100%)",
  examiner:  "linear-gradient(135deg, #1A1A2E 0%, #0F0F1F 100%)",
  night:     "linear-gradient(135deg, #14143b 0%, #283593 100%)",
  photogram: "linear-gradient(135deg, #FF6B35 0%, #C43F1A 100%)",
};

/* ---------------- Demo course data ---------------- */
const COURSE_ENROLL = {
  id: "airspace", mode: "enroll", img: "airspace", icon: "map-trifold",
  category: "Foundation", kicker: "Open course · self-paced",
  title: "Airspace Classes for sub-25kg RPAS",
  lead: "Read controlled and uncontrolled airspace with confidence. A focused, self-paced primer on the classes, boundaries, and entry rules that govern every flight you plan under 25 kg.",
  meta: [
    { i: "stack",        k: "Modules",      v: "4 modules" },
    { i: "clock",        k: "Duration",     v: "~2 hours" },
    { i: "chart-line-up",k: "Level",        v: "Beginner" },
    { i: "seal-check",   k: "On completion",v: "Certificate" },
  ],
  price: "Free", priceSub: "Open to all learners",
  about: [
    "Most airspace incidents for small RPAS happen at the boundary between classes — a learner climbs through a shelf they didn't know was there, or assumes uncontrolled airspace where a control zone quietly begins. This course removes that ambiguity.",
    "Across four short modules you'll learn to identify every airspace class relevant to sub-25 kg operations, read the lateral and vertical limits straight from a chart, and know exactly when a call, a clearance, or an authorisation is required before you launch.",
  ],
  outcomes: [
    { h: "Classify any airspace", t: "Distinguish Class A through G and the rules each imposes on RPAS." },
    { h: "Read chart boundaries", t: "Pull lateral and vertical limits directly from a sectional." },
    { h: "Know when to call", t: "Recognise where clearance or authorisation is mandatory." },
    { h: "Plan a compliant route", t: "Pick a corridor that keeps you legal end to end." },
  ],
  modules: [
    { num: "01", title: "Airspace fundamentals", dur: "28 min", lessons: 3, preview: true, sections: [
      { id: "1.1", name: "Controlled vs. uncontrolled airspace", kind: "reading", dur: "8 min", free: true },
      { id: "1.2", name: "The vertical structure of airspace", kind: "video", dur: "11 min", free: true },
      { id: "1.3", name: "Why class matters for RPAS", kind: "reading", dur: "9 min" },
    ]},
    { num: "02", title: "Classes A–G in detail", dur: "42 min", lessons: 4, sections: [
      { id: "2.1", name: "Class C, D and the control zone", kind: "reading", dur: "12 min" },
      { id: "2.2", name: "Class E and transition layers", kind: "reading", dur: "10 min" },
      { id: "2.3", name: "Class G — the default below", kind: "video", dur: "9 min" },
      { id: "2.4", name: "Knowledge check", kind: "quiz", dur: "11 min" },
    ]},
    { num: "03", title: "Reading sectional charts", dur: "36 min", lessons: 3, sections: [
      { id: "3.1", name: "Decoding boundary symbology", kind: "reading", dur: "13 min" },
      { id: "3.2", name: "Shelves, steps and floors", kind: "interactive", dur: "14 min" },
      { id: "3.3", name: "Worked example — a real corridor", kind: "video", dur: "9 min" },
    ]},
    { num: "04", title: "Assessment & certificate", dur: "20 min", lessons: 2, sections: [
      { id: "4.1", name: "Final knowledge assessment", kind: "quiz", dur: "15 min" },
      { id: "4.2", name: "Claim your certificate", kind: "reading", dur: "5 min" },
    ]},
  ],
  instructor: { initials: "RM", name: "Capt. Rorisang Mokoena", role: "Lead Instructor · 4,200 logged hours",
    bio: "Former ATC and RPAS examiner. Rorisang has trained over 1,800 commercial drone pilots across Southern Africa." },
  included: [
    { i: "monitor-play", t: "11 video & reading lessons" },
    { i: "file-text",    t: "Printable chart cheat-sheet" },
    { i: "infinity",     t: "Lifetime access, self-paced" },
    { i: "certificate",  t: "Certificate of completion" },
    { i: "device-mobile",t: "Mobile & offline-ready" },
  ],
  rating: "4.8", ratings: "326 ratings", learners: "2,140 enrolled",
};

const COURSE_APPLY = {
  id: "examiner", mode: "apply", img: "examiner", icon: "graduation-cap",
  category: "Advanced", kicker: "Cohort-based · application required",
  title: "Examiner Pathway",
  lead: "Become a certified RPAS flight examiner. A mentored, cohort-based programme that qualifies you to assess and sign off other pilots — admission by application.",
  meta: [
    { i: "stack",         k: "Modules",   v: "12 modules" },
    { i: "clock",         k: "Duration",  v: "22 hours" },
    { i: "chart-line-up", k: "Level",     v: "Advanced" },
    { i: "users-three",   k: "Format",    v: "Cohort + mentor" },
  ],
  price: "By application", priceSub: "Partner-sponsored seats",
  about: [
    "The Examiner Pathway is the platform's most senior credential. Graduates are authorised to conduct practical assessments, issue competency sign-offs, and represent First Class as accredited examiners.",
    "Because examiners carry regulatory weight, admission is selective. Each cohort is capped, mentored by a serving examiner, and structured around live assessment practice — not self-paced reading. Applicants are reviewed against the prerequisites below before a seat is offered.",
  ],
  outcomes: [
    { h: "Run a practical assessment", t: "Conduct and score a full RPAS flight test to standard." },
    { h: "Apply the competency matrix", t: "Map observed performance to objective criteria." },
    { h: "Give defensible feedback", t: "Document outcomes that withstand appeal and audit." },
    { h: "Carry examiner authority", t: "Sign off candidates as an accredited First Class examiner." },
  ],
  modules: [
    { num: "01", title: "The examiner's role & ethics", dur: "1h 40m", lessons: 4, preview: true, sections: [
      { id: "1.1", name: "What an examiner is accountable for", kind: "reading", dur: "22 min", free: true },
      { id: "1.2", name: "Conflicts, bias and recusal", kind: "video", dur: "26 min" },
      { id: "1.3", name: "Regulatory framework overview", kind: "reading", dur: "30 min" },
      { id: "1.4", name: "Cohort orientation (live)", kind: "interactive", dur: "22 min" },
    ]},
    { num: "02", title: "The competency matrix", dur: "2h 10m", lessons: 5, sections: [
      { id: "2.1", name: "Anatomy of a standard", kind: "reading", dur: "24 min" },
      { id: "2.2", name: "Observable vs. inferred performance", kind: "video", dur: "28 min" },
      { id: "2.3", name: "Scoring boundaries & edge cases", kind: "interactive", dur: "34 min" },
      { id: "2.4", name: "Calibration workshop (live)", kind: "interactive", dur: "30 min" },
      { id: "2.5", name: "Matrix assessment", kind: "quiz", dur: "14 min" },
    ]},
    { num: "03", title: "Conducting the practical test", dur: "2h 25m", lessons: 4, sections: [
      { id: "3.1", name: "Briefing the candidate", kind: "video", dur: "30 min" },
      { id: "3.2", name: "Managing the test environment", kind: "reading", dur: "28 min" },
      { id: "3.3", name: "Intervention & safety calls", kind: "interactive", dur: "40 min" },
      { id: "3.4", name: "Live assessment shadowing", kind: "interactive", dur: "47 min" },
    ]},
    { num: "04", title: "Documentation & appeals", dur: "1h 50m", lessons: 3, sections: [
      { id: "4.1", name: "Writing a defensible report", kind: "reading", dur: "35 min" },
      { id: "4.2", name: "Handling an appeal", kind: "video", dur: "40 min" },
      { id: "4.3", name: "Final examiner board (live)", kind: "interactive", dur: "35 min" },
    ]},
  ],
  moreModulesNote: "+ 8 further modules unlock as the cohort progresses",
  cohort: { starts: "06 Apr 2026", deadline: "Applications close 23 Mar", seats: "9 of 24 seats left" },
  prereqs: [
    { label: "RPAS Standard certified", note: "Completed Feb 2026 · 92%", met: true },
    { label: "150+ logged flight hours", note: "You have 168 logged hours", met: true },
    { label: "Partner sponsorship", note: "Request from your organisation", met: false },
  ],
  instructor: { initials: "AV", name: "Adaeze Veld", role: "Chief Examiner · Programme mentor",
    bio: "Adaeze has signed off more than 600 commercial examiners and chairs the First Class assessment board." },
  included: [
    { i: "users-three",       t: "Capped cohort with live sessions" },
    { i: "chalkboard-teacher",t: "1:1 mentorship from a serving examiner" },
    { i: "drone",             t: "Supervised live assessment practice" },
    { i: "certificate",       t: "Accredited examiner credential" },
    { i: "seal-check",        t: "Listed in the examiner registry" },
  ],
  rating: "4.9", ratings: "48 graduate reviews", learners: "Cohort capped at 24",
};

const KIND_ICON = {
  reading: "file-text", video: "play-circle", quiz: "question",
  interactive: "cursor-click",
};

/* ====================================================================
   DESKTOP
   ==================================================================== */
function CourseOverview({ course = COURSE_ENROLL, onBack, onEnroll, atoBand = null, atoPanel = null, heroBrand = null, heroCorner = null, preHero = null, heroBg = null, heroArt = null, heroClass = "", titleBrand = null }) {
  const [openMod, setOpenMod] = React.useState(course.modules[0].num);
  const isApply = course.mode === "apply";
  const grad = OVERVIEW_GRADIENTS[course.img] || OVERVIEW_GRADIENTS.airspace;
  const totalLessons = course.modules.reduce((n, m) => n + m.lessons, 0);

  return (
    <div className="lxo">
      {/* Back bar */}
      <div className="lxo-backbar">
        <button className="fc-btn fc-btn-ghost fc-btn-sm" onClick={onBack}>
          <i className="ph ph-arrow-left"></i><span>All courses</span>
        </button>
        <div className="crumb">
          <i className="ph ph-caret-right"></i>
          <span>{course.category}</span>
          <i className="ph ph-caret-right"></i>
          <strong>{course.title}</strong>
        </div>
      </div>

      {preHero}
      {/* Hero */}
      <header className={"lxo-hero " + heroClass} style={{ background: heroBg || grad }}>
        <div className="lxo-hero-grid"></div>
        <div className="lxo-hero-glow"></div>
        {heroArt || <i className={`ph-fill ph-${course.icon} lxo-hero-icon`}></i>}
        <div className="lxo-hero-inner">
          {heroCorner}
          {heroBrand}
          <div className="lxo-hero-eyebrow">
            <span>{course.category}</span><span className="sep">·</span><span>{course.kicker}</span>
          </div>
          <div className="lxo-hero-chips">
            {isApply
              ? <><span className="lxo-chip-glass accent"><i className="ph-fill ph-lock-key"></i>Application required</span>
                  <span className="lxo-chip-glass"><i className="ph ph-users-three"></i>Cohort starts {course.cohort.starts}</span></>
              : <><span className="lxo-chip-glass accent"><i className="ph-fill ph-lightning"></i>Free to enrol</span>
                  <span className="lxo-chip-glass"><i className="ph ph-play-circle"></i>Start immediately</span></>}
          </div>
          {titleBrand ? <div className="lxo-title-row">{titleBrand}<h1>{course.title}</h1></div> : <h1>{course.title}</h1>}
          <p className="lxo-hero-lead">{course.lead}</p>
          <div className="lxo-hero-meta">
            {course.meta.map((m) => (
              <div key={m.k} className="lxo-meta-item">
                <i className={`ph ph-${m.i}`}></i>
                <div><div className="k">{m.k}</div><div className="v">{m.v}</div></div>
              </div>
            ))}
          </div>
        </div>
      </header>

      {atoBand ? <div className="lxo-atoband">{atoBand}</div> : null}

      {/* Body */}
      <div className="lxo-body">
        <div className="lxo-main">
          {/* About */}
          <section>
            <h2 className="lxo-sec-title">About this course</h2>
            <div className="lxo-prose">
              {course.about.map((p, i) => <p key={i}>{p}</p>)}
            </div>
          </section>

          {/* Outcomes */}
          <section>
            <h2 className="lxo-sec-title">What you'll learn</h2>
            <div className="lxo-outcomes">
              {course.outcomes.map((o, i) => (
                <div key={i} className="lxo-outcome">
                  <i className="ph-fill ph-check-circle"></i>
                  <span><strong>{o.h}.</strong> {o.t}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Table of contents */}
          <section>
            <div className="lxo-toc-head">
              <h2 className="lxo-sec-title" style={{ margin: 0 }}>Course content</h2>
              <span className="lxo-toc-summary">{course.modules.length} modules · {totalLessons} lessons · {course.meta[1].v.replace("~", "")}</span>
            </div>
            <div className="lxo-toc">
              {course.modules.map((m) => {
                const open = openMod === m.num;
                return (
                  <div key={m.num} className={"lxo-mod" + (open ? " open" : "")}>
                    <button className="lxo-mod-row" onClick={() => setOpenMod(open ? null : m.num)}>
                      <span className="lxo-mod-num">{m.num}</span>
                      <span className="lxo-mod-info">
                        <span className="lxo-mod-title">{m.title}</span>
                        <span className="lxo-mod-meta">
                          <span>{m.lessons} lessons</span><span className="dot"></span><span>{m.dur}</span>
                        </span>
                      </span>
                      {m.preview ? <span className="lxo-mod-preview">Free preview</span> : <span></span>}
                      <i className="ph ph-caret-right lxo-mod-caret"></i>
                    </button>
                    {open && (
                      <div className="lxo-mod-sections">
                        {m.sections.map((s) => (
                          <div key={s.id} className={"lxo-toc-sec" + (s.free ? " free" : "")}>
                            <i className={`ph ph-${KIND_ICON[s.kind]} kind`}></i>
                            <span className="name">{s.name}</span>
                            {s.free ? <span className="freetag">Preview</span> : <i className="ph ph-lock-simple lock"></i>}
                            <span className="dur">{s.dur}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {course.moreModulesNote && (
              <p style={{ fontSize: 13, color: "var(--fg-3)", margin: "12px 4px 0", fontFamily: "var(--font-mono)" }}>
                <i className="ph ph-dots-three-outline"></i> {course.moreModulesNote}
              </p>
            )}
          </section>

          {/* Requirements / prerequisites */}
          <section>
            <h2 className="lxo-sec-title">{isApply ? "Admission prerequisites" : "Before you start"}</h2>
            {isApply ? (
              <div className="lxo-reqs">
                {course.prereqs.map((r, i) => (
                  <div key={i} className="lxo-req">
                    <i className={"ph-fill " + (r.met ? "ph-check-circle met" : "ph-circle unmet")}></i>
                    <span className="label"><strong>{r.label}</strong><span>{r.note}</span></span>
                    <span className={"status " + (r.met ? "met" : "unmet")}>{r.met ? "Met" : "Action needed"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="lxo-reqs">
                <div className="lxo-req">
                  <i className="ph-fill ph-check-circle met"></i>
                  <span className="label"><strong>No prerequisites</strong><span>Open to every learner — beginners welcome.</span></span>
                </div>
                <div className="lxo-req">
                  <i className="ph ph-device-mobile" style={{ color: "var(--color-primary)" }}></i>
                  <span className="label"><strong>Any device</strong><span>Works on desktop, tablet and mobile. Download lessons for offline study.</span></span>
                </div>
              </div>
            )}
          </section>

          {/* Instructor */}
          <section>
            <h2 className="lxo-sec-title">Your instructor</h2>
            <div className="lxo-instructor">
              <div className="lxo-instructor-av">{course.instructor.initials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="name">{course.instructor.name}</div>
                <div className="role">{course.instructor.role}</div>
                <div className="bio">{course.instructor.bio}</div>
              </div>
            </div>
          </section>
        </div>

        {/* Sticky enrol / apply card */}
        <aside className="lxo-aside">
          <div className="lxo-enrol">
            <div className="lxo-enrol-top">
              <div className="lxo-price-row">
                <span className={"lxo-price" + (course.mode === "enroll" ? " free" : "")}>{course.price}</span>
                <span className="lxo-price-sub">{course.priceSub}</span>
              </div>
              <p className="lxo-enrol-note">
                {isApply
                  ? "Submit your application for the next cohort. Our team reviews every applicant within 3 working days."
                  : "Enrol now and the first module opens immediately. Your progress saves automatically."}
              </p>
            </div>

            {isApply && (
              <div className="lxo-cohort">
                <div className="h"><i className="ph-fill ph-calendar-star"></i> Next cohort</div>
                <div className="row"><span>Starts</span><strong>{course.cohort.starts}</strong></div>
                <div className="row"><span>{course.cohort.deadline}</span><strong className="seats">{course.cohort.seats}</strong></div>
              </div>
            )}

            <div className="lxo-cta-wrap">
              <button className={"lxo-cta " + (isApply ? "indigo" : "primary")} onClick={onEnroll}>
                {isApply
                  ? <><i className="ph ph-paper-plane-tilt"></i> Start application</>
                  : <><i className="ph ph-plus-circle"></i> Enrol &amp; start free</>}
              </button>
              <button className="lxo-cta-secondary">
                <i className="ph ph-bookmark-simple"></i> Save for later
              </button>
              <div className="lxo-cta-reassure">
                {isApply
                  ? <><i className="ph ph-info"></i> Applying doesn't commit you to a seat</>
                  : <><i className="ph ph-check-circle"></i> No payment required · cancel anytime</>}
              </div>
            </div>

            <div className="lxo-included">
              <div className="h">{isApply ? "What the programme includes" : "What's included"}</div>
              <ul>
                {course.included.map((x, i) => (
                  <li key={i}><i className={`ph ph-${x.i}`}></i> {x.t}</li>
                ))}
              </ul>
            </div>

            <div className="lxo-enrol-foot">
              <button className="lxo-mini"><i className="ph ph-share-network"></i> Share</button>
              <span className="sep"></span>
              <button className="lxo-mini"><i className="ph ph-question"></i> Ask a question</button>
            </div>
          </div>

          <div className="lxo-proof">
            <div className="stars">★★★★★</div>
            <div className="score">{course.rating} <span style={{ fontWeight: 400, color: "var(--fg-3)", fontSize: 13 }}>/ 5</span></div>
            <div className="count">{course.ratings} · {course.learners}</div>
          </div>

          {atoPanel}
        </aside>
      </div>
    </div>
  );
}

/* ====================================================================
   MOBILE
   ==================================================================== */
function CourseOverviewMobile({ course = COURSE_ENROLL, onBack, onEnroll }) {
  const [openMod, setOpenMod] = React.useState(course.modules[0].num);
  const isApply = course.mode === "apply";
  const grad = OVERVIEW_GRADIENTS[course.img] || OVERVIEW_GRADIENTS.airspace;

  return (
    <div className="lxo-m">
      <div className="lxo-m-bar">
        <button className="lxm-iconbtn" onClick={onBack}><i className="ph ph-arrow-left"></i></button>
        <div className="crumb">{course.category} · <strong>Overview</strong></div>
        <button className="lxm-iconbtn"><i className="ph ph-share-network"></i></button>
      </div>

      <div className="lxo-m-hero" style={{ background: grad }}>
        <div className="grid"></div>
        <i className={`ph-fill ph-${course.icon} bgicon`}></i>
        <div className="lxo-m-hero-inner">
          <div className="lxo-m-eyebrow">{course.kicker}</div>
          <div className="lxo-m-chips">
            {isApply
              ? <><span className="lxo-chip-glass accent"><i className="ph-fill ph-lock-key"></i>Apply</span>
                  <span className="lxo-chip-glass"><i className="ph ph-users-three"></i>{course.cohort.starts}</span></>
              : <><span className="lxo-chip-glass accent"><i className="ph-fill ph-lightning"></i>Free</span>
                  <span className="lxo-chip-glass">{course.category}</span></>}
          </div>
          <h1>{course.title}</h1>
          <p>{course.lead}</p>
        </div>
      </div>

      <div className="lxo-m-metastrip">
        {course.meta.map((m) => (
          <div key={m.k} className="item">
            <i className={`ph ph-${m.i}`}></i>
            <div><div className="k">{m.k}</div><div className="v">{m.v}</div></div>
          </div>
        ))}
      </div>

      <div className="lxo-m-section">
        <h3 className="lxo-m-h">About this course</h3>
        {course.about.map((p, i) => <p key={i}>{p}</p>)}
      </div>

      <div className="lxo-m-section">
        <h3 className="lxo-m-h">What you'll learn</h3>
        <div className="lxo-m-outcomes">
          {course.outcomes.map((o, i) => (
            <div key={i} className="lxo-m-outcome">
              <i className="ph-fill ph-check-circle"></i>
              <span><strong>{o.h}.</strong> {o.t}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="lxo-m-section">
        <h3 className="lxo-m-h">Course content</h3>
        <div className="lxo-m-toc">
          {course.modules.map((m) => {
            const open = openMod === m.num;
            return (
              <div key={m.num} className={"lxo-m-mod" + (open ? " open" : "")}>
                <button className="lxo-m-mod-row" onClick={() => setOpenMod(open ? null : m.num)}>
                  <span className="lxo-m-mod-num">{m.num}</span>
                  <span style={{ minWidth: 0 }}>
                    <span className="lxo-m-mod-title">{m.title}</span>
                    <span className="lxo-m-mod-meta">
                      <span>{m.lessons} lessons · {m.dur}</span>
                      {m.preview && <span className="pv">· Free preview</span>}
                    </span>
                  </span>
                  <i className="ph ph-caret-right lxo-m-mod-caret"></i>
                </button>
                {open && (
                  <div className="lxo-m-mod-secs">
                    {m.sections.map((s) => (
                      <div key={s.id} className={"lxo-m-toc-sec" + (s.free ? " free" : "")}>
                        <i className={`ph ph-${s.free ? KIND_ICON[s.kind] : "lock-simple"} kind`}></i>
                        <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.name}</span>
                        <span className="dur">{s.dur}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {course.moreModulesNote && (
          <p style={{ fontSize: 12, color: "var(--fg-3)", margin: "10px 2px 0", fontFamily: "var(--font-mono)" }}>{course.moreModulesNote}</p>
        )}
      </div>

      {isApply && (
        <div className="lxo-m-cohort">
          <div className="h"><i className="ph-fill ph-calendar-star"></i> Next cohort</div>
          <div className="row"><span>Starts</span><strong>{course.cohort.starts}</strong></div>
          <div className="row"><span>{course.cohort.deadline}</span><strong>{course.cohort.seats}</strong></div>
        </div>
      )}

      <div className="lxo-m-section">
        <h3 className="lxo-m-h">{isApply ? "Admission prerequisites" : "Before you start"}</h3>
        {isApply
          ? course.prereqs.map((r, i) => (
              <div key={i} className="lxo-m-req">
                <i className={"ph-fill " + (r.met ? "ph-check-circle met" : "ph-circle unmet")}></i>
                <span style={{ flex: 1 }}><strong>{r.label}</strong><br /><span style={{ fontSize: 12, color: "var(--fg-3)" }}>{r.note}</span></span>
              </div>
            ))
          : (
            <div className="lxo-m-req">
              <i className="ph-fill ph-check-circle met"></i>
              <span><strong>No prerequisites</strong><br /><span style={{ fontSize: 12, color: "var(--fg-3)" }}>Open to every learner — beginners welcome.</span></span>
            </div>
          )}
      </div>

      <div className="lxo-m-section">
        <h3 className="lxo-m-h">Your instructor</h3>
        <div className="lxo-m-instructor">
          <div className="av">{course.instructor.initials}</div>
          <div style={{ minWidth: 0 }}>
            <div className="name">{course.instructor.name}</div>
            <div className="role">{course.instructor.role}</div>
          </div>
        </div>
      </div>

      {/* Sticky CTA */}
      <div className="lxo-m-cta">
        <div className="price-block">
          <div className={"price" + (course.mode === "enroll" ? " free" : "")}>{course.price}</div>
          <div className="price-sub">{isApply ? course.cohort.seats : "Self-paced"}</div>
        </div>
        <button className={isApply ? "indigo" : "primary"} onClick={onEnroll}>
          {isApply ? <><i className="ph ph-paper-plane-tilt"></i> Apply now</> : <><i className="ph ph-plus-circle"></i> Enrol free</>}
        </button>
      </div>
    </div>
  );
}

/* ====================================================================
   TABLET — desktop layout, single column (uses .lxo.tablet overrides)
   ==================================================================== */
function CourseOverviewTablet({ course = COURSE_ENROLL, onBack, onEnroll, titleBrand = null }) {
  const [openMod, setOpenMod] = React.useState(course.modules[0].num);
  const isApply = course.mode === "apply";
  const grad = OVERVIEW_GRADIENTS[course.img] || OVERVIEW_GRADIENTS.airspace;
  const totalLessons = course.modules.reduce((n, m) => n + m.lessons, 0);

  return (
    <div className="lxo tablet">
      <div className="lxo-backbar">
        <button className="fc-btn fc-btn-ghost fc-btn-sm" onClick={onBack}>
          <i className="ph ph-arrow-left"></i><span>All courses</span>
        </button>
        <div className="crumb"><i className="ph ph-caret-right"></i><strong>{course.title}</strong></div>
      </div>

      <header className="lxo-hero" style={{ background: grad }}>
        <div className="lxo-hero-grid"></div>
        <div className="lxo-hero-glow"></div>
        <i className={`ph-fill ph-${course.icon} lxo-hero-icon`}></i>
        <div className="lxo-hero-inner">
          <div className="lxo-hero-eyebrow"><span>{course.category}</span><span className="sep">·</span><span>{course.kicker}</span></div>
          <div className="lxo-hero-chips">
            {isApply
              ? <><span className="lxo-chip-glass accent"><i className="ph-fill ph-lock-key"></i>Application required</span>
                  <span className="lxo-chip-glass"><i className="ph ph-users-three"></i>Cohort {course.cohort.starts}</span></>
              : <><span className="lxo-chip-glass accent"><i className="ph-fill ph-lightning"></i>Free to enrol</span>
                  <span className="lxo-chip-glass"><i className="ph ph-play-circle"></i>Start immediately</span></>}
          </div>
          {titleBrand ? <div className="lxo-title-row">{titleBrand}<h1>{course.title}</h1></div> : <h1>{course.title}</h1>}
          <p className="lxo-hero-lead">{course.lead}</p>
          <div className="lxo-hero-meta">
            {course.meta.map((m) => (
              <div key={m.k} className="lxo-meta-item">
                <i className={`ph ph-${m.i}`}></i>
                <div><div className="k">{m.k}</div><div className="v">{m.v}</div></div>
              </div>
            ))}
          </div>
        </div>
      </header>

      <div className="lxo-body">
        {/* enrol card first on tablet for prominence */}
        <aside className="lxo-aside" style={{ order: -1 }}>
          <div className="lxo-enrol">
            <div className="lxo-enrol-top">
              <div className="lxo-price-row">
                <span className={"lxo-price" + (course.mode === "enroll" ? " free" : "")}>{course.price}</span>
                <span className="lxo-price-sub">{course.priceSub}</span>
              </div>
              <p className="lxo-enrol-note">
                {isApply ? "Submit your application for the next cohort — reviewed within 3 working days."
                         : "Enrol now and the first module opens immediately."}
              </p>
            </div>
            {isApply && (
              <div className="lxo-cohort">
                <div className="h"><i className="ph-fill ph-calendar-star"></i> Next cohort</div>
                <div className="row"><span>Starts</span><strong>{course.cohort.starts}</strong></div>
                <div className="row"><span>{course.cohort.deadline}</span><strong className="seats">{course.cohort.seats}</strong></div>
              </div>
            )}
            <div className="lxo-cta-wrap">
              <button className={"lxo-cta " + (isApply ? "indigo" : "primary")} onClick={onEnroll}>
                {isApply ? <><i className="ph ph-paper-plane-tilt"></i> Start application</>
                         : <><i className="ph ph-plus-circle"></i> Enrol &amp; start free</>}
              </button>
              <button className="lxo-cta-secondary"><i className="ph ph-bookmark-simple"></i> Save for later</button>
            </div>
            <div className="lxo-included">
              <div className="h">{isApply ? "Programme includes" : "What's included"}</div>
              <ul>{course.included.map((x, i) => <li key={i}><i className={`ph ph-${x.i}`}></i> {x.t}</li>)}</ul>
            </div>
          </div>
        </aside>

        <div className="lxo-main">
          <section>
            <h2 className="lxo-sec-title">About this course</h2>
            <div className="lxo-prose">{course.about.map((p, i) => <p key={i}>{p}</p>)}</div>
          </section>
          <section>
            <h2 className="lxo-sec-title">What you'll learn</h2>
            <div className="lxo-outcomes">
              {course.outcomes.map((o, i) => (
                <div key={i} className="lxo-outcome"><i className="ph-fill ph-check-circle"></i><span><strong>{o.h}.</strong> {o.t}</span></div>
              ))}
            </div>
          </section>
          <section>
            <div className="lxo-toc-head">
              <h2 className="lxo-sec-title" style={{ margin: 0 }}>Course content</h2>
              <span className="lxo-toc-summary">{course.modules.length} modules · {totalLessons} lessons</span>
            </div>
            <div className="lxo-toc">
              {course.modules.map((m) => {
                const open = openMod === m.num;
                return (
                  <div key={m.num} className={"lxo-mod" + (open ? " open" : "")}>
                    <button className="lxo-mod-row" onClick={() => setOpenMod(open ? null : m.num)}>
                      <span className="lxo-mod-num">{m.num}</span>
                      <span className="lxo-mod-info">
                        <span className="lxo-mod-title">{m.title}</span>
                        <span className="lxo-mod-meta"><span>{m.lessons} lessons</span><span className="dot"></span><span>{m.dur}</span></span>
                      </span>
                      {m.preview ? <span className="lxo-mod-preview">Free preview</span> : <span></span>}
                      <i className="ph ph-caret-right lxo-mod-caret"></i>
                    </button>
                    {open && (
                      <div className="lxo-mod-sections">
                        {m.sections.map((s) => (
                          <div key={s.id} className={"lxo-toc-sec" + (s.free ? " free" : "")}>
                            <i className={`ph ph-${KIND_ICON[s.kind]} kind`}></i>
                            <span className="name">{s.name}</span>
                            {s.free ? <span className="freetag">Preview</span> : <i className="ph ph-lock-simple lock"></i>}
                            <span className="dur">{s.dur}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
          <section>
            <h2 className="lxo-sec-title">{isApply ? "Admission prerequisites" : "Before you start"}</h2>
            {isApply ? (
              <div className="lxo-reqs">
                {course.prereqs.map((r, i) => (
                  <div key={i} className="lxo-req">
                    <i className={"ph-fill " + (r.met ? "ph-check-circle met" : "ph-circle unmet")}></i>
                    <span className="label"><strong>{r.label}</strong><span>{r.note}</span></span>
                    <span className={"status " + (r.met ? "met" : "unmet")}>{r.met ? "Met" : "Action needed"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="lxo-reqs">
                <div className="lxo-req">
                  <i className="ph-fill ph-check-circle met"></i>
                  <span className="label"><strong>No prerequisites</strong><span>Open to every learner — beginners welcome.</span></span>
                </div>
              </div>
            )}
          </section>
          <section>
            <h2 className="lxo-sec-title">Your instructor</h2>
            <div className="lxo-instructor">
              <div className="lxo-instructor-av">{course.instructor.initials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="name">{course.instructor.name}</div>
                <div className="role">{course.instructor.role}</div>
                <div className="bio">{course.instructor.bio}</div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  CourseOverview, CourseOverviewMobile, CourseOverviewTablet,
  COURSE_ENROLL, COURSE_APPLY,
});
