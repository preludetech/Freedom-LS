/* Shared shell: icons, avatars, header + bell, notification panel, educator layout. */
const Ic = ({n, fill, style, className = ""}) => <i aria-hidden="true" className={`${fill ? "ph-fill" : "ph"} ph-${n} ${className}`} style={style}></i>;
const ucInitials = (name) => name.split(" ").map((s) => s[0]).slice(0, 2).join("");
const ucTone = (name) => "t" + ((name.charCodeAt(0) + name.length) % 4 + 1);
const Av = ({name, size = 36, tone, sq}) => <span className={`uc-av ${tone || ucTone(name)} ${sq ? "sq" : ""}`} style={{width:size,height:size,fontSize:Math.round(size*0.36)}} aria-hidden="true">{ucInitials(name)}</span>;
const Role = ({r}) => <span className={`uc-role r-${r.toLowerCase().replace(/\s/g, "")}`}>{r}</span>;
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

const LPage = ({mobile, count = 0, open, title, children, overlay, flush}) => (
  <div className="uc">
    <Header mobile={mobile} count={count} open={open} title={title} />
    <main className={`uc-main ${mobile ? "m" : ""} ${flush ? "flush" : ""}`}>{children}</main>
    {overlay}
  </div>
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

const Toast = ({children, icon = "check-circle"}) => <div className="uc-toast" role="status"><Ic n={icon} fill />{children}</div>;

const DashStub = ({mobile}) => (
  <div className="uc-dash uc-wrap" style={{maxWidth:1100}}>
    <h1 style={{fontSize: mobile ? 24 : 28}}>My courses</h1>
    <div className="uc-dash-g" style={mobile ? {gridTemplateColumns:"1fr"} : null}>
      {[["Introduction to Python",42],["Data Basics",100],["Spreadsheet Skills",100]].slice(0, mobile ? 2 : 3).map(([t, v]) => (
        <div className="uc-dash-c" key={t}><div className="ph">course image</div><h3>{t}</h3><div className="uc-bar"><div style={{width:v+"%"}}></div></div><span className="uc-muted" style={{fontSize:13}}>{v === 100 ? "Completed" : v + "% complete"}</span></div>
      ))}
    </div>
  </div>
);

const UC_ORGS = [{id:"nw",name:"Northwind Academy",unread:3},{id:"rv",name:"Riverside College",unread:1}];

const EduSidebar = ({active = "messages", admin, orgOpen, multiOrg, msgCount = 3, repCount = 2}) => (
  <nav className="uc-side" aria-label="Educator">
    <button className="uc-org" aria-haspopup="menu" aria-expanded={orgOpen ? "true" : "false"} aria-label="Organisation: Northwind Academy. Switch organisation">
      <Av name="Northwind Academy" size={32} sq tone="t1" />
      <div><div className="n">Northwind Academy</div><div className="s">{multiOrg ? "1 of 2 organisations" : "Organisation"}</div></div>
      {multiOrg && <Ic n="caret-up-down" style={{color:"var(--muted)"}} />}
    </button>
    {orgOpen && (
      <div className="uc-orgmenu" role="menu" aria-label="Switch organisation">
        <div className="h">Your organisations</div>
        {UC_ORGS.map((o, i) => (
          <button key={o.id} role="menuitemradio" aria-checked={i === 0 ? "true" : "false"}>
            <Av name={o.name} size={28} sq tone={i ? "t2" : "t1"} />
            <span style={{fontWeight:600,fontSize:13}}>{o.name}</span>
            <span className="on"><span className="uc-muted" style={{fontSize:12}}>{o.unread} unread</span>{i === 0 && <Ic n="check" style={{color:"var(--primary)"}} />}</span>
          </button>
        ))}
      </div>
    )}
    {[["overview","squares-four","Overview"],["learners","users","Learners"],["cohorts","users-three","Cohorts"],["courses","books","Courses"],["messages","chat-circle-text","Messages"]].map(([id, ic, l]) => (
      <a key={id} href="#" className="uc-nav" aria-current={active === id ? "page" : undefined}>
        <Ic n={ic} fill={active === id} />{l}
        {id === "messages" && msgCount > 0 && <span className="uc-cnt" aria-label={`${msgCount} unread`}>{msgCount}</span>}
      </a>
    ))}
    {admin && <>
      <div className="uc-navl">Site admin</div>
      <a href="#" className="uc-nav" aria-current={active === "reports" ? "page" : undefined}><Ic n="flag" fill={active === "reports"} />Reports{repCount > 0 && <span className="uc-cnt" aria-label={`${repCount} open`}>{repCount}</span>}</a>
      <a href="#" className="uc-nav"><Ic n="gear-six" />Site settings</a>
    </>}
  </nav>
);

const EduShell = ({mobile, count = 3, children, overlay, ...side}) => (
  <div className="uc">
    <Header mobile={mobile} count={count} lead={mobile ? <button className="uc-ib" aria-label="Open educator menu"><Ic n="list" /></button> : null} />
    <div className="uc-edu">
      {!mobile && <EduSidebar {...side} />}
      <main className={`uc-edu-main ${mobile ? "m" : ""}`}>{children}</main>
      {overlay}
    </div>
  </div>
);

Object.assign(window, {Ic, Av, Role, NewMark, Bell, Header, LPage, NotifItem, NotifPanel, Toast, DashStub, EduSidebar, EduShell, ucBadge});
