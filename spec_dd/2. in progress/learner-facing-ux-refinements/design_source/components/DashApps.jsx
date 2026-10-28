/* Entry points from the dashboard to My applications */

const DA_NEXT = {
  info: { nx: "Upload a replacement photo ID by 11 Sep", icon: "warning-circle", cta: "Respond", act: true },
  draft: { nx: "Step 3 of 5 · applications close 20 Oct", icon: "pencil-simple", cta: "Continue" },
  review: { nx: "Submitted today · you can still edit", icon: "clock", cta: "View" },
  interview: { nx: "Interview 12 Sep, 10:00", icon: "calendar-blank", cta: "View" },
};
const DA_ORDER = ["info", "draft", "offer", "payment", "review", "interview", "wait"];
const daActive = (ids) => AM_APPS.filter((a) => !a.past && (!ids || ids.includes(a.id))).sort((a, b) => DA_ORDER.indexOf(a.state) - DA_ORDER.indexOf(b.state));

const DaAllLink = ({ n, onClick, label = "All applications" }) => (
  <a href="#" className="da-link" onClick={(e) => { e.preventDefault(); onClick?.(); }}>{label}{n ? <span className="n">{n}</span> : null}<i className="ph ph-arrow-right"></i></a>
);

/* 1 · Strip — only rendered when there's an active application */
function DaStrip({ ids, max = 2, onOpen, onAll }) {
  const all = daActive(ids);
  if (!all.length) return null;
  const shown = all.slice(0, max);
  const need = all.filter((a) => DA_NEXT[a.state]?.act).length;
  return (
    <div className="da-strip">
      <div className="fc-section-header">
        <div>
          <h3>Your applications</h3>
          <p>{need ? `${need} needs your attention` : `${all.length} in progress`}{all.length > shown.length ? ` · showing ${shown.length} of ${all.length}` : ""}</p>
        </div>
        <DaAllLink n={all.length} onClick={onAll} />
      </div>
      <div className={"da-grid" + (shown.length === 1 ? " one" : "")}>
        {shown.map((a) => {
          const n = DA_NEXT[a.state] || { nx: a.when, icon: "clock", cta: "View" };
          return (
            <div key={a.id} className={"da-card" + (n.act ? " act" : "")} onClick={() => onOpen?.(a)}>
              <div className="ic"><i className={`ph-fill ph-${a.icon}`}></i></div>
              <div style={{ minWidth: 0 }}>
                <div className="ti">{a.title}<AppBadge state={a.state} sm /></div>
                <div className="nx"><i className={`ph ph-${n.icon}`}></i>{n.nx}</div>
              </div>
              <button className={"fc-btn fc-btn-sm " + (n.act || a.state === "draft" ? "fc-btn-primary" : "fc-btn-secondary")}><span>{n.cta}</span><i className="ph ph-arrow-right"></i></button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* 2 · Applied course card inside "Apply to enroll" (window global used by Dashboard) */
function AppliedCard({ c, app }) {
  const a = AM_APPS.find((x) => x.id === app.id);
  const draft = a.state === "draft";
  return (
    <div className="fc-card-apply da-applied" onClick={() => app.onOpen?.(a)}>
      <CourseThumb kind={c.img} size="lg" chip={<FCChip tone={draft ? "warning" : "info"} icon={draft ? "pencil-simple" : "paper-plane-tilt"}>{draft ? "Draft saved" : "Applied"}</FCChip>} />
      <div className="fc-card-body">
        <div className="fc-card-eyebrow">{c.tag}</div>
        <div className="fc-card-title" style={{ fontSize: 20 }}>{c.title}</div>
        <div className="fc-card-sub">{c.subtitle}</div>
        <div className="da-status">
          <div className="k">YOUR APPLICATION</div>
          <div style={{ marginTop: 8 }}><AppBadge state={a.state} sm /></div>
          <div className="s" style={{ marginTop: 8 }}>{draft ? "Step 3 of 5 · nothing sent yet" : `${a.ref} · submitted today · editable until review starts`}</div>
          {draft ? <div className="fc-track"><div className="fc-fill" style={{ width: "60%" }} /></div> : null}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button className="fc-btn fc-btn-primary"><span>{draft ? "Continue application" : "View application"}</span><i className="ph ph-arrow-right"></i></button>
          <button className="fc-btn fc-btn-ghost"><span>Course details</span></button>
        </div>
      </div>
    </div>
  );
}

/* 3 · Profile menu + notifications */
const DaProfileMenu = ({ onApps }) => (
  <div className="lxa-menu da-menu">
    <div className="lxa-menu-user"><div className="nm">Amara Okafor</div><div className="em">amara.okafor@skylift.co</div></div>
    <div className="lxa-menu-item"><i className="ph ph-user"></i>Profile</div>
    <div className="lxa-menu-item on" onClick={onApps}><i className="ph ph-paper-plane-tilt"></i><div style={{ flex: 1 }}>My applications<span className="sub">1 needs action</span></div><span className="pill">4</span></div>
    <div className="lxa-menu-item"><i className="ph ph-certificate"></i>Records &amp; certificates</div>
    <div className="lxa-menu-item"><i className="ph ph-gear"></i>Settings</div>
    <div className="lxa-menu-item"><i className="ph ph-sign-out"></i>Sign out</div>
  </div>
);

const DaNotifications = ({ onApps }) => (
  <div className="da-notif">
    <div className="da-notif-h">Notifications<a href="#">Mark all read</a></div>
    <div className="da-ni unread" onClick={onApps}>
      <div className="ic warn"><i className="ph ph-warning-circle"></i></div>
      <div><div className="t"><b>Action needed on BVLOS Operations.</b> Your photo ID is cropped. Upload a full copy by 11 Sep.</div><div className="go">Open application<i className="ph ph-arrow-right"></i></div><div className="w">2 HOURS AGO</div></div>
    </div>
    <div className="da-ni unread" onClick={onApps}>
      <div className="ic ok"><i className="ph ph-paper-plane-tilt"></i></div>
      <div><div className="t"><b>Examiner Pathway application received.</b> You can edit it until review starts.</div><div className="w">TODAY, 09:14</div></div>
    </div>
    <div className="da-ni">
      <div className="ic"><i className="ph ph-chat-circle"></i></div>
      <div><div className="t">Peter replied in <b>RPAS Standard</b> · Module 3 discussion</div><div className="w">YESTERDAY</div></div>
    </div>
  </div>
);

/* Full desktop dashboard with the entry points wired in */
function DaDesktop({ ids, overlay = null, onApps, onOpenApp, applied = { examiner: { id: "exp" } } }) {
  const ap = {};
  Object.keys(applied).forEach((k) => (ap[k] = { ...applied[k], onOpen: onOpenApp }));
  const any = daActive(ids).length > 0;
  return (
    <div className="da-overlay-host">
      <TopBar active="courses" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <Dashboard heroVariant="split"
          appsSlot={<DaStrip ids={ids} onOpen={onOpenApp} onAll={onApps} />}
          applyAction={any ? <DaAllLink label="My applications" onClick={onApps} /> : null}
          applied={ap} />
      </div>
      {overlay ? <div className="da-dim" /> : null}
      {overlay === "menu" ? <div className="da-pop"><DaProfileMenu onApps={onApps} /></div> : null}
      {overlay === "notif" ? <div className="da-pop" style={{ right: 64 }}><DaNotifications onApps={onApps} /></div> : null}
    </div>
  );
}

/* Clickable: dashboard → My applications → an application */
function DaProto() {
  const [screen, setScreen] = React.useState({ s: "dash" });
  const [overlay, setOverlay] = React.useState(null);
  const toApps = () => { setOverlay(null); setScreen({ s: "apps" }); };
  const toApp = (a) => { setOverlay(null); setScreen({ s: "apps", id: a.id }); };
  if (screen.s === "apps") {
    return (
      <div className="da-overlay-host">
        <TopBar active="courses" onNav={() => setScreen({ s: "dash" })} />
        <AppManage key={screen.id || "list"} variant="cards" init={screen.id ? { openId: screen.id } : {}} />
      </div>
    );
  }
  return (
    <div style={{ position: "relative", height: "100%" }} onClick={(e) => {
      if (e.target.closest(".fc-avatar")) setOverlay(overlay === "menu" ? null : "menu");
      else if (e.target.closest('.fc-icon-btn[aria-label="Notifications"]')) setOverlay(overlay === "notif" ? null : "notif");
      else if (overlay && !e.target.closest(".da-pop")) setOverlay(null);
    }}>
      <DaDesktop overlay={overlay} onApps={toApps} onOpenApp={toApp} />
    </div>
  );
}

/* ---------- Phone ---------- */
function DaMobileStrip({ ids, onAll }) {
  const all = daActive(ids);
  if (!all.length) return null;
  return (
    <div className="lxm-section">
      <div className="lxm-section-h"><h3>Your applications</h3><a href="#" onClick={(e) => { e.preventDefault(); onAll?.(); }}>All ({all.length}) →</a></div>
      <div className="da-m-list">
        {all.slice(0, 2).map((a) => {
          const n = DA_NEXT[a.state] || { nx: a.when };
          return (
            <div key={a.id} className={"da-m-row" + (n.act ? " act" : "")}>
              <div className="ic"><i className={`ph-fill ph-${a.icon}`}></i></div>
              <div style={{ flex: 1, minWidth: 0 }}><div className="ti">{a.title}</div><div className="nx">{n.nx}</div></div>
              <i className="ph ph-caret-right"></i>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const DaMobileApplied = () => {
  const a = AM_APPS.find((x) => x.id === "exp");
  return (
    <div className="da-m-applied">
      <div className="h">
        <div className="ic" style={{ background: "#1A1A2E", color: "#FF6B35" }}><i className="ph-fill ph-graduation-cap"></i></div>
        <div style={{ flex: 1 }}><div className="ti">Examiner Pathway</div><div className="sub">12 mods · 22 hrs · Cohort starts Apr 6</div></div>
      </div>
      <div className="da-status">
        <div className="k">YOUR APPLICATION</div>
        <div style={{ marginTop: 8 }}><AppBadge state={a.state} sm /></div>
        <div className="s" style={{ marginTop: 8 }}>Submitted today · editable until review starts</div>
      </div>
      <button className="fc-btn fc-btn-secondary"><span>View application</span><i className="ph ph-arrow-right"></i></button>
    </div>
  );
};

function DaMobileDash({ ids, scrollTo = null }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!scrollTo || !ref.current) return;
    const t = setTimeout(() => {
      const root = ref.current.querySelector(".lx-mobile");
      const h = [...root.querySelectorAll(".lxm-section-h h3")].find((x) => x.textContent === scrollTo);
      if (h) root.scrollTop = h.closest(".lxm-section").offsetTop - 70;
    }, 300);
    return () => clearTimeout(t);
  }, []);
  const any = daActive(ids).length > 0;
  return (
    <div ref={ref} style={{ height: "100%" }}>
      <MobileDashboard onOpenCourse={() => {}}
        appsSlot={<DaMobileStrip ids={ids} />}
        applyAction={any ? <a href="#">My applications →</a> : null}
        appliedSlot={any ? <DaMobileApplied /> : null} />
    </div>
  );
}

const DaMobileProfile = () => (
  <div className="lx-mobile" style={{ display: "flex", flexDirection: "column" }}>
    <header className="lxm-topbar"><div className="logo" style={{ fontFamily: "var(--font-heading)", fontWeight: 600 }}>Profile</div><div className="right"><button className="lxm-iconbtn"><i className="ph ph-gear"></i></button></div></header>
    <div className="da-prof">
      <div className="da-prof-user"><div className="av">AO</div><div><div className="nm">Amara Okafor</div><div className="em">amara.okafor@skylift.co</div></div></div>
      <div className="da-prof-group">
        <div className="da-prof-row on"><i className="ph ph-paper-plane-tilt"></i><div className="grow">My applications<div className="sub">1 needs action</div></div><span className="cnt">4</span><i className="ph ph-caret-right"></i></div>
        <div className="da-prof-row"><i className="ph ph-certificate"></i><div className="grow">Records &amp; certificates</div><i className="ph ph-caret-right"></i></div>
        <div className="da-prof-row"><i className="ph ph-user"></i><div className="grow">Personal details</div><i className="ph ph-caret-right"></i></div>
      </div>
      <div className="da-prof-group">
        <div className="da-prof-row"><i className="ph ph-bell"></i><div className="grow">Notifications</div><i className="ph ph-caret-right"></i></div>
        <div className="da-prof-row"><i className="ph ph-question"></i><div className="grow">Support</div><i className="ph ph-caret-right"></i></div>
        <div className="da-prof-row"><i className="ph ph-sign-out"></i><div className="grow">Sign out</div></div>
      </div>
    </div>
    <div className="lxm-tabbar" style={{ marginTop: "auto" }}>
      <button className="lxm-tab"><i className="ph ph-house"></i><span>Home</span></button>
      <button className="lxm-tab"><i className="ph ph-books"></i><span>Catalogue</span></button>
      <button className="lxm-tab"><i className="ph ph-medal"></i><span>Records</span></button>
      <button className="lxm-tab active"><i className="ph-fill ph-user"></i><span>Profile</span></button>
    </div>
  </div>
);

Object.assign(window, { DaStrip, AppliedCard, DaProfileMenu, DaNotifications, DaDesktop, DaProto, DaMobileDash, DaMobileProfile, daActive });
