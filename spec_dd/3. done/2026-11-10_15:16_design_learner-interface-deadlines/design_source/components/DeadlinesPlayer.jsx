/* Deadlines — course player, tablet and mobile treatments. */

const DL_MOD = { m3: "rpas-m3", m4: "rpas-m4", m7: "rpas-prac", m8: "rpas-exam", "03": "rpas-m3", "04": "rpas-m4", "07": "rpas-prac", "08": "rpas-exam" };
const DL_SEC = { "3.5": "rpas-q35" };
const dlMod = (m) => DL_MOD[m.id || m.num] ? dlById(DL_MOD[m.id || m.num]) : null;
const dlShort = (d) => d.days < 0 ? "Overdue" : d.days === 0 ? "Today" : d.date;
const DL_DONE = [
  { id: "m1", title: "Module 1 — Airspace fundamentals", date: "06 Feb", met: "Completed 04 Feb" },
  { id: "m2", title: "Module 2 — Aircraft systems", date: "20 Feb", met: "Completed 19 Feb" },
];

/* ---------- Sidebar header ---------- */
const DLSbLine = () => {
  const d = dlById("rpas-done");
  return (
    <div className="dl-sb-line">
      <div><i className="ph ph-flag-checkered"></i>Course due <strong>{d.date}</strong> · {dlRel(d)}</div>
      <div className="s"><i className="ph ph-lock-key"></i>Access ends after this date</div>
    </div>
  );
};
const DLSbNext = () => {
  const d = dlById("rpas-m3");
  return (
    <div className="dl-sb-next">
      <div className="h"><span>Next deadline</span><a href="#">All 7 →</a></div>
      <div className="t">{d.title}</div>
      <div className="r"><DLPill d={d} size="sm" /><DLCons d={d} short /></div>
    </div>
  );
};
const DLSbShortcut = ({ active }) => (
  <button className={"fc-sb-shortcut dl-sb-shortcut" + (active ? " active" : "")}>
    <i className="ph ph-calendar-check"></i><span>Deadlines</span>
    <span className="dl-pill dl-t-today sm" style={{ marginLeft: "auto" }}>1 today</span>
    <span className="fc-mono fc-sb-count" style={{ marginLeft: 6 }}>7</span>
  </button>
);
const DL_SB = { line: { sbHead: <DLSbLine /> }, next: { sbHead: <DLSbNext /> }, shortcut: { sbFoot: <DLSbShortcut /> } };

/* ---------- Outline ---------- */
const DL_OUTLINE = {
  date: {
    modMeta: (m) => { const d = dlMod(m); return d ? <span className={`dl-mod-date dl-tx-${dlTone(d)}`}><i className={`ph ph-${DL_TONE_ICON[dlTone(d)]}`}></i>{dlShort(d)}</span> : null; },
    secMeta: (s) => { const d = DL_SEC[s.id] && dlById(DL_SEC[s.id]); return d ? <span className={`dl-mod-date dl-tx-${dlTone(d)}`}>{dlShort(d)}</span> : null; },
  },
  below: {
    modBelow: (m) => { const d = dlMod(m); return d ? (
      <div className={"dl-mod-below" + (m.locked ? " locked" : "")}>
        <span className={`dl-tx-${dlTone(d)}`}><i className={`ph ph-${DL_TONE_ICON[dlTone(d)]}`}></i>{d.days === 0 ? `Due today · ${d.time}` : `Due ${d.date}`}</span>
        <DLCons d={d} short />
      </div>) : null; },
    secMeta: (s) => { const d = DL_SEC[s.id] && dlById(DL_SEC[s.id]); return d ? <DLPill d={d} size="sm" text={d.date} /> : null; },
  },
};

/* ---------- Section header ---------- */
const DL_HEADER = {
  chip: { headerChip: <DLPill d={dlById("rpas-m3")} text={`Module 3 due today · ${dlById("rpas-m3").time}`} /> },
  block: { headerRight: (
    <div className="dl-head-block">
      <DLTile d={dlById("rpas-m3")} />
      <div><div className="t">Module 3 due today</div><div className="s">{dlById("rpas-m3").time} {DL_TZ} · Target date, nothing locks</div></div>
    </div>
  ) },
};

/* ---------- Banner ---------- */
const DL_BANNER = {
  bar: { banner: (
    <div className="dl-pbar dl-pbar-today">
      <i className="ph ph-clock-countdown"></i>
      <span><strong>Module 3 is due today at 23:59 {DL_TZ}.</strong> 4 sections left, about 40 min.</span>
      <span className="dl-pbar-note"><i className="ph ph-flag"></i>Target date, nothing locks</span>
      <a href="#">All deadlines →</a>
    </div>
  ) },
  inline: { articleTop: (
    <div className="dl-inline">
      <div className="dl-inline-h"><i className="ph ph-clock-countdown"></i>Module 3 is due today at 23:59 {DL_TZ}</div>
      <p>You have 4 sections left in this module, about 40 minutes. This is a target date from your instructor, so nothing locks if you miss it.</p>
      <div className="dl-inline-next">Coming up: <strong>3.5 Section quiz</strong> · 03 Mar · marked late after this date</div>
    </div>
  ) },
};

/* ---------- Drawer / popover ---------- */
const DLDrawerItem = ({ d }) => (
  <div className={"dl-dr-item" + (d.id === "rpas-m3" ? " current" : "")}>
    <DLTile d={d} />
    <div className="b">
      <div className="k"><i className={`ph ph-${DL_KIND[d.kind].icon}`}></i>{DL_KIND[d.kind].label}<span className={`dl-tx-${dlTone(d)}`}>{dlRel(d)}</span></div>
      <div className="t">{d.title}</div>
      <div className="w">{d.dow} {d.date} · {d.time} {DL_TZ}</div>
      <DLCons d={d} />
    </div>
  </div>
);
const DLDrawer = () => {
  const groups = [["Due today", DL_RPAS.filter((d) => d.days === 0)], ["This week", DL_RPAS.filter((d) => d.days > 0 && d.days <= 7)], ["Later", DL_RPAS.filter((d) => d.days > 7)]];
  return (
    <aside className="dl-drawer">
      <div className="dl-drawer-head">
        <div><FCEyebrow>Deadlines</FCEyebrow><h4>RPAS Standard</h4></div>
        <button className="fc-icon-btn"><i className="ph ph-x"></i></button>
      </div>
      <div className="dl-drawer-tabs"><button className="on">Upcoming <span>7</span></button><button>Met <span>2</span></button></div>
      <div className="dl-drawer-list">
        {groups.map(([g, items]) => items.length ? (
          <div key={g}><div className="dl-group-h">{g}<span>{items.length}</span></div>{items.map((d) => <DLDrawerItem key={d.id} d={d} />)}</div>
        ) : null)}
      </div>
      <div className="dl-drawer-foot"><i className="ph ph-info"></i>Deadlines are set by RPAS Training Academy. Times shown in {DL_TZ}.</div>
    </aside>
  );
};
const DLPopover = () => (
  <div className="dl-pop">
    <div className="dl-pop-h"><span>RPAS Standard · 7 upcoming</span><a href="#">Open full list</a></div>
    {DL_RPAS.slice(0, 5).map((d) => (
      <div key={d.id} className={"dl-pop-row" + (d.id === "rpas-m3" ? " current" : "")}>
        <span className={`dl-pop-date dl-tx-${dlTone(d)}`}>{d.days === 0 ? "Today" : d.date}</span>
        <div className="b"><div className="t">{d.title}</div><DLCons d={d} short /></div>
      </div>
    ))}
    <div className="dl-pop-more">+ 2 later · last: course completion 31 Mar</div>
  </div>
);
const DL_DRAWER = {
  side: { drawer: <DLDrawer />, sbFoot: <DLSbShortcut active /> },
  popover: { headerChip: <span className="dl-pill dl-t-today dl-pop-anchor"><i className="ph ph-clock-countdown"></i>Module 3 due today · 23:59<i className="ph ph-caret-up"></i></span>, overlay: <DLPopover /> },
};

const DLPlayerFrame = ({ dl = {} }) => (
  <div className="lx-frame-app">
    <TopBar crumb={{ course: "RPAS Standard", module: "Module 3" }} active="courses" />
    <CoursePlayer showWidgets={false} onBack={() => {}} dl={dl} />
  </div>
);

/* ---------- Tablet & mobile ---------- */
const DLMobileList = ({ tablet }) => (
  <div className={tablet ? "dl-t-section" : "lxm-section"}>
    <div className={tablet ? "lxt-section-h" : "lxm-section-h"}>
      {tablet ? <div><h3>Deadlines</h3><p>Next 3 weeks · all courses</p></div> : <h3>Deadlines</h3>}
      <a href="#">All 9 →</a>
    </div>
    <div className="dl-m-list">{DL_ITEMS.slice(0, tablet ? 5 : 4).map((d) => <DLRow key={d.id} d={d} compact />)}</div>
  </div>
);
const DLMobileAlert = () => {
  const d = dlById("airlaw-q2");
  return (
    <div className="dl-m-alert">
      <i className="ph-fill ph-warning-circle"></i>
      <div className="b"><strong>{d.title} is {-d.days} days overdue</strong><span>{d.course} · late accepted to 06 Mar</span></div>
      <i className="ph ph-caret-right"></i>
    </div>
  );
};
const dlMobileCard = (c) => { const d = { wx: null, comms: dlById("comms"), rules: dlById("airlaw-q2") }[c.id]; return <div style={{ marginTop: 8 }}>{d ? <DLPill d={d} size="sm" text={d.days < 0 ? "Overdue" : `${d.date} · ${dlRel(d)}`} /> : <DLNone />}</div>; };
const dlTabletCard = (c) => { const d = { wx: null, comms: dlById("comms"), rules: dlById("airlaw-q2") }[c.id]; return <div style={{ marginTop: 8 }}>{d ? <DLPill d={d} size="sm" /> : <DLNone />}</div>; };
const DLMobileHero = () => <div style={{ margin: "2px 0 10px" }}><DLPill d={dlById("rpas-m3")} size="sm" text="Module 3 due today · 23:59" /></div>;

const DL_MOBILE_PLAYER = {
  banner: <div className="dl-m-pbar"><i className="ph ph-clock-countdown"></i><span><strong>Module 3 due today</strong> · 23:59</span><span className="r">4 left</span></div>,
  sheetHead: <div className="dl-m-sheetnext"><DLPill d={dlById("rpas-m3")} size="sm" text="Module 3 due today" /><a href="#">All deadlines →</a></div>,
  modMeta: DL_OUTLINE.date.modMeta,
  secMeta: DL_OUTLINE.date.secMeta,
};
const DLMobileSheet = () => (
  <div className="lxm-sheet-overlay">
    <div className="lxm-sheet">
      <div className="lxm-sheet-handle"></div>
      <div className="lxm-sheet-head"><div className="eyebrow">Deadlines</div><h4>RPAS Standard</h4></div>
      <div className="dl-m-sheetlist">{DL_RPAS.map((d) => <DLDrawerItem key={d.id} d={d} />)}</div>
    </div>
  </div>
);
const DL_TABLET_PLAYER = { sbHead: <DLSbNext />, modMeta: DL_OUTLINE.date.modMeta, headerChip: <div style={{ marginBottom: 8 }}><DLPill d={dlById("rpas-m3")} text="Module 3 due today · 23:59" /></div>, banner: DL_BANNER.bar.banner };

Object.assign(window, { DL_SB, DL_OUTLINE, DL_HEADER, DL_BANNER, DL_DRAWER, DLPlayerFrame, DLMobileList, DLMobileAlert, dlMobileCard, dlTabletCard, DLMobileHero, DL_MOBILE_PLAYER, DLMobileSheet, DL_TABLET_PLAYER });
