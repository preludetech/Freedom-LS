/* Status screens — one component, nine states. Plus the applications list and
   the small entry-point artefacts (dashboard card, email, profile menu). */

function ApplicationStatus({ state = "review", editWindow = false, showAnswers = true, onBack, onEdit, onContinue }) {
  const s = APP_STATES[state];
  const isDraft = state === "draft";
  return (
    <div className="lxa-shell">
      <div className="lxa-page">
        <a className="lxa-back" href="#" onClick={(e) => { e.preventDefault(); onBack?.(); }}>
          <i className="ph ph-arrow-left"></i>My applications
        </a>

        <div className="lxa-status-top">
          <div className="grow">
            <AppBadge state={state} />
            <h1 className="lxa-h" style={{ marginTop: 14 }}>{s.head}</h1>
            <p className="lxa-sub">{s.blurb}</p>
            <div className="lxa-meta">
              <div><div className="k">REFERENCE</div><div className="v" style={{ fontFamily: "var(--font-mono)" }}>{isDraft ? "—" : APP_META.ref}</div></div>
              <div><div className="k">COURSE</div><div className="v">{APP_META.course}</div></div>
              <div><div className="k">COHORT</div><div className="v">{APP_META.cohort.replace("Cohort 12 · starts ", "12 · ")}</div></div>
              <div><div className="k">{isDraft ? "STARTED" : "SUBMITTED"}</div><div className="v">{isDraft ? APP_META.started : APP_META.submitted}</div></div>
              <div><div className="k">FEE</div><div className="v">{APP_META.fee}</div></div>
            </div>
          </div>
        </div>

        {s.callout ? <div style={{ marginTop: 28 }}><AppCallout c={s.callout} /></div> : null}

        {editWindow ? (
          <div style={{ marginTop: 28 }}>
            <AppCallout c={{
              tone: "info", icon: "pencil-simple", t: "You can still change your answers",
              d: "Editing stays open until the eligibility check begins — usually within a working day of submitting. After that, changes go through your admissions contact.",
              acts: [{ label: "Edit application", icon: "pencil-simple" }],
            }} />
          </div>
        ) : null}

        <div className="lxa-cols">
          <div>
            <div className="lxa-panel">
              <div className="lxa-panel-h"><div className="t">Progress</div>
                {!isDraft ? <span className="lxa-badge sm review" style={{ background: "var(--grey-100)", color: "var(--fg-2)" }}><i className="ph ph-clock"></i>Updated {state === "draft" ? "2 Sep" : "today"}</span> : null}
              </div>
              <AppTimeline items={s.tl} />
            </div>

            {showAnswers ? (
              <div className="lxa-panel">
                <div className="lxa-panel-h">
                  <div className="t">Your answers</div>
                  {isDraft || editWindow
                    ? <button className="fc-btn fc-btn-secondary fc-btn-sm" onClick={onEdit}><i className="ph ph-pencil-simple"></i><span>Edit</span></button>
                    : <span className="lxa-lock"><i className="ph ph-lock-simple"></i>Read-only</span>}
                </div>
                <ReviewBody readOnly={!(isDraft || editWindow)} onEdit={onEdit} declared={false} setDeclared={() => {}} />
              </div>
            ) : null}

            {showAnswers ? null : (
              <div className="lxa-panel">
                <div className="lxa-panel-h">
                  <div className="t">Your answers</div>
                  {isDraft || editWindow
                    ? <button className="fc-btn fc-btn-secondary fc-btn-sm" onClick={onEdit}><i className="ph ph-pencil-simple"></i><span>Edit</span></button>
                    : <span className="lxa-lock"><i className="ph ph-lock-simple"></i>Read-only</span>}
                </div>
                <dl className="lxa-kv" style={{ padding: 0 }}>
                  <dt>Name</dt><dd>{APP_VALUES.legalName}</dd>
                  <dt>Licence</dt><dd>{APP_VALUES.licence}</dd>
                  <dt>Command hours</dt><dd>{APP_VALUES.hours}</dd>
                  <dt>Operator &amp; role</dt><dd>{APP_VALUES.operator}</dd>
                  <dt>Documents</dt><dd>4 files attached</dd>
                </dl>
                <button className="fc-btn fc-btn-ghost fc-btn-sm" style={{ marginTop: 12, paddingLeft: 0 }}><span>See the full application</span><i className="ph ph-arrow-right"></i></button>
              </div>
            )}

            {state === "declined" ? (
              <div className="lxa-panel">
                <div className="lxa-panel-h"><div className="t">Reviewer's note</div></div>
                <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.65, color: "var(--fg-2)" }}>
                  “Amara's assessment write-ups are among the most consistent we've seen from a non-accredited assessor, and her declared experience is genuine. The cohort minimum of 500 logged command hours is a regulatory floor we can't move — she is 88 hours short. I'd encourage a reapplication for Cohort 13 and would expect it to succeed.”
                </p>
                <div className="lxa-hint" style={{ marginTop: 12 }}>Dana Whitmore, Admissions · 8 Sep 2026</div>
              </div>
            ) : null}
          </div>

          <aside>
            <div className="lxa-panel">
              <div className="lxa-side-h">{isDraft ? "Finish your application" : "Actions"}</div>
              <div className="lxa-side-acts">
                {s.primary ? (
                  <button className={`fc-btn fc-btn-${s.primary.variant || "primary"}`} onClick={isDraft ? onContinue : undefined}>
                    <i className={`ph ph-${s.primary.icon}`}></i><span>{s.primary.label}</span>
                  </button>
                ) : null}
                {(s.secondary || []).map((a) => (
                  <button key={a.label} className={`fc-btn fc-btn-${a.variant || "secondary"}`}>
                    <i className={`ph ph-${a.icon}`}></i><span>{a.label}</span>
                  </button>
                ))}
                {!isDraft ? (
                  <button className="fc-btn fc-btn-ghost"><i className="ph ph-file-arrow-down"></i><span>Download a PDF copy</span></button>
                ) : null}
              </div>
              {s.note ? <div className="lxa-side-note">{s.note}</div> : null}
            </div>

            <div className="lxa-panel">
              <div className="lxa-side-h">Your admissions contact</div>
              <div className="lxa-contact">
                <div className="av">DW</div>
                <div><div className="nm">Dana Whitmore</div><div className="rl">Admissions, Examiner Pathway</div></div>
              </div>
              <div className="lxa-side-acts" style={{ marginTop: 16 }}>
                <button className="fc-btn fc-btn-secondary fc-btn-sm"><i className="ph ph-chat-circle"></i><span>Send a message</span></button>
              </div>
              <div className="lxa-side-note">Replies within one working day.</div>
            </div>

            <div className="lxa-panel">
              <div className="lxa-side-h">Cohort 12</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13.5, color: "var(--fg-2)" }}>
                <div style={{ display: "flex", gap: 9 }}><i className="ph ph-calendar-blank" style={{ color: "var(--fg-3)", fontSize: 16 }}></i>Starts 6 Oct 2026 · 14 weeks</div>
                <div style={{ display: "flex", gap: 9 }}><i className="ph ph-users-three" style={{ color: "var(--fg-3)", fontSize: 16 }}></i>18 seats · 4 remaining</div>
                <div style={{ display: "flex", gap: 9 }}><i className="ph ph-clock-countdown" style={{ color: "var(--fg-3)", fontSize: 16 }}></i>{APP_META.closes}</div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

/* ---------- My applications ---------- */
const APP_ROWS = {
  active: [
    { title: "Examiner Pathway", meta: "Cohort 12 · starts 6 Oct 2026", state: "review", when: "Submitted 3 Sep", icon: "graduation-cap" },
    { title: "Instrument Rating Conversion", meta: "Step 3 of 5 · documents", state: "draft", when: "Edited 2 Sep", icon: "compass" },
  ],
  past: [
    { title: "Night Operations Endorsement", meta: "Cohort 8 · started 3 Mar 2026", state: "offer", when: "Accepted 12 Feb", icon: "moon-stars" },
    { title: "Examiner Pathway", meta: "Cohort 9 · 500 h minimum not met", state: "declined", when: "Closed 14 Nov 2025", icon: "graduation-cap" },
  ],
};

function ApplicationsList({ tab: initialTab = "active", empty = false, onOpen }) {
  const [tab, setTab] = React.useState(initialTab);
  const rows = APP_ROWS[tab];
  return (
    <div className="lxa-shell">
      <div className="lxa-page">
        <h1 className="lxa-h">My applications</h1>
        <p className="lxa-sub">Courses you've applied for, and drafts you haven't sent yet. Self-enrolled courses live under My courses.</p>
        <div className="lxa-tabs">
          <button className={"lxa-tab" + (tab === "active" ? " on" : "")} onClick={() => setTab("active")}>Active (2)</button>
          <button className={"lxa-tab" + (tab === "past" ? " on" : "")} onClick={() => setTab("past")}>Past (2)</button>
        </div>
        {empty ? (
          <div className="lxa-empty">
            <i className="ph ph-paper-plane-tilt"></i>
            <div className="t">No applications yet</div>
            <div className="d">Cohort programmes and advanced courses need an application. You'll find them in the catalogue.</div>
            <button className="fc-btn fc-btn-primary" style={{ marginTop: 18 }}><i className="ph ph-magnifying-glass"></i><span>Browse the catalogue</span></button>
          </div>
        ) : (
          <div className="lxa-rows">
            {rows.map((r, i) => (
              <div className="lxa-row" key={i} onClick={() => onOpen?.(r.state)}>
                <div className="ic"><i className={`ph-fill ph-${r.icon}`}></i></div>
                <div>
                  <div className="ti">{r.title}</div>
                  <div className="mt">{r.meta}</div>
                </div>
                <AppBadge state={r.state} sm />
                <div className="when">{r.when}<div style={{ marginTop: 6, color: "var(--fg-3)" }}><i className="ph ph-arrow-right"></i></div></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Entry-point artefacts ---------- */
function AppDashCard({ state = "draft", onClick }) {
  const s = APP_STATES[state];
  const tone = state === "draft" ? "draft" : state === "offer" ? "offer" : "review";
  const copy = {
    draft: { ti: "Examiner Pathway", mt: "Application draft · step 3 of 5", cta: "Continue application" },
    review: { ti: "Examiner Pathway", mt: `Application ${APP_META.ref} · submitted 3 Sep`, cta: "View application" },
    info: { ti: "Examiner Pathway", mt: "Photo ID needs replacing · respond by 11 Sep", cta: "Upload replacement" },
    offer: { ti: "Examiner Pathway", mt: "Seat offered · accept by 20 Sep", cta: "Accept my seat" },
  }[state] || { ti: "Examiner Pathway", mt: s.badge, cta: "View application" };
  return (
    <div className={`lxa-dashcard ${tone}`}>
      <div className="top">
        <div className="ic"><i className="ph-fill ph-graduation-cap"></i></div>
        <div style={{ flex: 1 }}>
          <div className="ti">{copy.ti}</div>
          <div className="mt">{copy.mt}</div>
        </div>
        <AppBadge state={state} sm />
      </div>
      {state === "draft" ? (
        <div className="lxa-mini-prog">
          <span className="lbl">3 / 5 steps</span>
          <div className="fc-track" style={{ flex: 1 }}><div className="fc-fill" style={{ width: "60%" }} /></div>
        </div>
      ) : null}
      <div className="foot">
        <button className={"fc-btn " + (state === "offer" ? "fc-btn-accent" : "fc-btn-primary")} onClick={onClick}>
          <span>{copy.cta}</span><i className="ph ph-arrow-right"></i>
        </button>
        <div className="sp" />
        {state === "draft" ? <span className="lxa-hint" style={{ marginTop: 0 }}>Closes 22 Sep</span> : null}
      </div>
    </div>
  );
}

function AppEmail({ kind = "draft" }) {
  const c = {
    draft: {
      fr: "First Class Admissions", sj: "Your Examiner Pathway application is saved",
      h: "Pick up where you left off", p: [
        "You're three steps into your application for Cohort 12. Nothing has been sent yet, and everything you entered is saved.",
        "Applications close 22 September 2026.",
      ], cta: "Continue my application",
    },
    info: {
      fr: "Dana Whitmore · First Class", sj: "Action needed: photo ID for FC-EX-2026-0184",
      h: "We need a clearer copy of your photo ID", p: [
        "The ID on your application is cropped, so we can't read the expiry date. A photo or scan showing the whole document is fine.",
        "Your eligibility check resumes as soon as you upload it. Please respond by 11 September.",
      ], cta: "Upload replacement ID",
    },
    offer: {
      fr: "First Class Admissions", sj: "You're in — Examiner Pathway Cohort 12",
      h: "You've been accepted", p: [
        "Peter recommended you after your assessment interview and admissions has confirmed a seat on Cohort 12, starting 6 October.",
        "Accept by 20 September to hold it. Nothing is charged until you accept.",
      ], cta: "Accept my seat",
    },
  }[kind];
  return (
    <div className="lxa-email">
      <div className="lxa-email-bar">
        <div className="fr">{c.fr}</div>
        <div className="sj">{c.sj}</div>
      </div>
      <div className="lxa-email-body">
        <h2>{c.h}</h2>
        {c.p.map((p, i) => <p key={i}>{p}</p>)}
        <button className="fc-btn fc-btn-primary" style={{ marginTop: 6 }}><span>{c.cta}</span><i className="ph ph-arrow-right"></i></button>
        <div className="lxa-hint" style={{ marginTop: 18 }}>Reference {APP_META.ref} · reply to this email to reach Dana directly.</div>
      </div>
    </div>
  );
}

function AppProfileMenu() {
  return (
    <div className="lxa-menu">
      <div className="lxa-menu-user">
        <div className="nm">Amara Okafor</div>
        <div className="em">amara.okafor@skylift.co</div>
      </div>
      <div className="lxa-menu-item"><i className="ph ph-user"></i>Profile</div>
      <div className="lxa-menu-item"><i className="ph ph-paper-plane-tilt"></i>My applications<span className="pill">1</span></div>
      <div className="lxa-menu-item"><i className="ph ph-certificate"></i>Records &amp; certificates</div>
      <div className="lxa-menu-item"><i className="ph ph-gear"></i>Settings</div>
      <div className="lxa-menu-item"><i className="ph ph-sign-out"></i>Sign out</div>
    </div>
  );
}

Object.assign(window, { ApplicationStatus, ApplicationsList, AppDashCard, AppEmail, AppProfileMenu, APP_ROWS });
