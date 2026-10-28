/* Course applications — view, edit, delete/withdraw.
   Rule: drafts can be edited and deleted. Submitted applications stay editable until
   review starts; after that changes go through a change request. Submitted
   applications are withdrawn, not deleted (record kept). */

const AM_APPS = [
  { id: "irc", title: "Instrument Rating Conversion", cohort: "Cohort 4 · starts 2 Nov 2026", state: "draft", step: 3, when: "Edited 2 Sep", whenK: "LAST EDITED", keep: "Draft kept until 1 Dec", docs: 2, icon: "compass" },
  { id: "exp", title: "Examiner Pathway", cohort: "Cohort 12 · starts 6 Oct 2026", state: "review", ref: "FC-EX-2026-0184", when: "Submitted today, 09:14", whenK: "SUBMITTED", icon: "graduation-cap", editable: true },
  { id: "thm", title: "Thermal Inspection Specialist", cohort: "Cohort 2 · starts 9 Nov 2026", state: "interview", ref: "FC-TH-2026-0042", when: "Interview 12 Sep, 10:00", whenK: "NEXT", icon: "thermometer-hot" },
  { id: "bv", title: "BVLOS Operations", cohort: "Cohort 3 · starts 19 Oct 2026", state: "info", ref: "FC-BV-2026-0071", when: "Respond by 11 Sep", whenK: "DUE", icon: "broadcast" },
  { id: "noe", title: "Night Operations Endorsement", cohort: "Cohort 8 · started 3 Mar 2026", state: "offer", ref: "FC-NO-2026-0022", when: "Accepted 12 Feb", whenK: "CLOSED", icon: "moon-stars", past: true },
  { id: "ex9", title: "Examiner Pathway", cohort: "Cohort 9 · 500 h minimum not met", state: "declined", ref: "FC-EX-2025-0311", when: "Closed 14 Nov 2025", whenK: "CLOSED", icon: "graduation-cap", past: true },
];

const amKind = (a) => (a.past ? "past" : a.state === "draft" ? "draft" : "live");
const AM_REASONS = ["Timing doesn't work", "Chose another course", "Cost", "Personal reasons", "Other"];
const AM_SECTIONS = ["About you", "Licences & experience", "Documents", "Why you're applying"];

/* Primary + secondary + destructive action for each kind of application */
function amActions(a) {
  const k = amKind(a);
  if (k === "draft") return {
    primary: { id: "edit", label: "Continue editing", icon: "pencil-simple" },
    view: { id: "view", label: "View", icon: "eye" },
    danger: { id: "delete", label: "Delete draft", icon: "trash" },
  };
  if (k === "live" && a.editable) return {
    primary: { id: "edit", label: "Edit answers", icon: "pencil-simple" },
    view: { id: "view", label: "View", icon: "eye" },
    danger: { id: "withdraw", label: "Withdraw", icon: "x-circle" },
  };
  if (k === "live") return {
    primary: a.state === "info" ? { id: "view", label: "Respond", icon: "upload-simple" } : null,
    view: { id: "view", label: "View", icon: "eye" },
    change: { id: "change", label: "Request a change", icon: "note-pencil" },
    danger: { id: "withdraw", label: "Withdraw", icon: "x-circle" },
  };
  return { view: { id: "view", label: "View", icon: "eye" }, pdf: { id: "pdf", label: "Download PDF", icon: "file-arrow-down" } };
}

/* ---------- Modals ---------- */
function AmDeleteModal({ app, onCancel, onConfirm }) {
  return (
    <div className="am-modal-scrim" onClick={onCancel}>
      <div className="am-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="mk"><i className="ph ph-trash"></i></div>
        <h3>Delete this draft?</h3>
        <p>Your answers for <b>{app.title}</b> and {app.docs} uploaded documents will be permanently deleted. Nothing has been sent to admissions.</p>
        <ul className="am-conseq">
          <li><i className="ph ph-arrow-counter-clockwise"></i>You'll have a few seconds to undo.</li>
          <li><i className="ph ph-calendar-blank"></i>You can start a new application any time before applications close on 20 Oct.</li>
        </ul>
        <div className="am-modal-acts">
          <button className="fc-btn fc-btn-ghost" onClick={onCancel}><span>Keep draft</span></button>
          <button className="fc-btn fc-btn-danger" onClick={onConfirm}><i className="ph ph-trash"></i><span>Delete draft</span></button>
        </div>
      </div>
    </div>
  );
}

function AmWithdrawModal({ app, onCancel, onConfirm, reason: r0 = null }) {
  const [reason, setReason] = React.useState(r0);
  return (
    <div className="am-modal-scrim" onClick={onCancel}>
      <div className="am-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="mk"><i className="ph ph-x-circle"></i></div>
        <h3>Withdraw your application?</h3>
        <p>This ends your application for <b>{app.title}</b>, {app.cohort.split(" · ")[0]}. It can't be reopened.</p>
        <ul className="am-conseq">
          <li><i className="ph ph-users-three"></i>Your place in seat consideration ends and goes to the next applicant.</li>
          <li><i className="ph ph-credit-card"></i>Nothing has been charged.</li>
          <li><i className="ph ph-archive"></i>A record stays under Past, with a PDF of what you sent. You can apply again for a later cohort.</li>
        </ul>
        <div className="am-field">
          <label className="fc-label">Why are you withdrawing? <span style={{ color: "var(--fg-4)", fontWeight: 400 }}>Optional</span></label>
          <div className="am-chips">
            {AM_REASONS.map((x) => <button key={x} className={"am-chip" + (reason === x ? " on" : "")} onClick={() => setReason(reason === x ? null : x)}>{x}</button>)}
          </div>
        </div>
        <div className="am-modal-acts">
          <button className="fc-btn fc-btn-ghost" onClick={onCancel}><span>Keep application</span></button>
          <button className="fc-btn fc-btn-danger" onClick={onConfirm}><i className="ph ph-x-circle"></i><span>Withdraw application</span></button>
        </div>
      </div>
    </div>
  );
}

function AmChangeModal({ app, onCancel, onConfirm, section: s0 = null }) {
  const [section, setSection] = React.useState(s0);
  return (
    <div className="am-modal-scrim" onClick={onCancel}>
      <div className="am-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="mk p"><i className="ph ph-note-pencil"></i></div>
        <h3>Request a change</h3>
        <p>Review has started, so your answers are locked and the reviewer sees what you sent. Tell Dana Whitmore what needs to change and she'll reopen that section for you.</p>
        <div className="am-field">
          <label className="fc-label">Which section?</label>
          <div className="am-chips">
            {AM_SECTIONS.map((x) => <button key={x} className={"am-chip" + (section === x ? " on" : "")} onClick={() => setSection(x)}>{x}</button>)}
          </div>
        </div>
        <div className="am-field">
          <label className="fc-label">What's changed?</label>
          <textarea className="fc-input" rows={3} defaultValue={s0 ? "I renewed my RePL last week — the licence number is now 0091-5120 and the expiry date has moved to 2029." : ""} placeholder="e.g. I've logged 40 more command hours since submitting"></textarea>
        </div>
        <div className="am-modal-acts">
          <button className="fc-btn fc-btn-ghost" onClick={onCancel}><span>Cancel</span></button>
          <button className="fc-btn fc-btn-primary" onClick={onConfirm} disabled={!section}><i className="ph ph-paper-plane-tilt"></i><span>Send request</span></button>
        </div>
      </div>
    </div>
  );
}

const AmToast = ({ t, onUndo, onClose }) => (
  <div className="am-toast" role="status">
    <i className="ph-fill ph-check-circle lead"></i>
    <span>{t.msg}</span>
    {t.undo ? <button onClick={onUndo}>Undo</button> : null}
    <button className="x" onClick={onClose} aria-label="Dismiss"><i className="ph ph-x"></i></button>
  </div>
);

/* ---------- State hook shared by every layout ---------- */
function useAmState(init = {}) {
  const [apps, setApps] = React.useState(() => AM_APPS.map((a) => ({ ...a, ...(init.patch?.[a.id] || {}) })).filter((a) => !(init.removed || []).includes(a.id)));
  const [tab, setTab] = React.useState(init.tab || "active");
  const [modal, setModal] = React.useState(init.modal ? { type: init.modal, id: init.modalId } : null);
  const [toast, setToast] = React.useState(init.toast || null);
  const [menu, setMenu] = React.useState(init.menu || null);
  const [sel, setSel] = React.useState(init.sel || "irc");
  const [page, setPage] = React.useState(init.openId ? { type: "view", id: init.openId } : null); // {type:'view'|'edit', id}
  const lastDeleted = React.useRef(init.toast?.undo ? AM_APPS.find((a) => a.id === "irc") : null);

  const act = (actionId, a) => {
    setMenu(null);
    if (actionId === "view") setPage({ type: "view", id: a.id });
    else if (actionId === "edit") setPage({ type: "edit", id: a.id });
    else if (actionId === "delete" || actionId === "withdraw" || actionId === "change") setModal({ type: actionId, id: a.id });
    else if (actionId === "pdf") setToast({ msg: "Downloading " + a.ref + ".pdf" });
  };
  const confirm = () => {
    const a = apps.find((x) => x.id === modal.id);
    if (modal.type === "delete") {
      lastDeleted.current = a;
      setApps((xs) => xs.filter((x) => x.id !== a.id));
      setToast({ msg: "Draft deleted", undo: true });
      if (sel === a.id) setSel(apps.find((x) => x.id !== a.id && !x.past)?.id);
    } else if (modal.type === "withdraw") {
      setApps((xs) => xs.map((x) => (x.id === a.id ? { ...x, state: "withdrawn", past: true, when: "Withdrawn today", whenK: "CLOSED" } : x)));
      setToast({ msg: "Application withdrawn · moved to Past. We've emailed a confirmation." });
    } else if (modal.type === "change") {
      setApps((xs) => xs.map((x) => (x.id === a.id ? { ...x, changeReq: true } : x)));
      setToast({ msg: "Change request sent to Dana Whitmore" });
    }
    setModal(null);
  };
  const undo = () => {
    const a = lastDeleted.current;
    if (a) setApps((xs) => (xs.some((x) => x.id === a.id) ? xs : [a, ...xs]));
    setToast(null);
  };
  const shown = apps.filter((a) => (tab === "past" ? a.past : !a.past));
  const counts = { active: apps.filter((a) => !a.past).length, past: apps.filter((a) => a.past).length };
  const mApp = modal && apps.find((x) => x.id === modal.id);
  const overlays = (
    <>
      {modal && mApp && modal.type === "delete" ? <AmDeleteModal app={mApp} onCancel={() => setModal(null)} onConfirm={confirm} /> : null}
      {modal && mApp && modal.type === "withdraw" ? <AmWithdrawModal app={mApp} reason={init.reason} onCancel={() => setModal(null)} onConfirm={confirm} /> : null}
      {modal && mApp && modal.type === "change" ? <AmChangeModal app={mApp} section={init.section} onCancel={() => setModal(null)} onConfirm={confirm} /> : null}
      {toast ? <AmToast t={toast} onUndo={undo} onClose={() => setToast(null)} /> : null}
    </>
  );
  return { apps, shown, counts, tab, setTab, menu, setMenu, sel, setSel, page, setPage, act, overlays };
}

const AmTabs = ({ s }) => (
  <div className="lxa-tabs">
    <button className={"lxa-tab" + (s.tab === "active" ? " on" : "")} onClick={() => s.setTab("active")}>Active ({s.counts.active})</button>
    <button className={"lxa-tab" + (s.tab === "past" ? " on" : "")} onClick={() => s.setTab("past")}>Past ({s.counts.past})</button>
  </div>
);

const AmEmpty = ({ tab }) => (
  <div className="lxa-empty">
    <i className="ph ph-paper-plane-tilt"></i>
    <div className="t">{tab === "past" ? "Nothing here yet" : "No active applications"}</div>
    <div className="d">{tab === "past" ? "Withdrawn and decided applications are kept here." : "Cohort programmes need an application. You'll find them in the catalogue."}</div>
  </div>
);

const AmProg = ({ n }) => <div className="am-prog">{[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= n ? "on" : ""} />)}</div>;

/* A · Cards with visible actions */
function AmCards({ s }) {
  return (
    <div className="am-cards">
      {s.shown.map((a) => {
        const x = amActions(a);
        return (
          <div className="am-card" key={a.id}>
            <div className="ic"><i className={`ph-fill ph-${a.icon}`}></i></div>
            <div style={{ minWidth: 0 }}>
              <div className="am-ti">{a.title}{a.changeReq ? <span className="am-pill"><i className="ph ph-note-pencil"></i>Change requested</span> : null}</div>
              <div className="am-mt">{a.cohort}{a.ref ? <> · <span style={{ fontFamily: "var(--font-mono)" }}>{a.ref}</span></> : null}</div>
            </div>
            <AppBadge state={a.state} sm />
            <div className="am-card-foot">
              {a.state === "draft" ? <><AmProg n={a.step} /><span>Step {a.step} of 5</span><span>·</span><span>{a.keep}</span></> : a.editable ? <><span>{a.when}</span><span>·</span><span style={{ color: "var(--color-primary)" }}><i className="ph ph-pencil-simple"></i>Editable until review starts</span></> : <><span>{a.when}</span>{amKind(a) === "live" ? <><span>·</span><span><i className="ph ph-lock-simple"></i>Locked for review</span></> : null}</>}
              <span className="sp" />
              <div className="am-acts">
                {x.danger ? <button className="fc-btn fc-btn-ghost fc-btn-sm am-dangerlink" onClick={() => s.act(x.danger.id, a)}><i className={`ph ph-${x.danger.icon}`}></i><span>{x.danger.label}</span></button> : null}
                {x.pdf ? <button className="fc-btn fc-btn-ghost fc-btn-sm" onClick={() => s.act("pdf", a)}><i className="ph ph-file-arrow-down"></i><span>PDF</span></button> : null}
                {x.change ? <button className="fc-btn fc-btn-secondary fc-btn-sm" onClick={() => s.act("change", a)}><i className="ph ph-note-pencil"></i><span>{x.change.label}</span></button> : null}
                <button className={`fc-btn fc-btn-${x.primary ? "secondary" : "secondary"} fc-btn-sm`} onClick={() => s.act("view", a)}><i className="ph ph-eye"></i><span>View</span></button>
                {x.primary ? <button className="fc-btn fc-btn-primary fc-btn-sm" onClick={() => s.act(x.primary.id, a)}><i className={`ph ph-${x.primary.icon}`}></i><span>{x.primary.label}</span></button> : null}
              </div>
            </div>
          </div>
        );
      })}
      {!s.shown.length ? <AmEmpty tab={s.tab} /> : null}
    </div>
  );
}

/* B · Table with overflow menu */
function AmTable({ s }) {
  return (
    <div className="am-tbl">
      <div className="am-tr h"><div>COURSE</div><div>STATUS</div><div>REFERENCE</div><div>LAST ACTIVITY</div><div></div></div>
      {s.shown.map((a) => {
        const x = amActions(a);
        const open = s.menu === a.id;
        return (
          <div className="am-tr" key={a.id}>
            <div className="crs">
              <div className="ic"><i className={`ph-fill ph-${a.icon}`}></i></div>
              <div style={{ minWidth: 0 }}>
                <div className="ti">{a.title}</div>
                <div className="am-mt">{a.cohort}</div>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
              <AppBadge state={a.state} sm />
              {a.changeReq ? <span className="am-pill"><i className="ph ph-note-pencil"></i>Change requested</span> : null}
            </div>
            <div className="mono">{a.ref || "Not submitted"}</div>
            <div className="dt">{a.state === "draft" ? <>Step {a.step} of 5<div className="am-mt">{a.when}</div></> : a.when}</div>
            <div className="end">
              <button className="fc-btn fc-btn-ghost fc-btn-sm" onClick={() => s.act(x.primary ? x.primary.id : "view", a)}><span>{x.primary ? (x.primary.id === "edit" ? (a.editable ? "Edit" : "Continue") : x.primary.label) : "View"}</span></button>
              <button className={"am-icbtn" + (open ? " on" : "")} aria-label="More actions" onClick={() => s.setMenu(open ? null : a.id)}><i className="ph ph-dots-three"></i></button>
            </div>
            {open ? (
              <div className="am-menu">
                <button onClick={() => s.act("view", a)}><i className="ph ph-eye"></i>View application</button>
                {x.primary?.id === "edit" ? <button onClick={() => s.act("edit", a)}><i className="ph ph-pencil-simple"></i>{a.editable ? "Edit answers" : "Continue editing"}</button> : null}
                {a.editable ? <div className="lock"><i className="ph ph-clock"></i>Editable until the eligibility check begins.</div> : null}
                {x.change ? <button onClick={() => s.act("change", a)}><i className="ph ph-note-pencil"></i>Request a change</button> : null}
                {a.ref ? <button onClick={() => s.act("pdf", a)}><i className="ph ph-file-arrow-down"></i>Download PDF</button> : null}
                {x.change ? <div className="lock"><i className="ph ph-lock-simple"></i>Answers are locked after you submit.</div> : null}
                {x.danger ? <><hr /><button className="am-dangerlink" onClick={() => s.act(x.danger.id, a)}><i className={`ph ph-${x.danger.icon}`}></i>{x.danger.id === "delete" ? "Delete draft" : "Withdraw application"}</button></> : null}
              </div>
            ) : null}
          </div>
        );
      })}
      {!s.shown.length ? <div style={{ padding: 20 }}><AmEmpty tab={s.tab} /></div> : null}
    </div>
  );
}

/* C · List + detail */
function AmSplit({ s }) {
  const a = s.shown.find((x) => x.id === s.sel) || s.shown[0];
  if (!a) return <AmEmpty tab={s.tab} />;
  const x = amActions(a);
  const st = APP_STATES[a.state];
  const k = amKind(a);
  return (
    <div className="am-split">
      <div className="am-list">
        {s.shown.map((r) => (
          <button key={r.id} className={"am-li" + (r.id === a.id ? " on" : "")} onClick={() => s.setSel(r.id)}>
            <div className="ic"><i className={`ph-fill ph-${r.icon}`}></i></div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="ti">{r.title}</div>
              <div className="mt">{r.state === "draft" ? `Step ${r.step} of 5 · ${r.when}` : r.when}</div>
              <div className="b"><AppBadge state={r.state} sm /></div>
            </div>
          </button>
        ))}
      </div>
      <div className="am-detail">
        <AppBadge state={a.state} sm />
        <h2>{a.title}</h2>
        <p>{a.cohort}{a.ref ? <> · <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{a.ref}</span></> : null}</p>
        <div className="am-detail-grid">
          <div>
            <div className="k">PROGRESS</div>
            {k === "draft"
              ? <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--fg-2)" }}><AmProg n={a.step} />Step {a.step} of 5 · documents</div>
              : <AppTimeline items={st.tl.slice(0, 3)} />}
          </div>
          <div>
            <div className="k">YOUR ANSWERS</div>
            <dl className="lxa-kv" style={{ padding: 0, gridTemplateColumns: "120px minmax(0,1fr)" }}>
              <dt>Name</dt><dd>{APP_VALUES.legalName}</dd>
              <dt>Licence</dt><dd>{APP_VALUES.licence}</dd>
              <dt>Documents</dt><dd>{k === "draft" ? `${a.docs} of 4 uploaded` : "4 files attached"}</dd>
            </dl>
          </div>
        </div>
        <div className="am-detail-acts">
          {x.primary ? <button className="fc-btn fc-btn-primary" onClick={() => s.act(x.primary.id, a)}><i className={`ph ph-${x.primary.icon}`}></i><span>{x.primary.label}</span></button> : null}
          <button className="fc-btn fc-btn-secondary" onClick={() => s.act("view", a)}><i className="ph ph-arrow-square-out"></i><span>Open full application</span></button>
          {x.change ? <button className="fc-btn fc-btn-secondary" onClick={() => s.act("change", a)}><i className="ph ph-note-pencil"></i><span>Request a change</span></button> : null}
          {x.pdf ? <button className="fc-btn fc-btn-ghost" onClick={() => s.act("pdf", a)}><i className="ph ph-file-arrow-down"></i><span>Download PDF</span></button> : null}
          <span className="sp" />
          {x.danger ? <button className="fc-btn fc-btn-ghost am-dangerlink" onClick={() => s.act(x.danger.id, a)}><i className={`ph ph-${x.danger.icon}`}></i><span>{x.danger.id === "delete" ? "Delete draft" : "Withdraw application"}</span></button> : null}
        </div>
        <div className="am-detail-note"><i className={`ph ph-${k === "draft" ? "floppy-disk" : a.editable ? "clock" : k === "live" ? "lock-simple" : "archive"}`}></i>
          {k === "draft" ? `Only you can see a draft. ${a.keep}.` : k === "live" && a.editable ? "You can edit your answers until the eligibility check begins, usually within a working day of submitting." : k === "live" ? (a.changeReq ? "Change request sent. Dana will reopen the section or reply by message." : "Answers are locked after you submit. Use a change request if something's wrong.") : "Kept on file. You can apply again for a later cohort."}
        </div>
      </div>
    </div>
  );
}

/* ---------- Page ---------- */
function AppManage({ variant = "cards", device = "desktop", init = {} }) {
  const s = useAmState(init);
  if (s.page) {
    const a = s.apps.find((x) => x.id === s.page.id) || AM_APPS[0];
    if (s.page.type === "edit") return <ApplicationWizard step={a.step || 5} onExit={() => s.setPage(null)} onSubmit={() => s.setPage(null)} />;
    return <ApplicationStatus state={a.state} editWindow={!!a.editable} onBack={() => s.setPage(null)} onContinue={() => s.setPage({ type: "edit", id: a.id })} onEdit={() => s.setPage({ type: "edit", id: a.id })} />;
  }
  const Body = variant === "table" ? AmTable : variant === "split" ? AmSplit : AmCards;
  return (
    <div className="am-wrap am-contained">
    <div className={"am" + (device === "tablet" ? " am-tab" : "")} onClick={(e) => { if (s.menu && !e.target.closest(".am-menu,.am-icbtn")) s.setMenu(null); }}>
      <div className={"lxa-page" + (variant === "split" ? " wide" : "")} style={device === "tablet" ? { padding: 28 } : null}>
        <div className="am-head">
          <div className="grow">
            <h1 className="lxa-h">My applications</h1>
            <p className="lxa-sub">Drafts can be edited or deleted. After you submit, you can edit until review starts, then request changes. Submitted applications can be withdrawn.</p>
          </div>
        </div>
        <AmTabs s={s} />
        <Body s={s} />
      </div>
    </div>
      {s.overlays}
    </div>
  );
}

/* Rules summary artboard */
const AmRules = () => (
  <div className="am-rules">
    <h2>What a learner can do, by status</h2>
    <p>Delete only exists for drafts. Anything submitted is withdrawn instead, so admissions keeps a record.</p>
    <div className="am-rule h"><div>STATUS</div><div>VIEW</div><div>EDIT</div><div>REMOVE</div></div>
    <div className="am-rule"><div><b>Draft</b><div className="am-mt">Not sent</div></div><div>Yes</div><div><b>Yes</b> · continue the form</div><div><b>Delete</b> · confirm, then undo for a few seconds</div></div>
    <div className="am-rule"><div><b>Submitted, review not started</b><div className="am-mt">Usually up to a working day</div></div><div>Yes</div><div><b>Yes</b> · edit answers directly</div><div><b>Withdraw</b> · confirm with consequences, optional reason</div></div>
    <div className="am-rule"><div><b>Under review, before decision</b><div className="am-mt">Eligibility, interview, waitlist, payment</div></div><div>Yes · read-only</div><div><b>Request a change</b> · admissions reopens a section</div><div><b>Withdraw</b></div></div>
    <div className="am-rule"><div><b>Info requested</b></div><div>Yes</div><div><b>Only the requested section</b> reopens</div><div>Withdraw</div></div>
    <div className="am-rule"><div><b>Past</b><div className="am-mt">Accepted, declined, withdrawn</div></div><div>Yes · plus PDF</div><div className="no">No</div><div className="no">No · kept on file</div></div>
  </div>
);

Object.assign(window, { AM_APPS, amActions, amKind, AM_REASONS, AmProg, AmToast, AppManage, AmRules, useAmState });
