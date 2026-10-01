/* Screens 8, 9, 11: educator inbox, quick view Messages tab, report queue. */
const EDU_ADA_THREAD = UC_ADA_THREAD;

const EduFilters = ({mobile, unread = 3}) => (
  <div className="uc-toolbar" style={{marginBottom:0,padding:mobile ? "0 0 12px" : "12px 16px",borderBottom:mobile ? 0 : "1px solid var(--border)"}}>
    <div className="uc-seg" role="radiogroup" aria-label="Show">
      <button role="radio" aria-checked="true">All</button>
      <button role="radio" aria-checked="false">Unread{unread > 0 && <span className="n">{unread}</span>}</button>
    </div>
    <button className="uc-select" aria-label="Filter by cohort" style={{height:38}}><Ic n="users-three" />All cohorts<Ic n="caret-down" /></button>
  </div>
);

/* state: populated | empty | twoOrg */
const EInbox = ({state = "populated", mobile, view = "list"}) => {
  const multi = state === "twoOrg";
  const empty = state === "empty";
  const head = (
    <div className="uc-ph" style={{marginBottom:16}}>
      <div>
        <h1 style={mobile ? {fontSize:24} : null}>Messages</h1>
        <div className="uc-ctxbar"><Ic n="buildings" />Conversations with learners in <strong style={{color:"var(--on-surface)"}}>Northwind Academy</strong>{multi && !mobile && <span>· Switch organisation in the sidebar to see Riverside College.</span>}</div>
      </div>
      {!empty && <button className="uc-btn p"><Ic n="pencil-simple-line" />New message</button>}
    </div>
  );
  const shell = {mobile, admin:false, multiOrg:multi, orgOpen:multi && !mobile, msgCount:empty ? 0 : 3, count:empty ? 0 : 3};
  if (empty) return (
    <EduShell {...shell}>
      {head}
      <div className="uc-card"><div className="uc-empty"><div className="uc-empty-ic"><Ic n="chat-circle-text" /></div><h2>No conversations yet</h2><p>You haven't messaged any learners in Northwind Academy. Start a conversation from a learner's quick view or with New message.</p><button className="uc-btn p"><Ic n="pencil-simple-line" />New message</button></div></div>
    </EduShell>
  );
  if (mobile && view === "thread") return (
    <div className="uc">
      <Header mobile count={3} lead={<button className="uc-ib" aria-label="Open educator menu"><Ic n="list" /></button>} />
      <Thread mobile meId="ada" otherId="amara" groups={EDU_ADA_THREAD} course="Python · Sep 2026 · Northwind Academy" />
    </div>
  );
  if (mobile) return (
    <EduShell {...shell}>
      {head}
      {multi && <div className="uc-note" style={{marginBottom:12}}><Ic n="buildings" /><div className="b" style={{marginTop:0}}>You also have 1 unread in Riverside College. Switch organisation from the menu.</div></div>}
      <EduFilters mobile />
      <div className="uc-card" style={{margin:"0 -16px",borderRadius:0,borderLeft:0,borderRight:0}}>{UC_ECONVS.map((c) => <ConvItem key={c.id} c={c} />)}</div>
    </EduShell>
  );
  return (
    <EduShell {...shell}>
      {head}
      <div className="uc-ibx">
        <ConvList convs={UC_ECONVS} selected="amara" head={<EduFilters />} />
        <Thread meId="ada" otherId="amara" groups={EDU_ADA_THREAD} course="Python · Sep 2026 · Northwind Academy" />
      </div>
    </EduShell>
  );
};

/* ---------- Quick view ---------- */
const QV_LEARNERS = [
  ["amara","Python · Sep 2026","Today"],["tomas","Python · Sep 2026","Today"],["priya","Data Basics · Self-paced","Yesterday"],
  ["chen","Data Basics · Self-paced","3 days ago"],["lebo","Python · Sep 2026","Mon"],["fatima","Python · Jan 2026","2 Sep"],
];
/* state: conv | none | denied */
const QuickView = ({state = "conv", mobile}) => {
  const id = state === "conv" ? "amara" : state === "none" ? "priya" : "chen";
  const p = UC_PEOPLE[id];
  const email = p.name.toLowerCase().replace(/[^a-z ]/g, "").replace(" ", ".") + "@mail.example";
  const panel = (
    <aside className={`uc-qv ${mobile ? "m" : ""}`} aria-label={`Quick view: ${p.name}`}>
      <div className="uc-qv-hd">
        <Av name={p.name} size={48} />
        <div className="who"><div className="nm">{p.name}</div><div className="em">{email}</div><div className="uc-row" style={{gap:6,marginTop:6,flexWrap:"wrap"}}><span className="uc-tag ok"><Ic n="check-circle" fill />Active member</span><span className="uc-tag">{QV_LEARNERS.find((l) => l[0] === id)[1]}</span></div></div>
        <button className="uc-ib" aria-label="Close quick view"><Ic n={mobile ? "x" : "x"} /></button>
      </div>
      <div className="uc-tabs" role="tablist">
        <button role="tab" aria-selected="false">Details</button>
        <button role="tab" aria-selected="true">Messages</button>
      </div>
      {state === "conv" && <>
        <div className="uc-row" style={{justifyContent:"space-between",padding:"10px 20px",borderBottom:"1px solid var(--border)",fontSize:13}}><span className="uc-muted">Showing the latest messages</span><a href="#">Open in Messages</a></div>
        <Thread noHeader mobile meId="ada" otherId="amara" groups={EDU_ADA_THREAD.slice(3)} />
      </>}
      {state === "none" && <>
        <div style={{flex:1,display:"flex",alignItems:"center",justifyContent:"center",padding:24,textAlign:"center"}}><div style={{display:"flex",flexDirection:"column",gap:6,alignItems:"center"}}><div className="uc-empty-ic" style={{marginBottom:4}}><Ic n="chat-circle-text" /></div><h3>No messages with Priya yet</h3><p style={{fontSize:13}}>Write below to start a conversation.</p></div></div>
        <Composer to="priya" mobile value="Hi Priya, I've left comments on your project. Have a look when you can." focus />
      </>}
      {state === "denied" && (
        <div style={{padding:20}}>
          <div className="uc-note" role="status"><Ic n="lock-simple" /><div><div className="h">You can't message Chen Wei</div><div className="b">Messaging isn't turned on for the Data Basics · Self-paced cohort. An organisation admin can turn it on in the cohort's settings.</div></div></div>
        </div>
      )}
    </aside>
  );
  return (
    <EduShell mobile={mobile} active="learners" overlay={panel}>
      <div className="uc-ph" style={{marginBottom:16}}><h1>Learners</h1></div>
      <div className="uc-card">
        <table className="uc-tbl"><thead><tr><th>Name</th><th>Cohort</th><th>Last active</th></tr></thead>
          <tbody>{QV_LEARNERS.map(([lid, c, t]) => <tr key={lid} className={lid === id ? "sel" : ""}><td><span className="uc-row"><Av name={UC_PEOPLE[lid].name} size={28} />{UC_PEOPLE[lid].name}</span></td><td>{c}</td><td>{t}</td></tr>)}</tbody>
        </table>
      </div>
    </EduShell>
  );
};

/* ---------- Report queue ---------- */
const CtxMsg = ({id, text, time, rep, hidden}) => (
  <div className={`uc-cm ${rep ? "rep" : ""}`}>
    <Av name={UC_PEOPLE[id].name} size={28} />
    <div>
      <div className="h"><strong>{UC_PEOPLE[id].name}</strong><Role r={UC_PEOPLE[id].role} /><time>{time}</time>{rep && <span className="uc-tag err"><Ic n="flag" fill />Reported message</span>}</div>
      {hidden
        ? <><div className="uc-bub hidden" style={{display:"inline-flex"}}><Ic n="eye-slash" />This message was hidden by a moderator.</div><div className="uc-stored"><strong style={{color:"var(--on-surface)"}}>Stored text, visible to site admins only:</strong> {text}</div></>
        : <div className="uc-bub">{text}</div>}
    </div>
  </div>
);

const REPORTS = [
  {id:1,reason:"Other",note:"He keeps asking for my quiz answers.",by:"amara",time:"2 hours ago",between:["marcus","amara"],
    ctx:[["marcus","Send me your quiz answers.","21:14"],["amara","No, we're meant to do the quiz on our own.","21:15"],["marcus","Come on. Just send them or I'll tell the instructor you copied mine.","21:18",true]]},
  {id:2,reason:"Spam",by:"priya",time:"Yesterday, 13:02",between:["jordan","priya"],
    ctx:[["jordan","Hi! Are you on the Data Basics course?","12:40"],["jordan","Earn R5,000 a week from home. Message me for the link.","12:41",true]]},
];
const RESOLVED = [
  {id:3,reason:"Harassment",by:"fatima",time:"23 Sep, 18:40",between:["jordan","fatima"],action:"hidden",who:"Sam Rivera",when:"24 Sep 2026, 14:10",
    ctx:[["fatima","Please stop messaging me.","18:31"],["jordan","You can't ignore me forever.","18:38",true]]},
  {id:4,reason:"Inappropriate",by:"lebo",time:"19 Sep, 10:15",between:["chen","lebo"],action:"dismissed",who:"Sam Rivera",when:"20 Sep 2026, 09:02",
    ctx:[["chen","That quiz was brutal, I nearly threw my laptop.","10:12",true]]},
];

const ReportCard = ({r, mobile}) => (
  <article className="uc-rep" aria-label={`Report: ${r.reason}`}>
    <div className="uc-rep-hd">
      <div className="uc-rep-meta">
        <div className="l1"><span className="uc-tag err"><Ic n="flag" />{r.reason}</span><span>Reported by {UC_PEOPLE[r.by].name}</span><Role r={UC_PEOPLE[r.by].role} /></div>
        <div className="l2">{r.time} · Conversation between {UC_PEOPLE[r.between[0]].name} and {UC_PEOPLE[r.between[1]].name}</div>
      </div>
      {r.action && <span className={`uc-tag ${r.action === "hidden" ? "warn" : ""}`}><Ic n={r.action === "hidden" ? "eye-slash" : "check"} />{r.action === "hidden" ? "Message hidden" : "Dismissed"}</span>}
    </div>
    {r.note && <div className="uc-rep-why"><span className="k">Reporter's note</span>{r.note}</div>}
    <div className="uc-ctx">
      <div className="uc-ctx-h"><Ic n="chats" />Context · last {r.ctx.length} message{r.ctx.length > 1 ? "s" : ""}</div>
      {r.ctx.map(([id, t, tm, rep], i) => <CtxMsg key={i} id={id} text={t} time={tm} rep={rep} hidden={rep && r.action === "hidden"} />)}
    </div>
    {r.action ? (
      <div className="uc-rep-res"><Ic n="user-check" /><span>{r.action === "hidden" ? "Hidden" : "Dismissed"} by <strong>{r.who}</strong> (Site admin) on {r.when}</span></div>
    ) : (
      <div className="uc-rep-act">
        <button className="uc-btn d"><Ic n="eye-slash" />Hide message</button>
        <button className="uc-btn s">Dismiss report</button>
        {!mobile && <span className="uc-muted" style={{fontSize:13}}>Hiding keeps the message stored and replaces it for both people.</span>}
      </div>
    )}
  </article>
);

const ReportQueue = ({filter = "open", mobile}) => (
  <EduShell mobile={mobile} active="reports" admin repCount={2}>
    <div className="uc-ph" style={{marginBottom:16}}><div><h1 style={mobile ? {fontSize:24} : null}>Reports</h1><p className="sub">Messages people have reported anywhere on First Class.</p></div></div>
    <div className="uc-toolbar">
      <div className="uc-seg" role="radiogroup" aria-label="Show">
        <button role="radio" aria-checked={filter === "open" ? "true" : "false"}>Open<span className="n">2</span></button>
        <button role="radio" aria-checked={filter === "resolved" ? "true" : "false"}>Resolved</button>
      </div>
    </div>
    <div style={{display:"flex",flexDirection:"column",gap:16,maxWidth:880}}>
      {(filter === "open" ? REPORTS : RESOLVED).map((r) => <ReportCard key={r.id} r={r} mobile={mobile} />)}
    </div>
  </EduShell>
);

Object.assign(window, {EInbox, QuickView, ReportQueue});
