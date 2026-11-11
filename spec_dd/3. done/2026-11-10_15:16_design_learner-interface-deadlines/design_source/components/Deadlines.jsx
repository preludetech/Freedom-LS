/* Deadlines — data, primitives and dashboard treatments. "Today" = Fri 27 Feb 2026. */

const DL_KIND = {
  course:     { label: "Course",           icon: "flag-checkered" },
  module:     { label: "Module",           icon: "stack" },
  section:    { label: "Section",          icon: "file-text" },
  assessment: { label: "Assessment",       icon: "exam" },
  exam:       { label: "Exam",             icon: "exam" },
  assignment: { label: "Assignment",       icon: "upload-simple" },
  milestone:  { label: "Cohort milestone", icon: "users-three" },
};
const DL_CONS = {
  info:  { label: "Target date",   icon: "flag" },
  late:  { label: "Marked late",   icon: "hourglass-medium" },
  locks: { label: "Locks",         icon: "lock-key" },
};

const DL_ITEMS = [
  { id: "airlaw-q2", course: "Air Law & Regulations", courseId: "rules", kind: "assessment", title: "Module 2 quiz", date: "25 Feb", dow: "Wed", time: "23:59", days: -2, cons: "late", note: "Late submissions accepted until 06 Mar, capped at 80%" },
  { id: "rpas-m3",   course: "RPAS Standard", courseId: "rpas", kind: "module", title: "Module 3 — Pre-flight checklist", date: "27 Feb", dow: "Fri", time: "23:59", days: 0, cons: "info", note: "Target date set by your instructor. Nothing locks." },
  { id: "comms",     course: "Radiotelephony & Comms", courseId: "comms", kind: "course", title: "Course completion", date: "02 Mar", dow: "Mon", time: "17:00", days: 3, cons: "locks", note: "Course access ends after this date" },
  { id: "rpas-q35",  course: "RPAS Standard", courseId: "rpas", kind: "section", title: "3.5 Section quiz", date: "03 Mar", dow: "Tue", time: "23:59", days: 4, cons: "late", note: "Submissions after this date are marked late" },
  { id: "rpas-log",  course: "RPAS Standard", courseId: "rpas", kind: "assignment", title: "Battery log submission", date: "04 Mar", dow: "Wed", time: "12:00", days: 5, cons: "late", note: "Late submissions lose 10% per day" },
  { id: "rpas-m4",   course: "RPAS Standard", courseId: "rpas", kind: "module", title: "Module 4 — Weather minima", date: "06 Mar", dow: "Fri", time: "23:59", days: 7, cons: "info", note: "Target date. Nothing locks." },
  { id: "rpas-prac", course: "RPAS Standard", courseId: "rpas", kind: "milestone", title: "Practical assessment booking", date: "13 Mar", dow: "Fri", time: "17:00", days: 14, cons: "locks", note: "Booking closes. Next cohort runs in May." },
  { id: "rpas-exam", course: "RPAS Standard", courseId: "rpas", kind: "exam", title: "Final examination window", date: "20 Mar", dow: "Fri", time: "17:00", days: 21, cons: "locks", note: "The exam can't be started after this date" },
  { id: "rpas-done", course: "RPAS Standard", courseId: "rpas", kind: "course", title: "Course completion", date: "31 Mar", dow: "Tue", time: "23:59", days: 32, cons: "locks", note: "Course access ends after this date" },
];
const dlById = (id) => DL_ITEMS.find((d) => d.id === id);
// The most pressing deadline per course, used on cards
const DL_FOR_COURSE = { rules: dlById("airlaw-q2"), comms: dlById("comms"), rpas: dlById("rpas-m3"), wx: null };
const DL_RPAS = DL_ITEMS.filter((d) => d.courseId === "rpas");
const DL_TZ = "SAST";

const dlTone = (d) => d.days < 0 ? "overdue" : d.days === 0 ? "today" : d.days <= 7 ? "soon" : "upcoming";
const dlRel = (d) => d.days < 0 ? `${-d.days} day${d.days === -1 ? "" : "s"} overdue` : d.days === 0 ? `Today, ${d.time}` : d.days === 1 ? "Tomorrow" : `${d.days} days left`;
const dlText = (d) => d.days < 0 ? `Overdue · was due ${d.date}` : d.days === 0 ? `Due today · ${d.time}` : `Due ${d.date} · ${dlRel(d)}`;
const DL_TONE_ICON = { overdue: "warning-circle", today: "clock-countdown", soon: "clock", upcoming: "calendar-blank" };

const DLPill = ({ d, text, size }) => {
  const t = dlTone(d);
  return (
    <span className={`dl-pill dl-t-${t}` + (size === "sm" ? " sm" : "")}>
      <i className={`ph${t === "overdue" ? "-fill" : ""} ph-${DL_TONE_ICON[t]}`}></i>{text || dlText(d)}
    </span>
  );
};
const DLCons = ({ d, short }) => (
  <span className="dl-cons"><i className={`ph ph-${DL_CONS[d.cons].icon}`}></i>{short ? DL_CONS[d.cons].label : d.note}</span>
);
const DLTile = ({ d, size }) => {
  const t = dlTone(d);
  return (
    <div className={`dl-tile dl-tile-${t}` + (size === "lg" ? " lg" : "")}>
      <span className="m">{t === "today" ? "Today" : d.date.split(" ")[1]}</span>
      <span className="d">{t === "today" ? d.time : d.date.split(" ")[0]}</span>
    </div>
  );
};
const DLNone = () => <span className="fc-card-due muted"><i className="ph ph-infinity"></i> No deadline</span>;

/* ---------- Course card treatments ---------- */
const dlCardPill = (c, slot) => {
  if (slot !== "foot") return null;
  const d = DL_FOR_COURSE[c.id];
  return d ? <DLPill d={d} size="sm" /> : <DLNone />;
};
const dlCardTwoLine = (c, slot) => {
  if (slot !== "foot") return null;
  const d = DL_FOR_COURSE[c.id];
  if (!d) return <DLNone />;
  return (
    <div className="dl-foot2">
      <div className={`dl-foot2-date dl-tx-${dlTone(d)}`}><i className={`ph ph-${DL_TONE_ICON[dlTone(d)]}`}></i>{dlText(d)}</div>
      <div className="dl-foot2-what">{d.kind === "course" ? "Course completion" : d.title} · <DLCons d={d} short /></div>
    </div>
  );
};
const dlCardBand = (c, slot) => {
  const d = DL_FOR_COURSE[c.id];
  if (slot === "foot") return d ? <span className="dl-foot-cons"><DLCons d={d} short /></span> : <DLNone />;
  if (!d) return null;
  const t = dlTone(d);
  return (
    <div className={`dl-band dl-band-${t}`}>
      <i className={`ph${t === "overdue" ? "-fill" : ""} ph-${DL_TONE_ICON[t]}`}></i>
      <span className="what">{d.kind === "course" ? "Course due" : d.title}</span>
      <span className="when">{d.days < 0 ? `was due ${d.date}` : d.days === 0 ? `today ${d.time}` : `${d.date} · ${dlRel(d)}`}</span>
    </div>
  );
};
const DL_CARD = { pill: dlCardPill, twoLine: dlCardTwoLine, band: dlCardBand };

/* ---------- Continue-learning hero treatments ---------- */
const heroD = () => dlById("rpas-m3");
const DL_HERO = {
  chip: () => ({ chip: <DLPill d={heroD()} text={`Module 3 due today · ${heroD().time}`} /> }),
  tile: () => ({ ctaTop: (
    <div className="dl-hero-tile">
      <DLTile d={heroD()} />
      <div><div className="t">Module 3 due</div><div className="s"><i className="ph ph-flag"></i> Target date</div></div>
    </div>
  ) }),
  strip: () => ({ body: (
    <div className="dl-hero-strip">
      <DLPill d={heroD()} size="sm" text={`Module 3 due today · ${heroD().time} ${DL_TZ}`} />
      <span className="dl-hero-strip-note">Target date, nothing locks</span>
      <span className="dl-hero-strip-next">Next: <strong>3.5 Section quiz</strong> · 03 Mar</span>
    </div>
  ) }),
};

/* ---------- Upcoming deadlines panel ---------- */
const DLRow = ({ d, compact }) => {
  const t = dlTone(d);
  return (
    <div className={"dl-row" + (compact ? " compact" : "")}>
      <DLTile d={d} />
      <div className="dl-row-main">
        <div className="dl-row-title">{d.title}</div>
        <div className="dl-row-meta"><span><i className={`ph ph-${DL_KIND[d.kind].icon}`}></i>{DL_KIND[d.kind].label}</span><span>{d.course}</span></div>
        {!compact && <div className="dl-row-cons"><DLCons d={d} /></div>}
      </div>
      <div className="dl-row-right">
        <span className={`dl-rel dl-tx-${t}`}>{dlRel(d)}</span>
        {!compact && <button className="fc-btn fc-btn-ghost fc-btn-sm"><span>Open</span><i className="ph ph-arrow-right"></i></button>}
      </div>
    </div>
  );
};

const DLListPanel = () => {
  const groups = [
    ["Overdue", DL_ITEMS.filter((d) => d.days < 0)],
    ["This week", DL_ITEMS.filter((d) => d.days >= 0 && d.days <= 7)],
    ["Later", DL_ITEMS.filter((d) => d.days > 7 && d.days <= 21)],
  ];
  return (
    <div className="dl-panel">
      <DashSectionHeader title="Deadlines" sub="Across all your courses · next 3 weeks" action="View all 9 →" />
      <div className="dl-list">
        {groups.map(([g, items]) => items.length ? (
          <div key={g} className="dl-group">
            <div className={"dl-group-h" + (g === "Overdue" ? " overdue" : "")}>{g}<span>{items.length}</span></div>
            {items.map((d) => <DLRow key={d.id} d={d} />)}
          </div>
        ) : null)}
      </div>
    </div>
  );
};

const DLTimelinePanel = () => {
  const start = -3, end = 22, span = end - start;
  const pos = (n) => `${((n - start) / span) * 100}%`;
  const items = DL_ITEMS.filter((d) => d.days <= 21);
  const weeks = [{ n: 0, l: "Today · 27 Feb" }, { n: 3, l: "Mon 02 Mar" }, { n: 10, l: "Mon 09 Mar" }, { n: 17, l: "Mon 16 Mar" }];
  return (
    <div className="dl-panel">
      <DashSectionHeader title="Deadlines" sub="Next 3 weeks across all your courses" action="View all 9 →" />
      <div className="dl-tl">
        <div className="dl-tl-axis">
          <div className="dl-tl-past" style={{ width: pos(0) }}></div>
          {weeks.map((w) => <div key={w.n} className={"dl-tl-tick" + (w.n === 0 ? " now" : "")} style={{ left: pos(w.n) }}><span>{w.l}</span></div>)}
          {items.map((d) => <span key={d.id} className={`dl-tl-dot dl-dot-${dlTone(d)}`} style={{ left: pos(d.days) }}></span>)}
        </div>
        <div className="dl-tl-lanes">
          {items.map((d, i) => (
            <div key={d.id} className="dl-tl-label" style={{ left: pos(d.days), top: (i % 3) * 64 }}>
              <span className={`dl-tl-stem dl-dot-${dlTone(d)}`} style={{ top: -((i % 3) * 64 + 8), height: (i % 3) * 64 + 22 }}></span>
              <div className={`dl-tl-when dl-tx-${dlTone(d)}`}>{d.days < 0 ? `Overdue · ${d.date}` : d.days === 0 ? `Today ${d.time}` : `${d.dow} ${d.date}`}</div>
              <div className="dl-tl-what">{d.title}</div>
              <div className="dl-tl-course">{d.course}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const DLRailPanel = () => (
  <div className="dl-rail">
    <div className="dl-rail-h"><span>Next deadlines</span><a href="#">All 9 →</a></div>
    {DL_ITEMS.slice(0, 4).map((d) => <DLRow key={d.id} d={d} compact />)}
  </div>
);
const DL_PANEL = { list: { deadlinesSlot: <DLListPanel /> }, timeline: { deadlinesSlot: <DLTimelinePanel /> }, rail: { statsSlot: <DLRailPanel /> } };

/* ---------- Top-of-page alert ---------- */
const DLBanner = () => {
  const d = dlById("airlaw-q2");
  return (
    <div className="dl-banner dl-banner-overdue">
      <i className="ph-fill ph-warning-circle"></i>
      <div className="dl-banner-body">
        <div className="t"><strong>{d.title}</strong> in {d.course} is {-d.days} days overdue.</div>
        <div className="s">{d.note}. Also due today: Module 3 — Pre-flight checklist.</div>
      </div>
      <button className="fc-btn fc-btn-primary fc-btn-sm dl-btn-danger"><span>Open quiz</span><i className="ph ph-arrow-right"></i></button>
      <button className="fc-icon-btn" title="Dismiss"><i className="ph ph-x"></i></button>
    </div>
  );
};
const DLGreetChips = () => (
  <div className="dl-greet-chips">
    <button className="dl-pill dl-t-overdue"><i className="ph-fill ph-warning-circle"></i>1 overdue</button>
    <button className="dl-pill dl-t-today"><i className="ph ph-clock-countdown"></i>1 due today</button>
    <button className="dl-pill dl-t-soon"><i className="ph ph-clock"></i>4 due this week</button>
    <a href="#" className="dl-greet-link">See deadlines →</a>
  </div>
);
const DLStack = () => (
  <div className="dl-stack">
    {[dlById("airlaw-q2"), dlById("rpas-m3")].map((d) => (
      <div key={d.id} className={`dl-stack-item dl-stack-${dlTone(d)}`}>
        <i className={`ph${dlTone(d) === "overdue" ? "-fill" : ""} ph-${DL_TONE_ICON[dlTone(d)]}`}></i>
        <div className="b"><strong>{d.title}</strong><span>{d.course} · {dlText(d)}</span></div>
        <a href="#">Open →</a>
      </div>
    ))}
  </div>
);
const DL_ALERT = { banner: { alertSlot: <DLBanner /> }, chips: { greetNote: <DLGreetChips /> }, stack: { alertSlot: <DLStack /> }, none: {} };

/* ---------- Fragments & full frames ---------- */
const DLCardsFrag = ({ v }) => {
  const cards = [
    { id: "wx", title: "Aviation Weather", subtitle: "4 modules · 5 hrs", progress: 28, img: "weather", tag: "Theory" },
    { id: "comms", title: "Radiotelephony & Comms", subtitle: "3 modules · 4 hrs", progress: 81, img: "comms", tag: "Practical" },
    { id: "rules", title: "Air Law & Regulations", subtitle: "5 modules · 7 hrs", progress: 14, img: "rules", tag: "Theory" },
  ];
  return (
    <div className="dl-frag">
      <DashSectionHeader title="In progress" hint="4 active" />
      <div className="fc-grid-3" style={{ gap: 16 }}>
        {cards.map((c) => <DashInProgressCard key={c.id} c={c} cardDue={DL_CARD[v]} />)}
      </div>
    </div>
  );
};
const DL_HERO_CARD = { id: "rpas", course: "RPAS Standard", module: "Module 3 — Pre-flight checklist", section: "Section 3.2 of 5 · Battery and propulsion check", progress: 62, remaining: "12 min", lastSeen: "Yesterday, 4:42 pm", img: "rpas" };
const DLHeroFrag = ({ v }) => (
  <div className="dl-frag"><DashContinueHero card={DL_HERO_CARD} variant="single" dl={DL_HERO[v]()} /></div>
);

const DLDashFrame = ({ card = "twoLine", hero = "strip", panel = "list", alert = "banner", crop }) => (
  <div className="lx-frame-app" style={crop ? { height: crop, overflow: "hidden" } : null}>
    <TopBar active="courses" />
    <div style={{ flex: 1, overflow: "hidden" }}>
      <Dashboard cardDue={DL_CARD[card]} heroDl={DL_HERO[hero]()} {...(DL_PANEL[panel] || {})} {...(DL_ALERT[alert] || {})} />
    </div>
  </div>
);

Object.assign(window, { DL_ITEMS, DL_RPAS, DL_KIND, DL_CONS, DL_TZ, dlById, dlTone, dlRel, dlText, DL_TONE_ICON, DLPill, DLCons, DLTile, DLRow, DLNone, DLCardsFrag, DLHeroFrag, DLDashFrame, DLListPanel, DLTimelinePanel, DLRailPanel, DLBanner, DLGreetChips, DLStack });
