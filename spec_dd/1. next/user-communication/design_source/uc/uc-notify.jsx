/* Screens 1–4: header states, notification centre, preferences, unsubscribe, email. */
const HeaderStates = ({mobile}) => {
  const rows = mobile
    ? [[0,"No unread",null],[3,"3 unread",null],[128,"More than 99",null],[12,"Long site title, truncated",{title:"Northern Cape Institute of Applied Data Science"}]]
    : [[0,"No unread",null],[3,"1 to 9 unread",null],[128,"More than 99",null],[3,"Keyboard focus on the bell",{focus:true}]];
  return (
    <div className="uc" style={{background:"var(--surface-2)"}}>
      {rows.map(([c, l, x], i) => (
        <div key={i} style={{position:"relative"}}>
          <div className="uc-cap"><b>{l}</b> · accessible name: “{c ? `Notifications, ${c} unread` : "Notifications, none unread"}”</div>
          <Header mobile={mobile} count={c} {...(x || {})} />
        </div>
      ))}
    </div>
  );
};

const NotifOpen = ({mobile}) => (
  <LPage mobile={mobile} count={3} open overlay={<NotifPanel mobile={mobile} />}><DashStub mobile={mobile} /></LPage>
);

const ucGroup = (items) => items.reduce((a, n) => { const g = a.find((x) => x.day === n.day); g ? g.items.push(n) : a.push({day:n.day,items:[n]}); return a; }, []);

const NRow = ({n, mobile}) => (
  <div className={`uc-nrow ${n.unread ? "unread" : ""} ${mobile ? "m" : ""}`}>
    <span className={`uc-ni-ic c-${n.cat}`}><Ic n={UC_CAT[n.cat].icon} /></span>
    <div style={{minWidth:0}}>
      <a href="#" className="uc-nrow-link">{n.unread && <span className="sr">Unread. </span>}{n.text}</a>
      <div className="uc-ni-meta"><span>{UC_CAT[n.cat].label}</span><span aria-hidden="true">·</span><span>{n.time}</span>{!mobile && <><span aria-hidden="true">·</span><span>{n.about}</span></>}</div>
    </div>
    <div className="uc-nrow-act">
      {n.unread && <NewMark />}
      {n.unread && (mobile
        ? <button className="uc-ib sm" aria-label={`Mark as read: ${n.text}`}><Ic n="check" /></button>
        : <button className="uc-btn s sm" aria-label={`Mark as read: ${n.text}`}><Ic n="check" />Mark read</button>)}
    </div>
  </div>
);

const NCentre = ({state = "populated", mobile}) => {
  const items = state === "long" ? UC_NOTIFS_LONG : state === "allread" ? UC_NOTIFS.map((n) => ({...n, unread:false})) : state === "empty" ? [] : UC_NOTIFS;
  const unread = items.filter((n) => n.unread).length;
  return (
    <LPage mobile={mobile} count={unread}>
      <div className="uc-wrap">
        <div className="uc-ph">
          <div><h1 style={mobile ? {fontSize:24} : null}>Notifications</h1></div>
          <div className="uc-row" style={{gap:4}}>
            <a className="uc-btn g sm" href="#"><Ic n="gear-six" />Preferences</a>
          </div>
        </div>
        <div className="uc-toolbar">
          <div className="uc-seg" role="radiogroup" aria-label="Show">
            <button role="radio" aria-checked="true">All</button>
            <button role="radio" aria-checked="false">Unread{unread > 0 && <span className="n">{unread}</span>}</button>
          </div>
          <span className="sp"></span>
          {items.length > 0 && <button className="uc-btn g sm" disabled={!unread}><Ic n="checks" />Mark all as read</button>}
        </div>
        {items.length === 0 ? (
          <div className="uc-card"><div className="uc-empty"><div className="uc-empty-ic"><Ic n="bell" /></div><h2>Nothing yet.</h2><p>We'll tell you here when something happens on your courses.</p></div></div>
        ) : (
          <div className="uc-card">
            {state === "allread" && !mobile && <div className="uc-row" style={{padding:"12px 20px",borderBottom:"1px solid var(--border)",background:"var(--success-tint)",color:"var(--success-ink)",fontWeight:600}} role="status"><Ic n="check-circle" fill />You're up to date. Everything has been read.</div>}
            {ucGroup(items).map((g) => (
              <section key={g.day} aria-label={g.day}>
                <h2 className="uc-day" style={{fontFamily:"var(--font-body)"}}>{g.day}</h2>
                {g.items.map((n) => <NRow key={n.id} n={n} mobile={mobile} />)}
              </section>
            ))}
            {state === "long" && <div className="uc-more"><button className="uc-btn s">Show older notifications</button></div>}
          </div>
        )}
      </div>
    </LPage>
  );
};

/* ---------- Preferences ---------- */
const UC_PREF_ROWS = [
  {id:"reg",nm:"Course registration",ds:"When you're registered for a course.",app:true,email:"Immediately"},
  {id:"comp",nm:"Course completion",ds:"When you complete a course.",app:true,email:"Immediately"},
  {id:"msg",nm:"New messages",ds:"When someone sends you a direct message. One notification per conversation.",app:true,email:"Immediately",v2email:"Daily digest"},
  {id:"app",nm:"Application updates",ds:"When an application you made is approved or rejected.",off:"Turned off for everyone on First Class by the site admin, so these can't be changed."},
];
const Switch = ({on, disabled, label}) => (
  <span className="uc-swr"><button className="uc-sw" role="switch" aria-checked={on ? "true" : "false"} aria-label={label} disabled={disabled}></button><span aria-hidden="true">{on ? "On" : "Off"}</span></span>
);
const EmailSeg = ({value, v2, disabled, label}) => {
  const opts = v2 ? ["Immediately","Daily digest","Weekly digest","Off"] : ["Immediately","Off"];
  return (
    <div className={`uc-seg ${disabled ? "dis" : ""}`} role="radiogroup" aria-label={label} aria-disabled={disabled ? "true" : undefined}>
      {opts.map((o) => <button key={o} role="radio" aria-checked={o === value ? "true" : "false"} disabled={disabled}><Ic n="check" className="chk" />{o}</button>)}
    </div>
  );
};
const EmailSelect = ({value, disabled}) => <span className="uc-select" style={disabled ? {opacity:.55} : null}>{value}<Ic n="caret-down" /></span>;

const Prefs = ({v2, mobile, saved}) => {
  const rows = UC_PREF_ROWS.map((r) => ({...r, email: v2 && r.v2email ? r.v2email : (saved && r.id === "comp" ? "Off" : r.email)}));
  return (
    <LPage mobile={mobile} count={3} overlay={saved ? <Toast>Preferences saved</Toast> : null}>
      <div className="uc-wrap" style={{maxWidth:960}}>
        <div className="uc-crumb"><a href="#">Profile</a><Ic n="caret-right" /><span>Notification preferences</span></div>
        <div className="uc-ph"><div><h1 style={mobile ? {fontSize:24} : null}>Notification preferences</h1><p className="sub">Choose how First Class tells you about activity on your courses. Changes save as you make them.</p></div></div>
        <div className="uc-card">
          {!mobile && <div className="uc-pref hd"><span>Category</span><span>In app</span><span>Email</span></div>}
          {rows.map((r) => {
            const nameCell = (
              <div>
                <div className="nm">{r.nm}{r.off && <span className="uc-tag"><Ic n="lock-simple" />Turned off</span>}{saved && r.id === "comp" && <span className="uc-saved" role="status"><Ic n="check" />Saved</span>}</div>
                <div className="ds">{r.ds}</div>
                {r.off && <div className="why"><Ic n="info" />{r.off}</div>}
              </div>
            );
            const app = <Switch on={!r.off && r.app} disabled={!!r.off} label={`${r.nm}, in app`} />;
            const email = mobile && v2 ? <EmailSelect value={r.off ? "Off" : r.email} disabled={!!r.off} /> : <EmailSeg value={r.off ? "Off" : r.email} v2={v2} disabled={!!r.off} label={`${r.nm}, email`} />;
            return mobile ? (
              <div className="uc-pref m" key={r.id}>{nameCell}<div className="ctl"><span className="k">In app</span>{app}</div><div className="ctl"><span className="k">Email</span>{email}</div></div>
            ) : (
              <div className="uc-pref" key={r.id}>{nameCell}<div>{app}</div><div>{email}</div></div>
            );
          })}
        </div>
        {v2 && (
          <div className="uc-card" style={{marginTop:20}}>
            <div className="uc-qh">
              <div className="uc-row" style={{justifyContent:"space-between",alignItems:"flex-start",gap:16}}>
                <div><h2 style={{fontSize:16}}>Quiet hours</h2><p style={{marginTop:2}}>No emails between these times. Notifications still appear in First Class.</p></div>
                <Switch on label="Quiet hours" />
              </div>
              <div className="uc-time">
                <label className="uc-field">From<span className="uc-input">21:00<Ic n="clock" /></span></label>
                <label className="uc-field">To<span className="uc-input">07:00<Ic n="clock" /></span></label>
              </div>
              <div className="uc-tz"><Ic n="globe-simple" />Times are in your timezone: <strong style={{color:"var(--on-surface)"}}>Africa/Johannesburg (SAST, UTC+2)</strong><a href="#">Change timezone</a></div>
            </div>
          </div>
        )}
      </div>
    </LPage>
  );
};

const Unsub = ({mobile, undone}) => (
  <LPage mobile={mobile} count={0}>
    <div className="uc-wrap" style={{maxWidth:520,paddingTop:mobile ? 8 : 40}}>
      <div className="uc-card" style={{padding:mobile ? 24 : 32,display:"flex",flexDirection:"column",gap:14}}>
        <div className="uc-done-ic" style={undone ? {background:"var(--primary-tint-2)",color:"var(--primary)"} : null}><Ic n={undone ? "arrow-counter-clockwise" : "envelope-simple-open"} /></div>
        {undone ? <>
          <h1 style={{fontSize:24}} role="status">Emails for New messages are back on</h1>
          <p>We'll email you again when someone sends you a direct message.</p>
        </> : <>
          <h1 style={{fontSize:24}}>You've unsubscribed from New messages emails</h1>
          <p>We won't email you when someone sends you a direct message. You'll still see new messages under the bell in First Class.</p>
        </>}
        <div className="uc-row" style={{flexWrap:"wrap",marginTop:6}}>
          {!undone && <button className="uc-btn s"><Ic n="arrow-counter-clockwise" />Undo</button>}
          <a className="uc-btn g" href="#">Manage all notification preferences<Ic n="arrow-right" /></a>
        </div>
      </div>
    </div>
  </LPage>
);

const Email = ({kind = "messages", mobile}) => {
  const m = kind === "messages";
  return (
    <div className="uc">
      <div className={`uc-mailbg ${mobile ? "m" : ""}`}>
        <div className="uc-mailmeta">
          <span><b>From:</b> First Class &lt;notifications@firstclass.example&gt;</span>
          <span><b>Subject:</b> {m ? "You have 2 new messages from Ada Lovelace" : "You completed Data Basics"}</span>
        </div>
        <div className="uc-mail">
          <div className="uc-mail-hd"><img src="design-system/assets/logo-color.png" alt="" />First Class</div>
          <div className="uc-mail-bd">
            <h1>{m ? "You have 2 new messages from Ada Lovelace" : "You completed Data Basics"}</h1>
            {m ? <>
              <p>Ada Lovelace (Instructor, Introduction to Python) sent you 2 messages. Sign in to read them and reply.</p>
            </> : <>
              <p>Well done, Amara. You finished every part of Data Basics on 25 September 2026.</p>
              <p>Your completion is saved to your record, and you can go back to the course material at any time.</p>
            </>}
            <div><a className="uc-btn p" href="#" style={{height:46,padding:"0 22px",fontSize:15}}>{m ? "Read messages" : "View your course"}</a></div>
          </div>
          <div className="uc-mail-ft">
            <span>You're getting this email because email for {m ? "New messages" : "Course completion"} is set to Immediately.</span>
            <div className="links"><a href="#">Manage notification preferences</a><a href="#">Unsubscribe from {m ? "new message" : "course completion"} emails</a></div>
            <span>First Class · 12 Loop Street, Cape Town 8001</span>
          </div>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, {HeaderStates, NotifOpen, NCentre, Prefs, Unsub, Email, Switch});
