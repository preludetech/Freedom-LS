/* Mobile dashboard + course player */

const courseColors = {
  rpas:       "linear-gradient(135deg, #283593 0%, #1A237E 100%)",
  weather:    "linear-gradient(135deg, #1f4496 0%, #283593 100%)",
  airspace:   "linear-gradient(135deg, #00A8A4 0%, #007570 100%)",
  comms:      "linear-gradient(135deg, #283593 0%, #4F86F7 100%)",
  rules:      "linear-gradient(135deg, #2D3748 0%, #1A202C 100%)",
  night:      "linear-gradient(135deg, #14143b 0%, #283593 100%)",
  photogram:  "linear-gradient(135deg, #FF6B35 0%, #C43F1A 100%)",
  examiner:   "linear-gradient(135deg, #1A1A2E 0%, #0F0F1F 100%)",
  emergency:  "linear-gradient(135deg, #C53030 0%, #742A2A 100%)",
  instrument: "linear-gradient(135deg, #00CEC9 0%, #009A97 100%)",
};
const courseIcons = {
  rpas: "drone", weather: "cloud-sun", airspace: "map-trifold", comms: "broadcast",
  rules: "scales", night: "moon-stars", photogram: "camera", examiner: "graduation-cap",
  emergency: "first-aid", instrument: "compass",
};
const iconColor = { examiner: "#FF6B35", instrument: "#1A1A2E", airspace: "#FFFFFF" };

function MobileDashboard({ onOpenCourse, onPreviewCourse, appsSlot = null, applyAction = null, appliedSlot = null }) {
  const preview = onPreviewCourse || onOpenCourse;
  return (
    <div className="lx-mobile">
      {/* Top bar */}
      <header className="lxm-topbar">
        <div className="logo">
          <img src="design-system/assets/logo-color.png" alt="" />
          <span>First Class</span>
        </div>
        <div className="right">
          <button className="lxm-iconbtn"><i className="ph ph-magnifying-glass"></i></button>
          <button className="lxm-iconbtn"><i className="ph ph-bell"></i><span className="dot"></span></button>
          <div className="lxm-avatar">AO</div>
        </div>
      </header>

      {/* Greeting */}
      <div className="lxm-greeting">
        <div className="eyebrow">Friday · 27 Feb</div>
        <h1>Welcome back,<br/>Amara.</h1>
        <p>You're <strong>38%</strong> away from your <strong>RPAS Standard</strong> certification. <strong>5-day streak</strong> — keep going.</p>
      </div>

      <div className="lxm-stats">
        <div className="lxm-stat"><div className="lxm-stat-num">14<span>h</span></div><div className="lxm-stat-lbl">This month</div></div>
        <div className="lxm-stat"><div className="lxm-stat-num">5<span>d</span></div><div className="lxm-stat-lbl">Streak</div></div>
        <div className="lxm-stat"><div className="lxm-stat-num">87<span>%</span></div><div className="lxm-stat-lbl">Avg</div></div>
      </div>

      {appsSlot}

      {/* Continue hero */}
      <div className="lxm-hero">
        <div className="lxm-hero-art" style={{ background: courseColors.rpas }}>
          <div className="grid"></div>
          <i className="ph-fill ph-drone"></i>
          <div className="stamp">RPAS · MOD 3 / 8</div>
        </div>
        <div className="lxm-hero-body">
          <div className="chips">
            <span className="lxm-chip-light"><i className="ph-fill ph-play-circle"></i>Continue</span>
            <span className="lxm-chip-light">Practical</span>
          </div>
          <div className="lxm-hero-eyebrow">RPAS Standard · Module 3</div>
          <div className="lxm-hero-h">Pre-flight checklist</div>
          <div className="lxm-hero-section">Section 3.2 of 5 · Battery & propulsion</div>
          <div className="lxm-hero-track"><div className="lxm-hero-fill" style={{ width: "62%" }}></div></div>
          <div className="lxm-hero-cta">
            <button className="lxm-hero-resume" onClick={onOpenCourse}>
              Resume <i className="ph ph-arrow-right"></i>
            </button>
            <span className="meta"><i className="ph ph-clock"></i> 12 min</span>
          </div>
        </div>
      </div>

      {/* In progress — horizontal scroll */}
      <div className="lxm-section">
        <div className="lxm-section-h"><h3>In progress</h3><a href="#">See all →</a></div>
        <div className="lxm-hscroll">
          {[
            { id: "wx", title: "Aviation Weather", sub: "4 mods · 5 hrs", progress: 28, kind: "weather" },
            { id: "comms", title: "Radiotelephony", sub: "3 mods · 4 hrs", progress: 81, kind: "comms" },
            { id: "rules", title: "Air Law", sub: "5 mods · 7 hrs", progress: 14, kind: "rules" },
          ].map(c => (
            <div key={c.id} className="lxm-hscroll-card" onClick={onOpenCourse}>
              <div className="thumb" style={{ background: courseColors[c.kind] }}>
                <div className="grid"></div>
                <i className={`ph-fill ph-${courseIcons[c.kind]}`} style={{ color: iconColor[c.kind] || "#00CEC9" }}></i>
                <span className="chip lxx-chip primary" style={{ background: "rgba(255,255,255,0.9)" }}>In progress</span>
              </div>
              <div className="body">
                <div className="eyebrow">Theory</div>
                <div className="title">{c.title}</div>
                <div className="sub">{c.sub}</div>
                <div className="lxt-hero-track" style={{ height: 4 }}>
                  <div className="lxt-hero-fill" style={{ width: `${c.progress}%` }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Open / Free */}
      <div className="lxm-section">
        <div className="lxm-section-h"><h3>Open courses · free</h3><a href="#">Browse →</a></div>
        <div className="lxm-vlist">
          {[
            { id: "airspace",  title: "Airspace classes for sub-25kg", sub: "Self-paced · 2 hrs",   kind: "airspace" },
            { id: "night",     title: "Night Operations primer",       sub: "Self-paced · 90 min",  kind: "night" },
            { id: "photogram", title: "Aerial Photogrammetry",         sub: "Self-paced · 3 hrs",   kind: "photogram" },
          ].map(c => (
            <div key={c.id} className="lxm-vrow" onClick={() => preview && preview("enroll")}>
              <div className="thumb" style={{ background: courseColors[c.kind] }}>
                <i className={`ph-fill ph-${courseIcons[c.kind]}`} style={{ color: iconColor[c.kind] || "#FFFFFF" }}></i>
              </div>
              <div className="body">
                <div className="eyebrow">Foundation · Free</div>
                <div className="title">{c.title}</div>
                <div className="sub">{c.sub}</div>
              </div>
              <button className="lxm-vrow-cta"><i className="ph ph-plus"></i></button>
            </div>
          ))}
        </div>
      </div>

      {/* Apply */}
      <div className="lxm-section">
        <div className="lxm-section-h"><h3>Apply to enroll</h3>{applyAction}</div>
        {appliedSlot || <div className="lxm-apply-card">
          <div className="lxm-apply-head">
            <div className="thumb" style={{ background: courseColors.examiner }}>
              <i className="ph-fill ph-graduation-cap" style={{ color: "#FF6B35" }}></i>
            </div>
            <div className="body">
              <div className="title">Examiner Pathway</div>
              <div className="sub">12 mods · 22 hrs · Cohort starts Apr 6</div>
            </div>
            <span className="lxx-chip warning"><i className="ph ph-lock-key"></i></span>
          </div>
          <div className="lxm-apply-reqs">
            <div className="lxm-apply-reqs-label">Prerequisites</div>
            <div className="row"><i className="ph ph-check-circle done"></i> RPAS Standard certified</div>
            <div className="row"><i className="ph ph-circle"></i> 150+ logged hours</div>
            <div className="row"><i className="ph ph-circle"></i> Partner sponsorship</div>
          </div>
          <button className="lxm-apply-cta" onClick={() => preview && preview("apply")}>Start application <i className="ph ph-arrow-right"></i></button>
        </div>}
      </div>

      {/* Completed */}
      <div className="lxm-section">
        <div className="lxm-section-h"><h3>Completed</h3></div>
        <div className="lxm-completed">
          <div className="lxm-completed-icon"><i className="ph-fill ph-seal-check"></i></div>
          <div style={{ flex: 1 }}>
            <div className="title">IFR Foundations</div>
            <div className="meta">Certified Feb 02 · <span style={{ fontFamily: "var(--font-mono)" }}>92%</span></div>
          </div>
          <button className="lxm-iconbtn"><i className="ph ph-download-simple"></i></button>
        </div>
        <div className="lxm-completed">
          <div className="lxm-completed-icon"><i className="ph-fill ph-seal-check"></i></div>
          <div style={{ flex: 1 }}>
            <div className="title">Drone Operations 101</div>
            <div className="meta">Certified Jan 14 · <span style={{ fontFamily: "var(--font-mono)" }}>88%</span></div>
          </div>
          <button className="lxm-iconbtn"><i className="ph ph-download-simple"></i></button>
        </div>
      </div>

      {/* Bottom tab bar */}
      <div className="lxm-tabbar">
        <button className="lxm-tab active"><i className="ph-fill ph-house"></i><span>Home</span></button>
        <button className="lxm-tab"><i className="ph ph-books"></i><span>Catalogue</span></button>
        <button className="lxm-tab"><i className="ph ph-medal"></i><span>Records</span></button>
        <button className="lxm-tab"><i className="ph ph-user"></i><span>Profile</span></button>
      </div>
    </div>
  );
}

function MobilePlayer({ onBack }) {
  const [tocOpen, setTocOpen] = React.useState(false);
  const [picked, setPicked] = React.useState(null);
  return (
    <div className="lxm-player">
      <div className="lxm-player-top">
        <div className="lxm-player-bar">
          <button className="lxm-iconbtn" onClick={onBack}><i className="ph ph-arrow-left"></i></button>
          <div className="crumb">RPAS · M3 · <strong>Pre-flight</strong></div>
          <button className="lxm-iconbtn"><i className="ph ph-bookmark-simple"></i></button>
          <button className="lxm-iconbtn" onClick={() => setTocOpen(true)}><i className="ph ph-list-bullets"></i></button>
        </div>
        <div className="lxm-player-progress">
          <div className="track"><div className="fill" style={{ width: "62%" }}></div></div>
          <span className="pct">62%</span>
        </div>
      </div>

      <div className="lxm-player-title">
        <div className="chips">
          <span className="lxx-chip info">Practical</span>
          <span className="lxx-chip primary"><i className="ph ph-book-open"></i>Reading</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-3)", marginLeft: "auto" }}>
            <i className="ph ph-clock"></i> 12 min
          </span>
        </div>
        <h1>Section 3.2 — Battery & propulsion check</h1>
      </div>

      <div className="lxm-player-content">
        <div className="lxm-objective">
          <div className="eyebrow">Learning objective</div>
          <p>Verify battery state and propulsion integrity to a reproducible standard.</p>
        </div>

        <p>Before every flight, verify your battery's terminal voltage with an independent voltmeter — not just the flight controller's reading. A 4S LiPo at <strong>15.8 V</strong> resting indicates a healthy charge; below <strong>15.0 V</strong> should be recharged.</p>

        <div className="lxm-hint">
          <div className="h"><i className="ph-fill ph-lightbulb"></i> Hint</div>
          Battery voltage drops under load. Check resting first, then verify telemetry within ±0.1 V.
        </div>

        <div className="lxm-video">
          <div className="grid"></div>
          <div className="duration">4:12</div>
          <button className="play"><i className="ph-fill ph-play"></i></button>
          <div className="meta">Demonstration · Bench-checking a 4S battery</div>
        </div>

        <h2>Propeller integrity</h2>
        <p>Inspect each propeller for chips, hairline cracks, and hub play. Even a <em>2 mm</em> nick — replace it.</p>
        <ul>
          <li>Check rotational symmetry.</li>
          <li>Verify torque on retaining nuts.</li>
          <li>Replace as a matched set.</li>
        </ul>

        <div className="lxm-quiz">
          <div className="head">
            <span className="lxx-chip primary"><i className="ph ph-lightning"></i>Knowledge check</span>
            <span style={{ fontSize: 11, color: "var(--fg-3)" }}>1 of 1</span>
          </div>
          <div className="q">Below what resting voltage should a 4S LiPo be recharged?</div>
          <div className="answers">
            {[{id:"a",l:"13.8 V"},{id:"b",l:"15.0 V"},{id:"c",l:"16.4 V"}].map((a,i) => (
              <button key={a.id} className={"lxm-answer" + (picked === a.id ? " selected" : "")} onClick={() => setPicked(a.id)}>
                <span className="marker">{String.fromCharCode(65+i)}</span>
                <span>{a.l}</span>
              </button>
            ))}
          </div>
        </div>

        <h2>Resources</h2>
        <a className="lxm-resource" href="#" onClick={e=>e.preventDefault()}>
          <div className="icon"><i className="ph ph-file-pdf"></i></div>
          <div style={{ flex: 1 }}>
            <div className="name">Pre-flight checklist (printable)</div>
            <div className="meta">PDF · 184 KB</div>
          </div>
          <i className="ph ph-download-simple" style={{ color: "var(--fg-3)" }}></i>
        </a>
        <a className="lxm-resource" href="#" onClick={e=>e.preventDefault()}>
          <div className="icon"><i className="ph ph-file-csv"></i></div>
          <div style={{ flex: 1 }}>
            <div className="name">Battery log template</div>
            <div className="meta">CSV · 12 KB</div>
          </div>
          <i className="ph ph-download-simple" style={{ color: "var(--fg-3)" }}></i>
        </a>
      </div>

      <div className="lxm-player-foot">
        <button className="lxm-foot-btn"><i className="ph ph-arrow-left"></i></button>
        <button className="lxm-foot-next">Next section <i className="ph ph-arrow-right"></i></button>
        <button className="lxm-foot-btn"><i className="ph ph-note"></i></button>
      </div>

      {tocOpen && (
        <div className="lxm-sheet-overlay" onClick={() => setTocOpen(false)}>
          <div className="lxm-sheet" onClick={e => e.stopPropagation()}>
            <div className="lxm-sheet-handle"></div>
            <div className="lxm-sheet-head">
              <div className="eyebrow">Course outline</div>
              <h4>RPAS Standard</h4>
              <div className="lxm-sheet-meta">
                <span><i className="ph ph-list-checks"></i> 8 modules</span>
                <span><i className="ph ph-clock"></i> 14 hrs</span>
                <span style={{ marginLeft: "auto" }}>62%</span>
              </div>
              <div className="lxm-sheet-track"><div className="lxm-sheet-fill" style={{ width: "62%" }}></div></div>
            </div>
            <div className="lxm-sheet-tree">
              {[
                { num:"01", title:"Airspace fundamentals", dur:"1h 20m", complete:true },
                { num:"02", title:"Aircraft systems", dur:"1h 50m", complete:true },
                { num:"03", title:"Pre-flight checklist", dur:"55m", current:true,
                  sections:[
                    {id:"3.1",title:"Site survey", complete:true},
                    {id:"3.2",title:"Battery and propulsion check", current:true},
                    {id:"3.3",title:"GPS lock & IMU calibration"},
                    {id:"3.4",title:"Communications check"},
                    {id:"3.5",title:"Section quiz"},
                  ]
                },
                { num:"04", title:"Weather minima", dur:"1h 10m" },
                { num:"05", title:"Flight planning", dur:"2h", locked:true },
                { num:"06", title:"Emergency procedures", dur:"1h 30m", locked:true },
                { num:"07", title:"Practical assessment", dur:"2h", locked:true },
                { num:"08", title:"Final examination", dur:"1h", locked:true },
              ].map(m => (
                <div key={m.num}>
                  <button className={"lxm-mod-row" + (m.current ? " current" : "") + (m.locked ? " locked" : "")}>
                    <span className="num">{m.num}</span>
                    <i className={`ph ${m.locked ? "ph-lock-key" : m.complete ? "ph-check-circle" : m.current ? "ph-play-circle" : "ph-circle"}`}
                       style={{ color: m.complete ? "var(--color-success)" : m.current ? "var(--color-primary)" : m.locked ? "var(--fg-4)" : "var(--fg-3)" }}></i>
                    <span className="title">{m.title}</span>
                    <span className="dur">{m.dur}</span>
                    {!m.locked && <i className="ph ph-caret-right" style={{ color: "var(--fg-4)", fontSize: 12 }}></i>}
                  </button>
                  {m.sections && (
                    <div className="lxm-mod-secs">
                      {m.sections.map(s => (
                        <button key={s.id} className={"lxm-sec-row" + (s.current ? " current" : "") + (s.complete ? " done" : "")}
                                onClick={() => setTocOpen(false)}>
                          <span className="id">{s.id}</span>
                          <i className={`ph ${s.complete ? "ph-check" : "ph-file-text"}`}></i>
                          <span>{s.title}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* Tablet versions */
function TabletDashboard({ onOpenCourse }) {
  return (
    <div className="lx-tablet">
      <header className="lxt-topbar">
        <div className="left">
          <div className="logo"><img src="design-system/assets/logo-color.png" alt="" /><span>First Class</span></div>
          <nav>
            <a className="active" href="#">My courses</a>
            <a href="#">Catalogue</a>
            <a href="#">Records</a>
          </nav>
        </div>
        <div className="right">
          <div className="lxt-search"><i className="ph ph-magnifying-glass"></i><input placeholder="Search…" /></div>
          <button className="lxm-iconbtn"><i className="ph ph-bell"></i><span className="dot"></span></button>
          <div className="lxt-avatar">AO</div>
        </div>
      </header>

      <div className="lxt-wrap">
        <div className="lxt-greet">
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-3)" }}>Friday · 27 February 2026</div>
            <h1>Welcome back, Amara.</h1>
            <p>You're <strong>38%</strong> away from your <strong>RPAS Standard</strong> certification. <strong>5-day streak</strong> — keep it going.</p>
          </div>
          <div className="lxt-stats">
            <div><div className="lxt-stat-num">14<span>h</span></div><div className="lxt-stat-lbl">This month</div></div>
            <div className="lxt-stat-sep"></div>
            <div><div className="lxt-stat-num">5<span>d</span></div><div className="lxt-stat-lbl">Streak</div></div>
            <div className="lxt-stat-sep"></div>
            <div><div className="lxt-stat-num">87<span>%</span></div><div className="lxt-stat-lbl">Avg score</div></div>
          </div>
        </div>

        {/* Hero */}
        <div className="lxt-section-h" style={{ marginTop: 0 }}><h3>Continue learning</h3></div>
        <div className="lxt-hero">
          <div className="lxt-hero-thumb"><div className="grid"></div><i className="ph-fill ph-drone"></i></div>
          <div>
            <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
              <span className="lxx-chip primary"><i className="ph ph-play-circle"></i>Continue</span>
              <span className="lxx-chip info">Practical</span>
            </div>
            <div className="lxt-hero-eyebrow">RPAS Standard · Module 3 of 8</div>
            <h2>Pre-flight checklist</h2>
            <div className="section">Section 3.2 of 5 · Battery and propulsion check</div>
            <div className="lxt-hero-track"><div className="lxt-hero-fill" style={{ width: "62%" }}></div></div>
          </div>
          <div className="lxt-hero-cta">
            <button className="lxt-hero-resume" onClick={onOpenCourse}>Resume <i className="ph ph-arrow-right"></i></button>
            <span className="meta"><i className="ph ph-clock"></i> 12 min</span>
          </div>
        </div>

        {/* In progress 2-up */}
        <div className="lxt-section-h"><div><h3>In progress</h3><p>3 active courses</p></div></div>
        <div className="lxt-grid-3">
          {[
            { id:"wx", title:"Aviation Weather", sub:"4 mods · 5 hrs", progress:28, kind:"weather", tag:"Theory" },
            { id:"comms", title:"Radiotelephony & Comms", sub:"3 mods · 4 hrs", progress:81, kind:"comms", tag:"Practical" },
            { id:"rules", title:"Air Law & Regulations", sub:"5 mods · 7 hrs", progress:14, kind:"rules", tag:"Theory" },
          ].map(c => (
            <div key={c.id} className="lxt-card" onClick={onOpenCourse}>
              <div className="thumb" style={{ background: courseColors[c.kind] }}>
                <div className="grid"></div>
                <i className={`ph-fill ph-${courseIcons[c.kind]}`} style={{ color: "#00CEC9" }}></i>
                <span className="chip lxx-chip primary" style={{ background: "rgba(255,255,255,0.92)" }}>{c.tag}</span>
              </div>
              <div className="body">
                <div className="eyebrow">In progress</div>
                <div className="title">{c.title}</div>
                <div className="sub">{c.sub}</div>
                <div className="track"><div className="fill" style={{ width: `${c.progress}%` }}></div></div>
                <div className="pct">{c.progress}%</div>
              </div>
            </div>
          ))}
        </div>

        {/* Open courses */}
        <div className="lxt-section-h"><div><h3>Open courses</h3><p>Free · enroll instantly</p></div><a href="#">Browse →</a></div>
        <div className="lxt-grid-3">
          {[
            { id:"airspace", title:"Airspace classes", sub:"Self-paced · 2 hrs", kind:"airspace", tag:"Foundation" },
            { id:"night", title:"Night Operations primer", sub:"Self-paced · 90 min", kind:"night", tag:"Foundation" },
            { id:"photogram", title:"Aerial Photogrammetry", sub:"Self-paced · 3 hrs", kind:"photogram", tag:"Specialist" },
          ].map(c => (
            <div key={c.id} className="lxt-card" onClick={onOpenCourse}>
              <div className="thumb" style={{ background: courseColors[c.kind] }}>
                <div className="grid"></div>
                <i className={`ph-fill ph-${courseIcons[c.kind]}`} style={{ color: iconColor[c.kind] || "#FFFFFF" }}></i>
                <span className="chip lxx-chip success"><i className="ph ph-lightning"></i>Free</span>
              </div>
              <div className="body">
                <div className="eyebrow">{c.tag}</div>
                <div className="title">{c.title}</div>
                <div className="sub">{c.sub}</div>
                <button style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid var(--color-primary)", background: "transparent", color: "var(--color-primary)", fontFamily: "var(--font-body)", fontWeight: 600, fontSize: 13, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 5 }}>
                  <i className="ph ph-plus-circle"></i> Enroll
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Apply */}
        <div className="lxt-section-h"><div><h3>Apply to enroll</h3><p>Cohort-based · prerequisites required</p></div></div>
        <div className="lxt-grid-2">
          {[
            { id:"examiner", title:"Examiner Pathway", sub:"12 mods · Cohort starts Apr 6", kind:"examiner",
              reqs:[["RPAS Standard certified",true],["150+ logged hours",false],["Partner sponsorship",false]] },
            { id:"emergency", title:"Emergency Response Operations", sub:"8 mods · Limited seats", kind:"emergency",
              reqs:[["RPAS Standard certified",true],["Medical clearance",false]] },
          ].map(c => (
            <div key={c.id} className="lxt-apply">
              <div className="thumb" style={{ background: courseColors[c.kind] }}>
                <i className={`ph-fill ph-${courseIcons[c.kind]}`} style={{ color: iconColor[c.kind] || "#fff" }}></i>
              </div>
              <div className="body">
                <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
                  <span className="lxx-chip warning"><i className="ph ph-lock-key"></i>Application required</span>
                </div>
                <div className="title">{c.title}</div>
                <div className="sub">{c.sub}</div>
                <div className="reqs">
                  <div className="reqs-label">Prerequisites</div>
                  {c.reqs.map(([t,d],i)=>(
                    <div key={i} className="req"><i className={"ph " + (d ? "ph-check-circle done" : "ph-circle")}></i> {t}</div>
                  ))}
                </div>
                <div className="lxt-apply-btns">
                  <button className="primary">Apply <i className="ph ph-arrow-right"></i></button>
                  <button className="ghost">Details</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TabletPlayer({ onBack }) {
  return (
    <div className="lx-tablet" style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <header className="lxt-topbar">
        <div className="left">
          <button className="lxm-iconbtn" onClick={onBack}><i className="ph ph-arrow-left"></i></button>
          <div className="logo"><img src="design-system/assets/logo-color.png" alt="" /><span>First Class</span></div>
        </div>
        <div className="right">
          <button className="lxm-iconbtn"><i className="ph ph-bookmark-simple"></i></button>
          <button className="lxm-iconbtn"><i className="ph ph-note"></i></button>
          <div className="lxt-avatar">AO</div>
        </div>
      </header>
      <div className="lxt-player">
        <aside className="lxt-player-side">
          <div className="lxt-player-side-head">
            <div className="eyebrow">Course outline</div>
            <h4>RPAS Standard</h4>
            <div className="meta"><span><i className="ph ph-list-checks"></i> 8 mods</span><span><i className="ph ph-clock"></i> 14 hrs</span></div>
            <div className="track"><div className="fill" style={{ width: "62%" }}></div></div>
          </div>
          <div className="lxt-player-side-tree">
            {[
              { num:"01", title:"Airspace fundamentals", complete:true, dur:"1h20m" },
              { num:"02", title:"Aircraft systems", complete:true, dur:"1h50m" },
              { num:"03", title:"Pre-flight checklist", current:true, dur:"55m",
                sections:[{id:"3.1",t:"Site survey",done:true},{id:"3.2",t:"Battery & propulsion",cur:true},{id:"3.3",t:"GPS & IMU"},{id:"3.4",t:"Comms check"},{id:"3.5",t:"Quiz"}]},
              { num:"04", title:"Weather minima", dur:"1h10m" },
              { num:"05", title:"Flight planning", locked:true, dur:"2h" },
              { num:"06", title:"Emergency procedures", locked:true, dur:"1h30m" },
              { num:"07", title:"Practical assessment", locked:true, dur:"2h" },
              { num:"08", title:"Final examination", locked:true, dur:"1h" },
            ].map(m => (
              <div key={m.num}>
                <button className={"lxm-mod-row" + (m.current ? " current" : "") + (m.locked ? " locked" : "")} style={{ padding: "9px 10px", fontSize: 13 }}>
                  <span className="num">{m.num}</span>
                  <i className={`ph ${m.locked ? "ph-lock-key" : m.complete ? "ph-check-circle" : m.current ? "ph-play-circle" : "ph-circle"}`}
                     style={{ color: m.complete ? "var(--color-success)" : m.current ? "var(--color-primary)" : m.locked ? "var(--fg-4)" : "var(--fg-3)" }}></i>
                  <span className="title">{m.title}</span>
                  <span className="dur">{m.dur}</span>
                  {!m.locked && <i className="ph ph-caret-right" style={{ color: "var(--fg-4)", fontSize: 11 }}></i>}
                </button>
                {m.sections && (
                  <div className="lxm-mod-secs" style={{ marginLeft: 22, paddingLeft: 24 }}>
                    {m.sections.map(s => (
                      <button key={s.id} className={"lxm-sec-row" + (s.cur ? " current" : "") + (s.done ? " done" : "")}>
                        <span className="id">{s.id}</span>
                        <i className={`ph ${s.done ? "ph-check" : "ph-file-text"}`}></i>
                        <span>{s.t}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </aside>
        <main className="lxt-player-main">
          <div className="lxt-player-header">
            <div className="crumb">RPAS Standard <i className="ph ph-caret-right" style={{ fontSize: 10 }}></i> Module 3 <i className="ph ph-caret-right" style={{ fontSize: 10 }}></i> <strong>Pre-flight checklist</strong></div>
            <div className="chips">
              <span className="lxx-chip info">Practical</span>
              <span className="lxx-chip primary"><i className="ph ph-book-open"></i>Reading</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-3)", marginLeft: "auto" }}><i className="ph ph-clock"></i> 12 min</span>
            </div>
            <h1>Section 3.2 — Battery and propulsion check</h1>
          </div>
          <div className="lxt-player-content">
            <article className="lxt-player-article">
              <div className="lxm-objective"><div className="eyebrow">Learning objective</div><p>Verify battery state and propulsion integrity to a reproducible standard before every flight.</p></div>
              <p>Before every flight, verify your battery's terminal voltage with an independent voltmeter — not just the controller's reading. A 4S LiPo at <strong>15.8 V</strong> resting indicates a healthy charge; below <strong>15.0 V</strong> should be recharged.</p>
              <div className="lxm-hint"><div className="h"><i className="ph-fill ph-lightbulb"></i> Hint</div>Battery voltage drops under load. Check resting first, then verify telemetry within ±0.1 V.</div>
              <div className="lxm-video">
                <div className="grid"></div><div className="duration">4:12</div>
                <button className="play"><i className="ph-fill ph-play"></i></button>
                <div className="meta">Demonstration · Bench-checking a 4S battery</div>
              </div>
              <h2>Propeller integrity</h2>
              <p>Inspect each propeller for chips, hairline cracks, and lateral play at the hub. Even a <em>2 mm</em> nick should be replaced — fatigue propagates rapidly under flight loads.</p>
              <ul style={{ paddingLeft: 20 }}>
                <li>Check rotational symmetry — spin each prop and observe wobble.</li>
                <li>Verify torque on retaining nuts to manufacturer spec.</li>
                <li>Replace as a matched set; never mix new and worn props.</li>
              </ul>
            </article>
          </div>
          <div className="lxt-player-foot">
            <button className="fc-btn fc-btn-ghost"><i className="ph ph-arrow-left"></i><span>3.1 Site survey</span></button>
            <button style={{ padding: "8px 14px", borderRadius: 999, background: "var(--color-success-light)", color: "var(--color-success)", border: "1px solid #C6F6D5", fontFamily: "var(--font-body)", fontWeight: 600, fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
              <i className="ph ph-check-circle"></i> Mark complete
            </button>
            <button className="fc-btn fc-btn-primary"><span>3.3 GPS & IMU</span><i className="ph ph-arrow-right"></i></button>
          </div>
        </main>
      </div>
    </div>
  );
}

Object.assign(window, { MobileDashboard, MobilePlayer, TabletDashboard, TabletPlayer });
