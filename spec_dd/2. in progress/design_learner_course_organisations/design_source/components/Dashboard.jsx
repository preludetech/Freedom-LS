/* Dashboard — the learner's home. Multiple course states grouped logically. */
const Dashboard = ({ onContinue, onOpenCourse, onPreviewCourse, density = "comfortable", heroVariant = "single", courseNote = null, appsSlot = null, applyAction = null, applied = {}, brand = null }) => {
  // ---- Demo data ----
  const continueCard = {
    id: "rpas", course: "RPAS Standard", module: "Module 3 — Pre-flight checklist",
    section: "Section 3.2 of 5 · Battery and propulsion check",
    progress: 62, remaining: "12 min", lastSeen: "Yesterday, 4:42 pm",
    img: "rpas", org: "rt",
  };

  const inProgress = [
    { id: "wx",     title: "Aviation Weather",          subtitle: "4 modules · 5 hrs",   progress: 28, due: "Due Mar 14", img: "weather", tag: "Theory" },
    { id: "comms",  title: "Radiotelephony & Comms",    subtitle: "3 modules · 4 hrs",   progress: 81, due: "Due Mar 02", img: "comms",   tag: "Practical", org: "rt" },
    { id: "rules",  title: "Air Law & Regulations",     subtitle: "5 modules · 7 hrs",   progress: 14, due: null,         img: "rules",   tag: "Theory" },
  ];

  const openCourses = [
    { id: "airspace",  title: "Airspace Classes for sub-25kg RPAS", subtitle: "Self-paced · 2 hrs", img: "airspace", tag: "Foundation", org: "rt" },
    { id: "night",     title: "Night Operations primer",            subtitle: "Self-paced · 90 min", img: "night",   tag: "Foundation" },
    { id: "photogram", title: "Aerial Photogrammetry — Intro",      subtitle: "Self-paced · 3 hrs", img: "photogram", tag: "Specialist", org: "rt" },
  ];

  const applyCourses = [
    { id: "examiner",  title: "Examiner Pathway",        subtitle: "12 modules · 22 hrs · Cohort starts Apr 6", img: "examiner",  tag: "Advanced", org: "rt",
      requirements: ["RPAS Standard certified", "150+ logged hours", "Partner sponsorship"] },
    { id: "emergency", title: "Emergency Response Operations", subtitle: "8 modules · 14 hrs · Limited seats",   img: "emergency", tag: "Advanced",
      requirements: ["RPAS Standard certified", "Medical clearance"] },
  ];

  const recommended = { id: "instrument", title: "IFR Foundations", subtitle: "Pairs with RPAS Standard", img: "instrument", tag: "Theory" };

  const completed = [
    { id: "ifr",   title: "IFR Foundations",      finished: "Feb 02, 2026", grade: "92%" },
    { id: "intro", title: "Drone Operations 101", finished: "Jan 14, 2026", grade: "88%" },
  ];

  const cardGap = density === "compact" ? 12 : 16;
  const sectionGap = density === "compact" ? 28 : 40;

  return (
    <div className="fc-prose-wrap" data-density={density}>

      {/* ================== Greeting + stats ================== */}
      <div className="fc-greet">
        <div>
          <FCEyebrow>Friday · 27 February 2026</FCEyebrow>
          <h1 className="fc-greet-h">
            Welcome back, Amara.
          </h1>
          <p className="fc-greet-sub">
            You're <strong>38%</strong> away from completing your <strong>RPAS Standard</strong> certification.
            Keep your streak alive — you've studied <strong>5 days running</strong>.
          </p>
        </div>
        <div className="fc-stats">
          <div className="fc-stat">
            <div className="fc-stat-num">14<span>h</span></div>
            <div className="fc-stat-lbl">This month</div>
          </div>
          <div className="fc-stat-sep" />
          <div className="fc-stat">
            <div className="fc-stat-num">5<span>d</span></div>
            <div className="fc-stat-lbl">Streak</div>
          </div>
          <div className="fc-stat-sep" />
          <div className="fc-stat">
            <div className="fc-stat-num">87<span>%</span></div>
            <div className="fc-stat-lbl">Avg. score</div>
          </div>
        </div>
      </div>

      {/* ================== Continue learning hero ================== */}
      <ContinueHero card={continueCard} onContinue={onContinue} variant={heroVariant} courseNote={courseNote} brand={brand} />

      {appsSlot}

      {/* ================== In progress ================== */}
      <SectionHeader title="In progress" hint={`${inProgress.length + 1} active`} />
      <div className="fc-grid-3" style={{ gap: cardGap, marginBottom: sectionGap }}>
        {inProgress.map((c) => (
          <InProgressCard key={c.id} c={c} onOpen={() => onOpenCourse?.(c.id)} courseNote={courseNote} brand={brand} />
        ))}
      </div>

      {/* ================== Open / free ================== */}
      <SectionHeader
        title="Open courses"
        sub="Free · enroll and start immediately"
        action="Browse all open courses →"
      />
      <div className="fc-grid-3" style={{ gap: cardGap, marginBottom: sectionGap }}>
        {openCourses.map((c) => (
          <OpenCard key={c.id} c={c} onOpen={() => (onPreviewCourse || onOpenCourse)?.("enroll")} courseNote={courseNote} brand={brand} />
        ))}
      </div>

      {/* ================== Apply ================== */}
      <SectionHeader
        title="Apply to enroll"
        sub="Cohort-based and advanced courses with prerequisites"
        action={applyAction}
      />
      <div className="fc-grid-2" style={{ gap: cardGap, marginBottom: sectionGap }}>
        {applyCourses.map((c) => (
          <ApplyCard key={c.id} c={c} app={applied[c.id]} onOpen={() => (onPreviewCourse || onOpenCourse)?.("apply")} courseNote={courseNote} brand={brand} />
        ))}
      </div>

      {/* ================== Recommended + completed split ================== */}
      <div className="fc-split" style={{ marginBottom: sectionGap }}>
        <div>
          <SectionHeader title="Recommended for you" sub="Based on your RPAS path" embedded />
          <RecommendedCard c={recommended} onOpen={() => onOpenCourse?.(recommended.id)} />
        </div>
        <div>
          <SectionHeader title="Completed" sub="2 certificates earned" embedded />
          <div className="fc-completed-list">
            {completed.map((c) => (
              <div key={c.id} className="fc-completed-row" onClick={() => onOpenCourse?.(c.id)}>
                <div className="fc-completed-icon">
                  <i className="ph-fill ph-seal-check"></i>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="fc-completed-title">{c.title}</div>
                  <div className="fc-completed-meta">
                    Certified {c.finished} · <span className="fc-mono">{c.grade}</span>
                  </div>
                </div>
                <button className="fc-btn fc-btn-ghost fc-btn-sm">
                  <i className="ph ph-download-simple"></i>
                  <span>Certificate</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
};

/* -------------- Sub-components -------------- */

const SectionHeader = ({ title, sub, hint, action, embedded }) => (
  <div className={"fc-section-header" + (embedded ? " embedded" : "")}>
    <div>
      <h3>{title}</h3>
      {sub ? <p>{sub}</p> : null}
    </div>
    {hint ? <span className="fc-section-hint">{hint}</span> : null}
    {action ? (typeof action === "string" ? <a href="#" className="fc-section-action">{action}</a> : action) : null}
  </div>
);

const ContinueHero = ({ card, onContinue, variant, courseNote, brand }) => {
  const b = (s) => (brand && card.org ? brand(card, s) : null);
  if (variant === "split") {
    return (
      <div className="fc-hero-split">
        <div className="fc-hero-split-thumb">
          <CourseThumb kind={card.img} size="hero" />
          <div className="fc-hero-split-stamp">
            <FCEyebrow style={{ color: "rgba(255,255,255,.7)" }}>Last opened</FCEyebrow>
            <div>{card.lastSeen}</div>
          </div>
        </div>
        <div className="fc-hero-split-body">
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <FCChip tone="primary" icon="play-circle">Continue learning</FCChip>
            <FCChip tone="info">Practical</FCChip>
          </div>
          <div className="fc-hero-eyebrow">{card.course} · Module 3 of 8</div>
          <h2 className="fc-hero-h">{card.module}</h2>
          <div className="fc-hero-section">{card.section}</div>
          <FCProgress value={card.progress} />
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 18 }}>
            <FCButton variant="primary" size="lg" iconAfter="arrow-right" onClick={onContinue}>Resume — {card.remaining}</FCButton>
            <FCButton variant="ghost" icon="list-bullets">Course outline</FCButton>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="fc-hero">
      <div className="fc-hero-thumb">
        <CourseThumb kind={card.img} size="hero" badge={b("thumb")} />
      </div>
      <div className="fc-hero-body">
        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          <FCChip tone="primary" icon="play-circle">Continue learning</FCChip>
          <FCChip tone="info">Practical</FCChip>
          <span className="fc-hero-lastseen">
            <i className="ph ph-clock-counter-clockwise"></i>
            Last opened {card.lastSeen}
          </span>
        </div>
        {b("top")}
        <div className="fc-hero-eyebrow">{card.course} · Module 3 of 8</div>
        <h2 className="fc-hero-h">{card.module}</h2>
        <div className="fc-hero-section">{card.section}</div>
        <FCProgress value={card.progress} />
        {b("foot")}
        {courseNote}
      </div>
      <div className="fc-hero-cta">
        <FCButton variant="primary" size="lg" iconAfter="arrow-right" onClick={onContinue}>Resume</FCButton>
        <div className="fc-hero-remaining">
          <i className="ph ph-clock"></i> {card.remaining} remaining
        </div>
      </div>
    </div>
  );
};

const brandOf = (brand, c, s) => (brand && c.org ? brand(c, s) : null);
const InProgressCard = ({ c, onOpen, courseNote, brand }) => (
  <div className="fc-card-interactive fc-course-card" onClick={onOpen}>
    <CourseThumb kind={c.img} size="md" chip={<FCChip tone="primary">{c.tag}</FCChip>} badge={brandOf(brand, c, "thumb")} />
    <div className="fc-card-body">
      {brandOf(brand, c, "top") || <div className="fc-card-eyebrow">In progress</div>}
      <div className="fc-card-title">{c.title}</div>
      <div className="fc-card-sub">{c.subtitle}</div>
      <FCProgress value={c.progress} />
      <div className="fc-card-foot">
        {c.due ? (
          <span className={"fc-card-due" + (c.progress < 50 ? " urgent" : "")}>
            <i className="ph ph-calendar-blank"></i> {c.due}
          </span>
        ) : <span className="fc-card-due muted"><i className="ph ph-infinity"></i> No deadline</span>}
        <i className="ph ph-arrow-right fc-card-arrow"></i>
      </div>
      {brandOf(brand, c, "foot")}
      {courseNote}
    </div>
  </div>
);

const OpenCard = ({ c, onOpen, courseNote, brand }) => (
  <div className="fc-card-interactive fc-course-card" onClick={onOpen}>
    <CourseThumb kind={c.img} size="md" chip={<FCChip tone="success" icon="lightning">Free</FCChip>} badge={brandOf(brand, c, "thumb")} />
    <div className="fc-card-body">
      {brandOf(brand, c, "top") || <div className="fc-card-eyebrow">{c.tag}</div>}
      <div className="fc-card-title">{c.title}</div>
      <div className="fc-card-sub">{c.subtitle}</div>
      <button className="fc-btn fc-btn-secondary fc-btn-sm" style={{ width: "100%", justifyContent: "center" }}>
        <i className="ph ph-plus-circle"></i><span>Enroll</span>
      </button>
      {brandOf(brand, c, "foot")}
      {courseNote}
    </div>
  </div>
);

const ApplyCard = ({ c, onOpen, courseNote, app, brand }) => app ? <AppliedCard c={c} app={app} /> : (
  <div className="fc-card-apply" onClick={onOpen}>
    <CourseThumb kind={c.img} size="lg" chip={<FCChip tone="warning" icon="lock-key">Application required</FCChip>} badge={brandOf(brand, c, "thumb")} />
    <div className="fc-card-body">
      {brandOf(brand, c, "top") || <div className="fc-card-eyebrow">{c.tag}</div>}
      <div className="fc-card-title" style={{ fontSize: 20 }}>{c.title}</div>
      <div className="fc-card-sub">{c.subtitle}</div>
      <div className="fc-req-list">
        <div className="fc-req-label">Prerequisites</div>
        {c.requirements.map((r, i) => (
          <div key={i} className="fc-req-row">
            <i className={"ph " + (i === 0 ? "ph-check-circle done" : "ph-circle")}></i>
            <span>{r}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <FCButton variant="primary" iconAfter="arrow-right">Start application</FCButton>
        <FCButton variant="ghost">Course details</FCButton>
      </div>
      {brandOf(brand, c, "foot")}
      {courseNote}
    </div>
  </div>
);

const RecommendedCard = ({ c, onOpen }) => (
  <div className="fc-card-recommended" onClick={onOpen}>
    <CourseThumb kind={c.img} size="md" />
    <div style={{ padding: 16 }}>
      <div className="fc-card-eyebrow" style={{ color: "var(--color-accent)" }}>
        <i className="ph-fill ph-sparkle"></i> Suggested next
      </div>
      <div className="fc-card-title">{c.title}</div>
      <div className="fc-card-sub" style={{ marginBottom: 14 }}>{c.subtitle}</div>
      <FCButton variant="secondary" iconAfter="arrow-right">View course</FCButton>
    </div>
  </div>
);

Object.assign(window, { Dashboard });
