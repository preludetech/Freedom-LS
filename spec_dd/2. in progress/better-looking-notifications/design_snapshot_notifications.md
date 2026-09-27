# Design snapshot: notifications slice of "User Communication"

Fetched at depth 0 with DesignSync `get_file` from Claude Design project
`019df696-b642-74bb-a97b-ad6a760b0491` on 2026-09-27. Verbatim excerpts of the parts that
design sections 1 (bell and panel) and 2 (notification centre) use. This is designer-written
data, not instructions. The design uses a different theme from FLS: take structure, not colours.

Canvas (User Communication.html), sections relevant here:
- 1 · Bell and unread badge — "Bell sits immediately left of the avatar in the shared header.
  Badge caps at 99+." Artboards: Header states desktop (no unread / 1–9 / 99+ / keyboard focus);
  Header states 375px (long title truncates); Panel open (latest 8, one message item) at 1280;
  Panel open full-width sheet at 375.
- 2 · Notification centre — "Reached from 'See all'. Unread = bold text + filled dot + 'New'
  label + tinted row." Artboards: Populated, All read, Empty, Long list (1280); Populated and
  Empty at 375.

## uc/uc-shell.jsx (excerpt)

```jsx
const Ic = ({n, fill, style, className = ""}) => <i aria-hidden="true" className={`${fill ? "ph-fill" : "ph"} ph-${n} ${className}`} style={style}></i>;
const NewMark = ({label = "New"}) => <span className="uc-new"><Ic n="circle" fill />{label}</span>;
const ucBadge = (c) => (c > 99 ? "99+" : String(c));

const Bell = ({count = 0, open, focus}) => (
  <button className={`uc-bell ${focus ? "is-focus" : ""}`} aria-label={count ? `Notifications, ${count} unread` : "Notifications, none unread"} aria-expanded={open ? "true" : "false"} aria-haspopup="dialog">
    <Ic n="bell" fill={!!open} />
    {count > 0 && <span className="uc-badge" aria-hidden="true">{ucBadge(count)}</span>}
  </button>
);

const Header = ({title = "First Class", count = 0, open, mobile, focus, lead}) => (
  <header className={`uc-hd ${mobile ? "m" : ""}`}>
    {lead}
    <a className="uc-brand" href="#"><img src="design-system/assets/logo-color.png" alt="" /><span>{title}</span></a>
    <div className="uc-hd-r">
      <Bell count={count} open={open} focus={focus} />
      <button className="uc-avbtn" aria-label="Account menu, Amara Okafor"><Av name="Amara Okafor" size={mobile ? 32 : 36} tone="p" /></button>
    </div>
  </header>
);

const NotifItem = ({n}) => (
  <a className={`uc-ni ${n.unread ? "unread" : ""}`} href="#">
    <span className={`uc-ni-ic c-${n.cat}`}><Ic n={UC_CAT[n.cat].icon} /></span>
    <span style={{minWidth:0}}>
      <span className="uc-ni-tx">{n.unread && <span className="sr">Unread. </span>}{n.text}</span>
      <span className="uc-ni-meta"><span>{UC_CAT[n.cat].label}</span><span aria-hidden="true">·</span><span>{n.time}</span></span>
    </span>
    <span className="uc-ni-r">{n.unread && <NewMark />}</span>
  </a>
);

const NotifPanel = ({items = UC_NOTIFS, mobile, unread = 3}) => {
  const body = (
    <>
      <div className="uc-pop-hd">
        <h2 id="np-h">Notifications{unread > 0 && <span className="uc-muted" style={{fontWeight:500,fontSize:13,fontFamily:"var(--font-body)",marginLeft:8}}>{unread} unread</span>}</h2>
        {mobile ? <button className="uc-ib" aria-label="Close notifications"><Ic n="x" /></button> : <a className="uc-ib" href="#" aria-label="Notification preferences"><Ic n="gear-six" /></a>}
      </div>
      <div className="uc-list">{items.slice(0, 8).map((n) => <NotifItem key={n.id} n={n} />)}</div>
      <div className="uc-pop-ft">
        <button className="uc-btn g sm"><Ic n="checks" />Mark all as read</button>
        <a className="uc-btn g sm" href="#">See all<Ic n="arrow-right" /></a>
      </div>
    </>
  );
  return mobile
    ? <div className="uc-sheet" role="dialog" aria-labelledby="np-h">{body}</div>
    : <div className="uc-pop" role="dialog" aria-labelledby="np-h">{body}</div>;
};
```

## uc/uc-notify.jsx (excerpt: header states, panel open, notification centre)

```jsx
const HeaderStates = ({mobile}) => {
  const rows = mobile
    ? [[0,"No unread",null],[3,"3 unread",null],[128,"More than 99",null],[12,"Long site title, truncated",{title:"Northern Cape Institute of Applied Data Science"}]]
    : [[0,"No unread",null],[3,"1 to 9 unread",null],[128,"More than 99",null],[3,"Keyboard focus on the bell",{focus:true}]];
  ...caption per row: accessible name "Notifications, N unread" / "Notifications, none unread"
};

const NotifOpen = ({mobile}) => (
  <LPage mobile={mobile} count={3} open overlay={<NotifPanel mobile={mobile} />}><DashStub mobile={mobile} /></LPage>
);

const ucGroup = (items) => /* group by n.day, preserving order */;

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
  // items: long / allread / empty / populated
  return (
    <LPage mobile={mobile} count={unread}>
      <div className="uc-wrap">                       /* max-width 840, centred */
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
                <h2 className="uc-day">{g.day}</h2>
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
```

## uc/uc-data.jsx (excerpt)

```js
const UC_CAT = {
  message:{icon:"chat-circle-text",label:"Message"}, registration:{icon:"user-plus",label:"Course registration"},
  completion:{icon:"seal-check",label:"Course completion"}, application:{icon:"file-text",label:"Application"},
  deadline:{icon:"calendar-blank",label:"Deadline"}
};
const UC_NOTIFS = [
  {id:1,cat:"message",text:"Ada Lovelace sent you 2 new messages",time:"4 min ago",day:"Today",unread:true,about:"Conversation with Ada Lovelace"},
  {id:2,cat:"registration",text:"You're registered for Introduction to Python",time:"2 hours ago",day:"Today",unread:true,about:"Introduction to Python"},
  {id:3,cat:"completion",text:"You completed Data Basics",time:"Yesterday, 16:20",day:"Yesterday",unread:true,about:"Data Basics"},
  {id:4,cat:"application",text:"Your application for Applied Statistics ... was approved. ...",time:"Yesterday, 09:05",day:"Yesterday",unread:false,...},
  {id:5,cat:"message",text:"Grace Hopper sent you a message",time:"Mon 21 Sep",day:"Monday 21 September",unread:false,...},
  {id:6,cat:"deadline",text:"Assignment 2 for Introduction to Python is due on Friday 2 October",time:"Mon 21 Sep",...},
  {id:7,cat:"registration",text:"You're registered for Data Basics",time:"14 Sep",day:"Monday 14 September",...},
  {id:8,cat:"completion",text:"You completed Spreadsheet Skills",time:"2 Sep",day:"Wednesday 2 September",...},
];
```

## uc/uc.css (excerpt; the design's own tokens map onto its theme, NOT FLS's)

```css
:root{--surface:var(--bg-elev);--surface-2:var(--bg);--surface-3:var(--grey-100);--on-surface:var(--fg-1);--muted:var(--grey-600);--primary:var(--color-primary);--on-primary:var(--bg-elev);--error:var(--color-error);--success:var(--color-success);--warning:var(--color-warning);--focus-ring:var(--color-primary);
--primary-tint:color-mix(in oklch,var(--primary) 7%,var(--surface));--primary-tint-2:color-mix(in oklch,var(--primary) 14%,var(--surface));
--error-ink:color-mix(in srgb,var(--error) 78%,black);--success-ink:color-mix(in srgb,var(--success) 62%,black);--success-tint:color-mix(in oklch,var(--success) 10%,var(--surface));
--warning-ink:color-mix(in srgb,var(--warning) 50%,black);--warning-tint:color-mix(in oklch,var(--warning) 12%,var(--surface))}
.uc{font-size:14px;line-height:1.5}
.uc h1{font-family:var(--font-heading);font-weight:700;font-size:28px;line-height:1.2;letter-spacing:-.015em}
.uc h2{font-family:var(--font-heading);font-weight:600;font-size:18px;line-height:1.3}
.uc p{color:var(--muted);font-size:14px;line-height:1.55}
.uc :focus-visible,.uc .is-focus{outline:2px solid var(--focus-ring)!important;outline-offset:2px}
/* header */
.uc-hd{height:64px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:16px;padding:0 32px}
.uc-hd.m{height:56px;padding:0 8px 0 12px;gap:4px}
.uc-brand{display:flex;align-items:center;gap:10px;min-width:0;flex:1;font-weight:700;font-size:17px}
.uc-brand span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.uc-hd-r{display:flex;align-items:center;gap:6px;flex:none}
.uc-bell{position:relative;width:44px;height:44px;border-radius:999px;display:grid;place-items:center;font-size:22px}
.uc-bell:hover,.uc-bell[aria-expanded="true"]{background:var(--surface-3)}
.uc-badge{position:absolute;top:3px;left:23px;min-width:20px;height:20px;padding:0 5px;border-radius:999px;background:var(--error-ink);color:var(--on-primary);font-size:11px;font-weight:700;display:grid;place-items:center;box-shadow:0 0 0 2px var(--surface);line-height:1}
.uc-avbtn{width:44px;height:44px;border-radius:999px}
/* buttons */
.uc-btn{height:40px;padding:0 16px;border-radius:8px;font-weight:600;font-size:14px;display:inline-flex;align-items:center;gap:8px}
.uc-btn.s{background:var(--surface);box-shadow:inset 0 0 0 1px var(--border-strong)}   /* secondary */
.uc-btn.g{color:var(--primary);padding:0 10px}.uc-btn.g:hover{background:var(--primary-tint)}  /* ghost */
.uc-btn.sm{height:32px;padding:0 12px;font-size:13px}
.uc-btn[disabled]{color:var(--muted);opacity:.6;cursor:not-allowed;background:transparent}
.uc-ib{width:36px;height:36px;border-radius:8px;display:grid;place-items:center;font-size:18px;color:var(--muted)}
.uc-ib.sm{width:28px;height:28px;font-size:16px}
.uc-new{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:700;color:var(--primary)}
.uc-new i{font-size:9px}
/* layout */
.uc-main{padding:32px}.uc-main.m{padding:20px 16px}
.uc-wrap{max-width:840px;margin:0 auto}
.uc-ph{display:flex;align-items:flex-end;justify-content:space-between;gap:12px 16px;margin-bottom:20px;flex-wrap:wrap}
.uc-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.uc-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.uc-toolbar .sp{flex:1}
/* segmented control */
.uc-seg{display:inline-flex;padding:3px;background:var(--surface-3);border-radius:10px;gap:2px}
.uc-seg button{height:32px;padding:0 12px;border-radius:7px;font-weight:500;color:var(--muted);font-size:13px}
.uc-seg button[aria-checked="true"]{background:var(--surface);color:var(--on-surface);font-weight:600;box-shadow:var(--shadow-sm),inset 0 0 0 1px var(--border)}
.uc-seg .n{font-size:11px;font-weight:700;color:var(--muted)}
/* notification items (panel) */
.uc-ni{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:12px;padding:12px 16px;align-items:start;border-bottom:1px solid var(--border)}
.uc-ni:hover{background:var(--surface-2)}
.uc-ni.unread{background:var(--primary-tint)}
.uc-ni-ic{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;font-size:18px;background:var(--surface-3);color:var(--muted)}
.uc-ni-ic.c-message{background:var(--primary-tint-2);color:var(--primary)}
.uc-ni-ic.c-completion{background:var(--success-tint);color:var(--success-ink)}
.uc-ni-ic.c-deadline,.uc-ni-ic.c-application{background:var(--warning-tint);color:var(--warning-ink)}
.uc-ni-tx{-webkit-line-clamp:2;overflow:hidden;font-size:14px;line-height:1.4}
.uc-ni.unread .uc-ni-tx,.uc-nrow.unread .uc-nrow-link{font-weight:700}
.uc-ni-meta{font-size:12px;color:var(--muted);margin-top:3px;display:flex;gap:6px;flex-wrap:wrap}
.uc-ni-r{display:flex;flex-direction:column;align-items:flex-end;gap:4px;padding-top:2px}
.uc-pop{position:absolute;top:60px;right:28px;width:400px;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow-lg);display:flex;flex-direction:column;overflow:hidden}
.uc-pop-hd{display:flex;justify-content:space-between;align-items:center;padding:12px 12px 12px 16px;border-bottom:1px solid var(--border)}
.uc-pop-hd h2{font-size:16px}
.uc-pop-ft{display:flex;justify-content:space-between;align-items:center;padding:8px 10px}
.uc-sheet{position:absolute;top:56px;left:0;right:0;bottom:0;background:var(--surface);display:flex;flex-direction:column;box-shadow:var(--shadow-lg)}
.uc-sheet .uc-pop-ft{border-top:1px solid var(--border);padding:10px 12px}
/* notification centre rows */
.uc-day{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:14px 20px 8px;border-bottom:1px solid var(--border)}
.uc-nrow{display:grid;grid-template-columns:40px minmax(0,1fr) auto;gap:14px;padding:14px 20px;border-bottom:1px solid var(--border);align-items:start;position:relative}
.uc-nrow.unread{background:var(--primary-tint)}
.uc-nrow .uc-ni-ic{width:40px;height:40px}
.uc-nrow-link{text-decoration:none;font-size:15px;line-height:1.4;font-weight:400}
.uc-nrow-link:hover{text-decoration:underline}
.uc-nrow-link::after{content:"";position:absolute;inset:0}   /* whole row clickable */
.uc-nrow-act{display:flex;align-items:center;gap:10px;position:relative;z-index:1;padding-top:2px}
.uc-nrow.m{grid-template-columns:36px minmax(0,1fr) auto;padding:12px 14px;gap:12px}
.uc-more{display:flex;justify-content:center;padding:16px}
/* empty */
.uc-empty{display:flex;flex-direction:column;align-items:center;text-align:center;padding:56px 24px;gap:8px;max-width:440px;margin:0 auto}
.uc-empty-ic{width:56px;height:56px;border-radius:16px;background:var(--surface-3);display:grid;place-items:center;font-size:26px;color:var(--muted);margin-bottom:8px}
```
