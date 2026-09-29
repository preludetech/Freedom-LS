/* Screens 5–7, 10: conversation list, thread, composer, recipient picker, report + block dialogs. */
const P = (id) => UC_PEOPLE[id];

const ConvItem = ({c, selected, showCourse = true}) => {
  const p = P(c.p);
  return (
    <a href="#" className={`uc-ci ${c.unread ? "unread" : ""} ${c.blocked ? "blocked" : ""}`} aria-current={selected ? "true" : undefined}>
      <Av name={p.name} size={40} />
      <span style={{minWidth:0}}>
        <span className="uc-ci-n"><strong>{p.name}</strong><Role r={p.role} /></span>
        {showCourse && <span className="uc-ci-sub" style={{display:"block"}}>{c.course}</span>}
        <span className="uc-ci-p" style={{display:"block"}}>{c.unread ? <span className="sr">Unread. </span> : null}{c.last}</span>
      </span>
      <span className="uc-ci-r">
        <time>{c.time}</time>
        {c.unread ? <NewMark label={c.unread > 1 ? `${c.unread} new` : "New"} /> : null}
        {c.blocked ? <span className="uc-tag"><Ic n="prohibit" />Blocked</span> : null}
      </span>
    </a>
  );
};

const ConvList = ({convs, selected, head}) => (
  <div className="uc-cl">
    {head}
    <div className="uc-cl-list" role="list">{convs.map((c) => <ConvItem key={c.id} c={c} selected={c.id === selected} />)}</div>
  </div>
);

const Composer = ({to, mobile, value = "", focus}) => (
  <div className={`uc-cmp ${mobile ? "m" : ""}`}>
    <div className="uc-who" id={`who-${to}`}><Ic n="eye" />Only <strong>{P(to).name}</strong> ({P(to).role}) will see this.</div>
    <div className="uc-cmp-row">
      <textarea className={`uc-ta ${focus ? "is-focus" : ""}`} rows={value ? 2 : 1} placeholder={`Write a message to ${P(to).name.split(" ")[0]}`} aria-label={`Message to ${P(to).name}`} aria-describedby={`who-${to}`} defaultValue={value}></textarea>
      <button className="uc-btn p" disabled={!value}><Ic n="paper-plane-right" fill />{!mobile && "Send"}{mobile && <span className="sr">Send</span>}</button>
    </div>
  </div>
);

const MsgGroup = ({g, meId, menuOpen, mobile, retry}) => {
  const mine = g.from === meId, p = P(g.from);
  const texts = g.hidden ? [null] : g.texts;
  return (
    <div className={`uc-mg ${mine ? "me" : ""}`}>
      {!mine && <Av name={p.name} size={32} />}
      <div className="uc-mg-c">
        <div className="uc-mg-hd"><strong>{mine ? "You" : p.name}</strong>{!mine && <Role r={p.role} />}<time>{g.time}</time></div>
        {texts.map((t, i) => (
          <div className="uc-mrow" key={i} style={{position:"relative"}}>
            {g.hidden
              ? <div className="uc-bub hidden"><Ic n="eye-slash" />This message was hidden by a moderator.</div>
              : <div className={`uc-bub ${g.failed ? "failed" : ""}`}>{t}</div>}
            {!mine && !g.hidden && <button className={`uc-ib sm ${menuOpen && i === texts.length - 1 ? "on is-focus" : ""}`} aria-label={`More actions for message from ${p.name}`} aria-haspopup="menu" aria-expanded={menuOpen && i === texts.length - 1 ? "true" : "false"}><Ic n="dots-three-vertical" /></button>}
            {menuOpen && i === texts.length - 1 && (
              <div className="uc-menu" role="menu" style={mobile ? {top:"calc(100% + 4px)",right:0} : {top:"calc(100% + 4px)",left:"calc(100% - 30px)"}}>
                <button role="menuitem" className="is-hover"><Ic n="flag" />Report message</button>
                <button role="menuitem" className="danger"><Ic n="prohibit" />Block {p.name}</button>
              </div>
            )}
          </div>
        ))}
        {g.failed && <div className="uc-fail" role="alert"><Ic n="warning-circle" fill />Not sent. Check your connection.<button>Retry</button></div>}
      </div>
    </div>
  );
};

/* mode: normal | new | closed | blocked */
const Thread = ({meId = "amara", otherId, groups = [], course, mode = "normal", closed, failed, mobile, menuOpen, value, focus, noHeader}) => {
  const o = P(otherId);
  const gs = failed ? [...groups, {from:meId,time:"10:51",texts:["Will do. Is section 4.3 part of the week 3 quiz?"],failed:true}] : groups;
  return (
    <section className={`uc-th ${mobile ? "m" : ""}`} aria-label={`Conversation with ${o.name}`}>
      {!noHeader && (
        <div className="uc-th-hd">
          {mobile && <a href="#" className="uc-ib" aria-label="Back to messages"><Ic n="arrow-left" /></a>}
          <Av name={o.name} size={mobile ? 32 : 40} />
          <div className="who"><div className="nm" style={mobile ? {fontSize:15} : null}>{o.name}<Role r={o.role} /></div><div className="ctx">{course}</div></div>
          <button className="uc-ib" aria-label="Conversation options" aria-haspopup="menu"><Ic n="dots-three" /></button>
        </div>
      )}
      {mode === "blocked" && (
        <div className="uc-banner" role="status"><Ic n="prohibit" /><span className="t"><strong>You blocked {o.name}.</strong> They can't message you, and you won't see new messages from them.</span><button className="uc-btn s sm">Unblock</button></div>
      )}
      <div className="uc-th-body">
        {mode === "new" ? (
          <div className="uc-start"><Av name={o.name} size={56} /><h2>{o.name} <Role r={o.role} /></h2><p>{course}</p><p>This is the start of your conversation.</p></div>
        ) : gs.map((g, i) => g.sep ? <div className="uc-sep" key={i}>{g.sep}</div> : <MsgGroup key={i} g={g} meId={meId} mobile={mobile} menuOpen={menuOpen && g.rep} />)}
      </div>
      {mode === "closed" ? (
        <div className={`uc-cmp ${mobile ? "m" : ""}`}><div className="uc-note" role="status"><Ic n="lock-simple" /><div><div className="h">{closed.h}</div><div className="b">{closed.b}</div></div></div></div>
      ) : mode === "blocked" ? null : <Composer to={otherId} mobile={mobile} value={value} focus={focus} />}
    </section>
  );
};

const UC_CLOSED = {
  config:{h:"You can't reply to this conversation",b:"Messaging with instructors on Introduction to Python has been turned off. You can still read earlier messages."},
  left:{h:"Grace Hopper has left Northwind Academy",b:"You can't reply, but you can still read earlier messages."},
};

const InboxHead = ({mobile, canNew = true}) => (
  <div className="uc-ph" style={{marginBottom:16}}>
    <h1 style={mobile ? {fontSize:24} : null}>Messages</h1>
    {canNew && <button className="uc-btn p"><Ic n="pencil-simple-line" />New message</button>}
  </div>
);

/* state: populated | emptyCan | emptyNo | blocked  · thread: props for the open thread */
const LInbox = ({state = "populated", mobile, view = "list", thread, overlay, count = 3}) => {
  const convs = state === "blocked" ? [...UC_LCONVS, UC_BLOCKED_CONV] : UC_LCONVS;
  const th = thread || (state === "blocked"
    ? {otherId:"marcus",groups:UC_MARCUS_THREAD.slice(0, 5),course:"Introduction to Python",mode:"blocked"}
    : {otherId:"ada",groups:UC_ADA_THREAD,course:"Introduction to Python"});
  const sel = th.otherId;
  if (state === "emptyCan" || state === "emptyNo") {
    return (
      <LPage mobile={mobile} count={0} overlay={overlay}>
        <div className="uc-wrap" style={{maxWidth:1100}}>
          <InboxHead mobile={mobile} canNew={state === "emptyCan"} />
          <div className="uc-card">
            {state === "emptyCan"
              ? <div className="uc-empty"><div className="uc-empty-ic"><Ic n="chat-circle-text" /></div><h2>No conversations yet</h2><p>You can message the instructors and TAs on your courses. Conversations you start or receive will appear here.</p><button className="uc-btn p"><Ic n="pencil-simple-line" />New message</button></div>
              : <div className="uc-empty"><div className="uc-empty-ic"><Ic n="chat-circle-slash" /></div><h2>Messaging isn't available on your courses.</h2><p>Your courses don't include messaging. Updates about your courses still appear under the bell.</p></div>}
          </div>
        </div>
      </LPage>
    );
  }
  if (mobile && view === "thread") {
    return <LPage mobile count={count} flush overlay={overlay}><Thread mobile {...th} /></LPage>;
  }
  if (mobile) {
    return (
      <LPage mobile count={count} overlay={overlay}>
        <InboxHead mobile />
        <div className="uc-card" style={{margin:"0 -16px",borderRadius:0,borderLeft:0,borderRight:0}}>
          {convs.map((c) => <ConvItem key={c.id} c={c} />)}
        </div>
      </LPage>
    );
  }
  return (
    <LPage count={count} overlay={overlay}>
      <div style={{display:"flex",flexDirection:"column",height:"100%",maxWidth:1180,margin:"0 auto"}}>
        <InboxHead />
        <div className="uc-ibx"><ConvList convs={convs} selected={sel} /><Thread {...th} /></div>
      </div>
    </LPage>
  );
};

/* ---------- Picker ---------- */
const Picker = ({state = "list", mobile}) => {
  const q = state === "search" ? "gr" : "";
  const groups = state === "search" ? [{label:"Data Basics",people:["grace"]}] : UC_PICKER;
  const hl = (name) => { if (!q) return name; const i = name.toLowerCase().indexOf(q); return i < 0 ? name : <>{name.slice(0, i)}<mark>{name.slice(i, i + q.length)}</mark>{name.slice(i + q.length)}</>; };
  return (
    <div className={`uc-scrim ${mobile ? "full" : ""}`}>
      <div className="uc-dlg" role="dialog" aria-modal="true" aria-labelledby="pk-h" style={mobile ? null : {width:520,height:state === "empty" ? "auto" : 560}}>
        <div className="uc-dlg-hd">
          <div><h2 id="pk-h">New message</h2>{state !== "empty" && <p style={{fontSize:13,marginTop:2}}>Only people you're allowed to message are listed.</p>}</div>
          <button className="uc-ib" aria-label="Close"><Ic n="x" /></button>
        </div>
        {state === "empty" ? (
          <div className="uc-dlg-bd" style={{alignItems:"center",textAlign:"center",padding:"8px 28px 28px"}}>
            <div className="uc-empty-ic"><Ic n="users" /></div>
            <h3>There's no one you can message yet</h3>
            <p>Messaging is set up separately for each course. None of your courses include it at the moment, so there's no one to show here.</p>
            <p>Updates about your courses still appear under the bell.</p>
          </div>
        ) : (
          <div className="uc-dlg-bd" style={{flex:1}}>
            <label className={`uc-search ${state === "search" ? "is-focus" : ""}`}><Ic n="magnifying-glass" /><input placeholder="Search by name" defaultValue={q} aria-label="Search people you can message" /></label>
            <div role="listbox" aria-label="People you can message" style={{overflow:"hidden"}}>
              {groups.map((g) => (
                <div key={g.label} role="group" aria-label={g.label}>
                  <div className="uc-gl"><Ic n="book-open" />{g.label}</div>
                  {g.people.map((id, i) => (
                    <button key={id} className={`uc-pr ${state === "search" && i === 0 ? "is-hover" : ""}`} role="option" aria-selected="false">
                      <Av name={P(id).name} size={36} />
                      <span style={{flex:1,minWidth:0}}><span className="nm">{hl(P(id).name)}<Role r={P(id).role} /></span>{id === "ada" && <span className="sb">You already have a conversation</span>}</span>
                      <Ic n="caret-right" style={{color:"var(--muted)"}} />
                    </button>
                  ))}
                </div>
              ))}
            </div>
            {state === "search" && <p style={{fontSize:13}} role="status">1 person matches “gr”.</p>}
          </div>
        )}
        {state === "empty" && <div className="uc-dlg-ft"><button className="uc-btn s">Close</button></div>}
      </div>
    </div>
  );
};

/* ---------- Report + block ---------- */
const ReportDialog = ({step = "form", mobile}) => (
  <div className={`uc-scrim ${mobile ? "m" : ""}`}>
    <div className="uc-dlg" role="dialog" aria-modal="true" aria-labelledby="rp-h">
      {step === "form" ? <>
        <div className="uc-dlg-hd"><div><h2 id="rp-h">Report message</h2><p style={{fontSize:13,marginTop:2}}>Site admins will review it. Marcus Webb isn't told who reported it.</p></div><button className="uc-ib" aria-label="Close"><Ic n="x" /></button></div>
        <div className="uc-dlg-bd">
          <div className="uc-quote"><div className="by">Marcus Webb · 8 Sep, 21:18</div>Come on. Just send them or I'll tell the instructor you copied mine.</div>
          <fieldset style={{border:0,padding:0,margin:0,display:"flex",flexDirection:"column",gap:8}} role="radiogroup">
            <legend style={{fontWeight:600,marginBottom:8,padding:0}}>Why are you reporting this?</legend>
            {[["Spam","Advertising, scams or repeated unwanted messages"],["Harassment","Threats, bullying or pressure"],["Inappropriate","Offensive or explicit content"],["Other",null]].map(([t, d]) => (
              <button key={t} className={`uc-radio ${t === "Other" ? "on" : ""}`} role="radio" aria-checked={t === "Other" ? "true" : "false"}>
                <span className="uc-rd"></span><span><span className="t">{t}</span>{d && <span className="d" style={{display:"block"}}>{d}</span>}</span>
              </button>
            ))}
            <label className="uc-field" style={{marginTop:4}}>Tell us what happened<textarea className="uc-ta is-focus" rows={2} defaultValue="He keeps asking for my quiz answers."></textarea></label>
          </fieldset>
        </div>
        <div className="uc-dlg-ft"><button className="uc-btn s">Cancel</button><button className="uc-btn p">Submit report</button></div>
      </> : <>
        <div className="uc-dlg-hd"><span></span><button className="uc-ib" aria-label="Close"><Ic n="x" /></button></div>
        <div className="uc-dlg-bd" role="status" style={{paddingTop:0}}>
          <div className="uc-done-ic"><Ic n="check" /></div>
          <h2 id="rp-h">Report sent</h2>
          <p>Your report went to the site admins. They'll review the message and decide what to do.</p>
          <p>If you don't want to hear from Marcus Webb again, you can also block him.</p>
        </div>
        <div className="uc-dlg-ft"><button className="uc-btn s"><Ic n="prohibit" />Block Marcus Webb</button><button className="uc-btn p">Done</button></div>
      </>}
    </div>
  </div>
);

const BlockDialog = ({mobile}) => (
  <div className={`uc-scrim ${mobile ? "m" : ""}`}>
    <div className="uc-dlg" role="alertdialog" aria-modal="true" aria-labelledby="bk-h" style={mobile ? null : {width:460}}>
      <div className="uc-dlg-hd"><h2 id="bk-h">Block Marcus Webb?</h2><button className="uc-ib" aria-label="Close"><Ic n="x" /></button></div>
      <div className="uc-dlg-bd">
        <ul className="uc-bul">
          <li><Ic n="chat-circle-slash" />He can't send you messages.</li>
          <li><Ic n="eye-slash" />You won't see new messages from him.</li>
          <li><Ic n="clock-counter-clockwise" />Your earlier messages stay in the conversation.</li>
          <li><Ic n="arrow-counter-clockwise" />You can unblock him at any time from the conversation.</li>
        </ul>
      </div>
      <div className="uc-dlg-ft"><button className="uc-btn s">Cancel</button><button className="uc-btn d"><Ic n="prohibit" />Block Marcus Webb</button></div>
    </div>
  </div>
);

const MARCUS_TH = {otherId:"marcus",groups:UC_MARCUS_THREAD,course:"Introduction to Python · learner in your cohort"};

Object.assign(window, {ConvItem, ConvList, Composer, Thread, UC_CLOSED, LInbox, Picker, ReportDialog, BlockDialog, MARCUS_TH, InboxHead});
