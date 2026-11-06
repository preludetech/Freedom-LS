/* Course Player — collapsible TOC sidebar + rich content area with widgets. */

const CoursePlayer = ({ onBack, density = "comfortable", showWidgets = true, dl = {} }) => {
  const [currentSection, setCurrentSection] = React.useState("3.2");
  const [expandedModule, setExpandedModule] = React.useState("m3");
  const [quizPicked, setQuizPicked] = React.useState(null);
  const [notesOpen, setNotesOpen] = React.useState(false);

  const modules = [
    { id: "m1", num: "01", title: "Airspace fundamentals", duration: "1h 20m", complete: true,
      sections: [
        { id: "1.1", title: "Controlled vs. uncontrolled airspace", complete: true },
        { id: "1.2", title: "Class C, D, E, G", complete: true },
        { id: "1.3", title: "Knowledge check", complete: true, kind: "quiz" },
      ]
    },
    { id: "m2", num: "02", title: "Aircraft systems", duration: "1h 50m", complete: true,
      sections: [
        { id: "2.1", title: "Powerplant overview", complete: true },
        { id: "2.2", title: "Flight controls", complete: true },
        { id: "2.3", title: "Telemetry & failsafes", complete: true },
        { id: "2.4", title: "Module quiz", complete: true, kind: "quiz" },
      ]
    },
    { id: "m3", num: "03", title: "Pre-flight checklist", duration: "55m", current: true,
      sections: [
        { id: "3.1", title: "Site survey",                       complete: true },
        { id: "3.2", title: "Battery and propulsion check",      current: true, kind: "reading" },
        { id: "3.3", title: "GPS lock and IMU calibration",      kind: "video" },
        { id: "3.4", title: "Communications check",              kind: "reading" },
        { id: "3.5", title: "Section quiz",                      kind: "quiz" },
      ]
    },
    { id: "m4", num: "04", title: "Weather minima",          duration: "1h 10m",
      sections: [
        { id: "4.1", title: "Wind, visibility, ceilings", kind: "reading" },
        { id: "4.2", title: "Reading a METAR/TAF",        kind: "reading" },
        { id: "4.3", title: "Decision matrix",            kind: "interactive" },
      ]
    },
    { id: "m5", num: "05", title: "Flight planning",            duration: "2h",     locked: true },
    { id: "m6", num: "06", title: "Emergency procedures",       duration: "1h 30m", locked: true },
    { id: "m7", num: "07", title: "Practical assessment",       duration: "2h",     locked: true },
    { id: "m8", num: "08", title: "Final examination",          duration: "1h",     locked: true },
  ];

  return (
    <div className="fc-shell fc-player" data-density={density}>
      {/* ============ TOC SIDEBAR ============ */}
      <aside className="fc-player-sidebar">
        <div className="fc-player-sb-head">
          <FCEyebrow>Course outline</FCEyebrow>
          <h4>RPAS Standard</h4>
          <div className="fc-player-sb-meta">
            <span><i className="ph ph-list-checks"></i> 8 modules</span>
            <span><i className="ph ph-clock"></i> 14 hrs</span>
          </div>
          <FCProgress value={62} />
          <div className="fc-player-sb-progress-meta">
            <span>62% complete</span>
            <span className="fc-mono">5 / 8 mods</span>
          </div>
          {dl.sbHead}
        </div>

        <div className="fc-player-sb-tree">
          {modules.map((m) => (
            <ModuleNode
              key={m.id}
              m={m}
              expanded={expandedModule === m.id || m.current}
              onToggle={() => setExpandedModule(expandedModule === m.id ? null : m.id)}
              currentSection={currentSection}
              onSelectSection={setCurrentSection}
              dl={dl}
            />
          ))}
        </div>

        <div className="fc-player-sb-foot">
          {dl.sbFoot}
          <button className="fc-sb-shortcut">
            <i className="ph ph-bookmark-simple"></i>
            <span>Bookmarks</span>
            <span className="fc-mono fc-sb-count">3</span>
          </button>
          <button className="fc-sb-shortcut">
            <i className="ph ph-paperclip"></i>
            <span>Resources</span>
            <span className="fc-mono fc-sb-count">12</span>
          </button>
          <button className="fc-sb-shortcut">
            <i className="ph ph-chats-circle"></i>
            <span>Discussion</span>
            <span className="fc-dot-mini" />
          </button>
        </div>
      </aside>

      {/* ============ MAIN ============ */}
      <main className="fc-main" style={{ position: "relative" }}>
        {dl.banner}
        {/* Section header strip */}
        <div className="fc-player-header">
          <div className="fc-player-header-row">
            <button className="fc-btn fc-btn-ghost fc-btn-sm" onClick={onBack}>
              <i className="ph ph-arrow-left"></i><span>Dashboard</span>
            </button>
            <div className="fc-player-crumb">
              <span>RPAS Standard</span>
              <i className="ph ph-caret-right"></i>
              <span>Module 3</span>
              <i className="ph ph-caret-right"></i>
              <strong>Pre-flight checklist</strong>
            </div>
            <div className="fc-player-header-actions">
              <button className="fc-icon-btn" title="Bookmark this section"><i className="ph ph-bookmark-simple"></i></button>
              <button className="fc-icon-btn" title="Toggle notes" onClick={() => setNotesOpen(!notesOpen)}>
                <i className={"ph " + (notesOpen ? "ph-note-pencil" : "ph-note")}></i>
              </button>
              <button className="fc-icon-btn" title="Settings"><i className="ph ph-gear-six"></i></button>
            </div>
          </div>

          <div className="fc-player-header-title">
            <div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                <FCChip tone="info">Practical</FCChip>
                <FCChip tone="primary" icon="book-open"> Reading</FCChip>
                <span className="fc-section-time">
                  <i className="ph ph-clock"></i> ~12 min remaining
                </span>
                {dl.headerChip}
              </div>
              <h1>Section 3.2 — Battery and propulsion check</h1>
            </div>
            {dl.headerRight}
            <div className="fc-section-stepper">
              <span className="fc-mono">3.2 / 3.5</span>
              <div className="fc-stepper-dots">
                {["3.1","3.2","3.3","3.4","3.5"].map((s, i) => (
                  <span key={s} className={"fc-step-dot" + (s === currentSection ? " current" : "") + (i === 0 ? " done" : "")} />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Reading content */}
        <div className="fc-content-wrap">
          <article className="fc-article">
            {dl.articleTop}

            {/* Hero callout */}
            <div className="fc-learning-objective">
              <FCEyebrow>Learning objective</FCEyebrow>
              <p>Verify battery state and propulsion integrity to a reproducible standard before every flight.</p>
            </div>

            <p className="fc-lead">
              Before every flight, verify your battery's terminal voltage with an independent voltmeter — not just the
              flight controller's onboard reading. A 4S LiPo at <strong>15.8 V</strong> resting indicates a healthy
              charge; anything below <span className="fc-glossary" data-term="resting voltage">
              <strong>15.0 V</strong></span> should be recharged before takeoff.
            </p>

            {/* Hint block */}
            <div className="fc-alert fc-alert-info" style={{ margin: "20px 0" }}>
              <div className="h"><i className="ph-fill ph-lightbulb"></i> Hint</div>
              Battery voltage drops under load. Always check resting voltage first, then verify the controller's
              telemetry matches within ±0.1 V before arming the motors.
            </div>

            {showWidgets && <VideoWidget />}

            <h2>Propeller integrity</h2>
            <p>
              Inspect each propeller for chips, hairline cracks, and lateral play at the hub. A propeller with even a
              <em> 2 mm </em>nick should be replaced — fatigue propagates rapidly under flight loads.
            </p>
            <ul className="fc-list">
              <li>Check rotational symmetry — spin each prop and observe wobble.</li>
              <li>Verify torque on retaining nuts to manufacturer spec.</li>
              <li>Replace as a matched set; never mix new and worn props on the same airframe.</li>
            </ul>

            {showWidgets && <DiagramWidget />}

            <h2>Verification log</h2>
            <p>Your platform recorded the following pre-flight verification automatically when you last powered the aircraft:</p>
            <CodeBlock />

            {showWidgets && <KnowledgeCheck picked={quizPicked} onPick={setQuizPicked} />}

            {showWidgets && <ResourcesWidget />}

            {showWidgets && <DiscussionWidget />}
          </article>

          {notesOpen && <NotesPanel onClose={() => setNotesOpen(false)} />}
          {dl.drawer}
        </div>

        {/* Footer nav */}
        <div className="fc-player-footer">
          <FCButton variant="ghost" icon="arrow-left">
            <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.2 }}>
              <span style={{ fontSize: 11, opacity: .6, fontWeight: 500 }}>Previous</span>
              <span>Section 3.1 — Site survey</span>
            </span>
          </FCButton>
          <button className="fc-mark-complete">
            <i className="ph ph-check-circle"></i><span>Mark section complete</span>
          </button>
          <FCButton variant="primary" iconAfter="arrow-right">
            <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.2 }}>
              <span style={{ fontSize: 11, opacity: .8, fontWeight: 500 }}>Next</span>
              <span>3.3 — GPS lock & IMU</span>
            </span>
          </FCButton>
        </div>
        {dl.overlay}
      </main>
    </div>
  );
};

/* ================== Sidebar module node ================== */
const ModuleNode = ({ m, expanded, onToggle, currentSection, onSelectSection, dl = {} }) => {
  const stateIcon = m.locked ? "ph-lock-key" : m.complete ? "ph-check-circle" : m.current ? "ph-play-circle" : "ph-circle";
  const stateColor = m.locked ? "var(--fg-4)" : m.complete ? "var(--color-success)" : m.current ? "var(--color-primary)" : "var(--fg-3)";
  return (
    <div className={"fc-mod-node" + (m.current ? " current" : "") + (m.locked ? " locked" : "")}>
      <button className="fc-mod-row" onClick={() => !m.locked && onToggle()} disabled={m.locked}>
        <span className="fc-mod-num">{m.num}</span>
        <i className={`ph ${stateIcon}`} style={{ color: stateColor }}></i>
        <span className="fc-mod-title">{m.title}</span>
        <span className="fc-mod-dur">{(dl.modMeta && dl.modMeta(m)) || m.duration || ""}</span>
        {!m.locked ? <i className={`ph ph-caret-${expanded ? "down" : "right"} fc-mod-caret`}></i> : <span></span>}
      </button>
      {dl.modBelow && dl.modBelow(m)}
      {expanded && m.sections && (
        <div className="fc-mod-sections">
          {m.sections.map((s) => (
            <button
              key={s.id}
              className={"fc-sec-row" + (s.id === currentSection ? " current" : "") + (s.complete ? " done" : "") + (dl.secMeta ? " dl-has" : "")}
              onClick={() => onSelectSection(s.id)}
            >
              <span className="fc-sec-id">{s.id}</span>
              <i className={`ph ${
                s.complete ? "ph-check" :
                s.kind === "quiz" ? "ph-question" :
                s.kind === "video" ? "ph-play-circle" :
                s.kind === "interactive" ? "ph-cursor-click" :
                "ph-file-text"
              } fc-sec-kind`}></i>
              <span className="fc-sec-title">{s.title}</span>
              {dl.secMeta && (dl.secMeta(s) || <span></span>)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

/* ================== Widgets ================== */

const VideoWidget = () => (
  <div className="fc-widget fc-video-widget">
    <div className="fc-video-thumb">
      <div className="fc-video-grid"></div>
      <i className="ph-fill ph-drone fc-video-bg-icon"></i>
      <button className="fc-video-play"><i className="ph-fill ph-play"></i></button>
      <div className="fc-video-overlay">
        <FCEyebrow style={{ color: "rgba(255,255,255,.7)" }}>Demonstration · 4:12</FCEyebrow>
        <div className="fc-video-title">Bench-checking a 4S battery</div>
      </div>
      <div className="fc-video-chips">
        <span><i className="ph ph-closed-captioning"></i> CC</span>
        <span><i className="ph ph-translate"></i> 4 langs</span>
      </div>
    </div>
    <div className="fc-video-chapters">
      <div className="fc-chapter active">
        <span className="fc-mono">00:00</span>
        <span>Test rig setup</span>
      </div>
      <div className="fc-chapter">
        <span className="fc-mono">01:14</span>
        <span>Reading the multimeter</span>
      </div>
      <div className="fc-chapter">
        <span className="fc-mono">02:38</span>
        <span>Common voltage faults</span>
      </div>
      <div className="fc-chapter">
        <span className="fc-mono">03:42</span>
        <span>Recap & next steps</span>
      </div>
    </div>
  </div>
);

const DiagramWidget = () => (
  <div className="fc-widget fc-diagram-widget">
    <div className="fc-diagram-canvas">
      {/* Stylised propeller + hub diagram in pure SVG */}
      <svg viewBox="0 0 480 220" width="100%" height="100%">
        <defs>
          <linearGradient id="propBlade" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#283593" />
            <stop offset="100%" stopColor="#00CEC9" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="480" height="220" fill="#F8F9FC"/>
        {/* faint grid */}
        {[40,80,120,160,200].map(y => <line key={y} x1="0" x2="480" y1={y} y2={y} stroke="#E2E8F0" strokeDasharray="3 4"/>)}
        {/* prop blades */}
        <ellipse cx="240" cy="110" rx="170" ry="14" fill="url(#propBlade)" opacity="0.85"/>
        {/* hub */}
        <circle cx="240" cy="110" r="22" fill="#1A1A2E" />
        <circle cx="240" cy="110" r="10" fill="#FF6B35" />
        {/* annotations */}
        <g fontFamily="IBM Plex Mono" fontSize="11" fill="#4A5568">
          <line x1="120" y1="80" x2="120" y2="105" stroke="#283593" strokeWidth="1.5"/>
          <circle cx="120" cy="110" r="3" fill="#283593"/>
          <text x="40" y="74">A · Blade tip</text>
          <line x1="240" y1="50" x2="240" y2="86" stroke="#283593" strokeWidth="1.5"/>
          <circle cx="240" cy="110" r="3" fill="#283593"/>
          <text x="200" y="44">B · Hub & retainer</text>
          <line x1="360" y1="160" x2="320" y2="120" stroke="#283593" strokeWidth="1.5"/>
          <circle cx="320" cy="115" r="3" fill="#283593"/>
          <text x="332" y="180">C · Trailing edge</text>
        </g>
      </svg>
    </div>
    <div className="fc-diagram-foot">
      <span><i className="ph ph-image-square"></i> <strong>Fig. 3.2.1</strong> — Propeller inspection points</span>
      <button className="fc-mini-btn"><i className="ph ph-arrows-out"></i> Open large</button>
    </div>
  </div>
);

const CodeBlock = () => (
  <div className="fc-codeblock">
    <div className="fc-codeblock-bar">
      <span><i className="ph ph-terminal"></i> verification.log</span>
      <button className="fc-mini-btn ghost"><i className="ph ph-copy"></i> Copy</button>
    </div>
    <pre>
      <code>
        <span className="c-com">{"// pre-flight verification log"}</span>{"\n"}
        <span className="c-id">BAT</span>.<span className="c-fn">verify</span>(<span className="c-str">"voltage_min"</span>, <span className="c-num">15.0</span>);  <span className="c-com">// PASS · 15.82V</span>{"\n"}
        <span className="c-id">PROP</span>.<span className="c-fn">inspect</span>(<span className="c-str">"all"</span>);                 <span className="c-com">// PASS · 4/4 props</span>{"\n"}
        <span className="c-id">GPS</span>.<span className="c-fn">lock</span>(<span className="c-num">10</span>);                       <span className="c-com">// PASS · 14 sats</span>{"\n"}
        <span className="c-id">IMU</span>.<span className="c-fn">calibrate</span>();                  <span className="c-warn">// WARN · drift +0.3°</span>
      </code>
    </pre>
  </div>
);

const KnowledgeCheck = ({ picked, onPick }) => {
  const correct = "b";
  const answers = [
    { id: "a", label: "13.8 V", note: "Below safe minimum" },
    { id: "b", label: "15.0 V", note: "Manufacturer spec floor" },
    { id: "c", label: "16.4 V", note: "Above resting nominal" },
    { id: "d", label: "Voltage doesn't matter if the controller arms", note: null },
  ];
  const showFeedback = picked !== null;
  return (
    <div className="fc-widget fc-quiz-widget">
      <div className="fc-quiz-head">
        <FCChip tone="primary" icon="lightning">Knowledge check</FCChip>
        <span className="fc-quiz-meta">1 of 1 · Doesn't affect your grade</span>
      </div>
      <div className="fc-quiz-q">
        Below what resting voltage should a 4S LiPo be recharged before takeoff?
      </div>
      <div className="fc-quiz-answers">
        {answers.map((a, i) => {
          const cls = ["fc-answer"];
          if (picked === a.id) cls.push("selected");
          if (showFeedback && a.id === correct) cls.push("correct");
          if (showFeedback && picked === a.id && a.id !== correct) cls.push("wrong");
          return (
            <button key={a.id} className={cls.join(" ")} onClick={() => !showFeedback && onPick(a.id)}>
              <span className="marker">{String.fromCharCode(65 + i)}</span>
              <span style={{ flex: 1, textAlign: "left" }}>
                <span style={{ display: "block", fontWeight: 500 }}>{a.label}</span>
                {a.note && <span style={{ display: "block", fontSize: 12, opacity: .7, marginTop: 2 }}>{a.note}</span>}
              </span>
              {showFeedback && a.id === correct && <i className="ph-fill ph-check-circle" style={{ color: "var(--color-success)" }}></i>}
              {showFeedback && picked === a.id && a.id !== correct && <i className="ph-fill ph-x-circle" style={{ color: "var(--color-error)" }}></i>}
            </button>
          );
        })}
      </div>
      {showFeedback && (
        <div className={"fc-alert " + (picked === correct ? "fc-alert-success" : "fc-alert-error")} style={{ marginTop: 12 }}>
          <div className="h">
            {picked === correct ? <><i className="ph-fill ph-check-circle"></i> Correct.</> : <><i className="ph-fill ph-info"></i> Not quite.</>}
          </div>
          The manufacturer floor is <strong>15.0 V</strong> resting. Below this, internal cell imbalance is significant
          enough that the chemistry can't be trusted under flight load.
        </div>
      )}
    </div>
  );
};

const ResourcesWidget = () => (
  <div className="fc-widget fc-resources">
    <div className="fc-resources-head">
      <h3>Resources for this section</h3>
      <button className="fc-mini-btn ghost"><i className="ph ph-download-simple"></i> Download all</button>
    </div>
    <div className="fc-resources-list">
      {[
        { icon: "file-pdf",    name: "Pre-flight checklist (printable)", meta: "PDF · 1 page · 184 KB" },
        { icon: "file-csv",    name: "Battery log template",             meta: "CSV · 12 KB" },
        { icon: "file-doc",    name: "Manufacturer specifications",      meta: "DOCX · 6 pages · 412 KB" },
        { icon: "link-simple", name: "OEM safety bulletin SB-2025-04",   meta: "External · 3 min read" },
      ].map((r) => (
        <a key={r.name} className="fc-resource-row" href="#" onClick={(e) => e.preventDefault()}>
          <div className="fc-resource-icon"><i className={`ph ph-${r.icon}`}></i></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="fc-resource-name">{r.name}</div>
            <div className="fc-resource-meta">{r.meta}</div>
          </div>
          <i className="ph ph-download-simple"></i>
        </a>
      ))}
    </div>
  </div>
);

const DiscussionWidget = () => (
  <div className="fc-widget fc-discussion">
    <div className="fc-discussion-head">
      <h3>Discussion</h3>
      <span className="fc-discussion-count">3 questions · 1 instructor reply pending</span>
    </div>
    <div className="fc-comment">
      <div className="fc-comment-avatar" style={{ background: "#FF6B35" }}>JN</div>
      <div className="fc-comment-body">
        <div className="fc-comment-head">
          <strong>Jelani Ndlovu</strong>
          <FCChip tone="primary">Learner</FCChip>
          <span>2 days ago</span>
        </div>
        <p>If the OEM floor is 15.0 V but my pack always sags to 14.8 V at landing, am I damaging cells over time?</p>
        <div className="fc-comment-actions">
          <button><i className="ph ph-arrow-fat-up"></i> 4</button>
          <button><i className="ph ph-chat"></i> Reply</button>
        </div>
      </div>
    </div>
    <div className="fc-comment fc-comment-instr">
      <div className="fc-comment-avatar" style={{ background: "#283593" }}>RM</div>
      <div className="fc-comment-body">
        <div className="fc-comment-head">
          <strong>Captain R. Mokoena</strong>
          <FCChip tone="success" icon="check-circle">Instructor</FCChip>
          <span>1 day ago</span>
        </div>
        <p>Sag to 14.8 V <em>under load</em> is fine — that's the discharge curve. The 15.0 V threshold is for <strong>resting</strong> voltage, measured 5 minutes after landing. Log both values for a few flights and you'll see the difference clearly.</p>
        <div className="fc-comment-actions">
          <button><i className="ph-fill ph-arrow-fat-up" style={{ color: "var(--color-primary)" }}></i> 12</button>
          <button><i className="ph ph-chat"></i> Reply</button>
        </div>
      </div>
    </div>
    <button className="fc-comment-compose">
      <i className="ph ph-pencil-simple-line"></i> Ask a question about this section…
    </button>
  </div>
);

const NotesPanel = ({ onClose }) => (
  <aside className="fc-notes">
    <div className="fc-notes-head">
      <div>
        <FCEyebrow>Your notes</FCEyebrow>
        <h4>Section 3.2</h4>
      </div>
      <button className="fc-icon-btn" onClick={onClose}><i className="ph ph-x"></i></button>
    </div>
    <div className="fc-notes-list">
      <div className="fc-note">
        <div className="fc-note-quote">"verify your battery's terminal voltage with an independent voltmeter"</div>
        <div className="fc-note-text">Buy a Fluke 101. Cross-check on every flight day, not every flight.</div>
        <div className="fc-note-meta">Yesterday · 4:38 pm</div>
      </div>
      <div className="fc-note">
        <div className="fc-note-quote">"replace as a matched set"</div>
        <div className="fc-note-text">Order spare matched props this week — only 2 in stock.</div>
        <div className="fc-note-meta">Today · 9:12 am</div>
      </div>
    </div>
    <div className="fc-notes-compose">
      <textarea placeholder="Add a note for this section…"></textarea>
      <div className="fc-notes-actions">
        <button className="fc-mini-btn"><i className="ph ph-quotes"></i> Quote</button>
        <FCButton size="sm" variant="primary">Save note</FCButton>
      </div>
    </div>
  </aside>
);

Object.assign(window, { CoursePlayer });
