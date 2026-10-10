/* Direct messaging UI: header, bell panel, conversation list, thread, composer, recipient picker. */
const U = (id) => DM_USERS[id];
const dmLinkify = (s) => s.split(/(https?:\/\/[^\s]+)/g).map((p, i) => (i % 2 ? <a key={i} href={p} target="_blank" rel="noopener noreferrer">{p}</a> : p));

function DMHeader({me, mobile, route, unreadConvs, bellCount, bellOpen, bellRef, onBell, onInbox, onHome}) {
  return (
    <header className={`uc-hd ${mobile ? "m" : ""}`}>
      <a className="uc-brand" href="#" onClick={(e) => { e.preventDefault(); onHome(); }}><img src="design-system/assets/logo-color.png" alt="" /><span>First Class</span></a>
      <div className="uc-hd-r">
        <a href="#" className="dm-hdlink" aria-current={route === "inbox" ? "page" : undefined} onClick={(e) => { e.preventDefault(); onInbox(); }}>
          <Ic n="chat-circle-text" fill={route === "inbox"} />
          {mobile ? <span className="sr">Messages</span> : "Messages"}
          {unreadConvs > 0 && <span className="uc-cnt" aria-hidden="true">{unreadConvs}</span>}
          {unreadConvs > 0 && <span className="sr">, {unreadConvs} unread {unreadConvs === 1 ? "conversation" : "conversations"}</span>}
        </a>
        <button ref={bellRef} className="uc-bell" onClick={onBell} aria-label={bellCount ? `Notifications, ${bellCount} unread` : "Notifications, none unread"} aria-expanded={bellOpen ? "true" : "false"} aria-haspopup="dialog">
          <Ic n="bell" fill={bellOpen} />
          {bellCount > 0 && <span className="uc-badge" aria-hidden="true">{ucBadge(bellCount)}</span>}
        </button>
        <span className="uc-avbtn" title={U(me).name}><Av name={U(me).name} size={mobile ? 32 : 36} tone="p" /></span>
      </div>
    </header>
  );
}

function DMNotifPanel({items, mobile, onOpen, onReadAll, onClose, panelRef}) {
  const unread = items.filter((n) => n.unread).length;
  React.useEffect(() => { const k = (e) => e.key === "Escape" && onClose(true); document.addEventListener("keydown", k); return () => document.removeEventListener("keydown", k); }, []);
  const body = (
    <>
      <div className="uc-pop-hd">
        <h2 id="np-h">Notifications{unread > 0 && <span className="uc-muted" style={{fontWeight:500,fontSize:13,fontFamily:"var(--font-body)",marginLeft:8}}>{unread} unread</span>}</h2>
        <button className="uc-ib" aria-label="Close notifications" onClick={() => onClose(true)}><Ic n="x" /></button>
      </div>
      <div className="uc-list dm-scroll">
        {items.length === 0 && <div className="uc-empty" style={{padding:"32px 20px"}}><p>Nothing here yet.</p></div>}
        {items.slice(0, 8).map((n) => (
          <a key={n.id} className={`uc-ni ${n.unread ? "unread" : ""}`} href="#" onClick={(e) => { e.preventDefault(); if (n.cid) onOpen(n.cid); }}>
            <span className={`uc-ni-ic c-${n.cat}`}><Ic n={UC_CAT[n.cat].icon} /></span>
            <span style={{minWidth:0}}>
              <span className="uc-ni-tx">{n.unread && <span className="sr">Unread. </span>}{n.text}</span>
              <span className="uc-ni-meta"><span>{n.cat === "message" ? "Direct message" : UC_CAT[n.cat].label}</span><span aria-hidden="true">·</span><span>{dmAgo(n.ts)}</span></span>
            </span>
            <span className="uc-ni-r">{n.unread && <NewMark />}</span>
          </a>
        ))}
      </div>
      <div className="uc-pop-ft"><button className="uc-btn g sm" onClick={onReadAll} disabled={!unread}><Ic n="checks" />Mark all as read</button></div>
    </>
  );
  return <div ref={panelRef} className={mobile ? "uc-sheet" : "uc-pop"} role="dialog" aria-labelledby="np-h">{body}</div>;
}

function DMConvList({me, list, sel, onOpen, flat}) {
  return (
    <ul className={`uc-cl-list dm-scroll ${flat ? "dm-flat" : ""}`} aria-label="Conversations">
      {list.map((c) => {
        const p = U(c.other), mine = c.last.from === me;
        return (
          <li key={c.id}>
            <button className={`uc-ci ${c.unread ? "unread" : ""}`} aria-current={c.id === sel ? "true" : undefined} onClick={() => onOpen(c.id)}>
              <Av name={p.name} size={40} />
              <span style={{minWidth:0}}>
                <span className="uc-ci-n"><strong>{p.name}</strong><Role r={p.role} /></span>
                <span className="uc-ci-sub" style={{display:"block"}}>{c.course}</span>
                <span className="uc-ci-p" style={{display:"block"}}>{c.unread ? <span className="sr">Unread. </span> : null}{mine ? "You: " : ""}{c.last.body.split("\n")[0]}</span>
              </span>
              <span className="uc-ci-r">
                <time dateTime={new Date(c.last.ts).toISOString()}>{dmListTime(c.last.ts)}</time>
                {c.unread ? <NewMark label={c.unread > 1 ? `${c.unread} new` : "New"} /> : null}
                {!c.canReply && <span className="uc-tag"><Ic n="lock-simple" />Read only</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function DMComposer({other, value, onChange, onSend, mobile, autoFocus}) {
  const ta = React.useRef(), id = React.useId();
  React.useLayoutEffect(() => { const el = ta.current; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight + 2, 160) + "px"; }, [value]);
  React.useEffect(() => { if (autoFocus) ta.current.focus(); }, [autoFocus, other]);
  const n = value.length, over = n > DM_MAX, empty = !value.trim();
  const submit = (e) => { e && e.preventDefault(); if (!empty && !over) onSend(value); ta.current.focus(); };
  return (
    <form className={`uc-cmp ${mobile ? "m" : ""}`} onSubmit={submit}>
      <div className="uc-who" id={`${id}-who`}><Ic n="eye" /><span>Only <strong>{U(other).name}</strong> ({U(other).role}) and you can read this conversation.</span></div>
      <div className="uc-cmp-row">
        <textarea ref={ta} className="uc-ta" rows={1} value={value} placeholder={`Write a message to ${dmFirst(other)}`} aria-label={`Message to ${U(other).name}`} aria-describedby={`${id}-who ${id}-hint ${over ? id + "-ct" : ""}`} aria-invalid={over ? "true" : undefined}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !mobile && !e.nativeEvent.isComposing) submit(e); }}></textarea>
        <button type="submit" className="uc-btn p" disabled={empty || over}><Ic n="paper-plane-right" fill />{mobile ? <span className="sr">Send</span> : "Send"}</button>
      </div>
      <span className="sr" id={`${id}-hint`}>{mobile ? "" : "Enter sends. Shift and Enter adds a new line."}</span>
      {n > DM_MAX - 200 && <div id={`${id}-ct`} className={`dm-count ${over ? "over" : ""}`} aria-live="polite">{over ? `${(n - DM_MAX).toLocaleString()} characters over the 2,000 limit` : `${(DM_MAX - n).toLocaleString()} characters left`}</div>}
    </form>
  );
}

function dmGroups(me, msgs, pending) {
  const all = [...msgs.map((m) => ({...m, status:"sent"})), ...pending.map((p) => ({...p, from:me, id:"p-" + p.key}))];
  const out = []; let day = null, g = null;
  all.forEach((m) => {
    const d = dmDay0(m.ts);
    if (d !== day) { out.push({sep:dmDayLabel(m.ts), key:"d" + d}); day = d; g = null; }
    if (g && g.from === m.from && m.ts - g.lastTs < 5 * 6e4 && m.status === "sent" && g.status === "sent") { g.items.push(m); g.lastTs = m.ts; }
    else { g = {from:m.from, ts:m.ts, lastTs:m.ts, items:[m], status:m.status, key:"g" + m.id}; out.push(g); }
  });
  return out;
}

function DMThread({me, th, mobile, draft, setDraft, onSend, onRetry, onDiscard, onOlder, onBack}) {
  const o = U(th.other), body = React.useRef(), atBottom = React.useRef(true), snap = React.useRef(null), prev = React.useRef({first:null, last:null, cid:undefined});
  const [pill, setPill] = React.useState(0);
  const all = [...th.msgs, ...th.pending.map((p) => ({id:"p-" + p.key, from:me}))];
  const firstId = th.msgs.length ? th.msgs[0].id : null, last = all[all.length - 1], lastId = last ? last.id : null;
  React.useLayoutEffect(() => {
    const el = body.current, p = prev.current;
    if (p.cid !== (th.cid || th.other)) { el.scrollTop = el.scrollHeight; setPill(0); atBottom.current = true; }
    else if (snap.current && firstId !== p.first) { el.scrollTop = snap.current.top + (el.scrollHeight - snap.current.h); snap.current = null; }
    else if (lastId !== p.last) {
      const newOnes = p.last == null ? 0 : all.filter((m) => typeof m.id === "number" && m.id > p.last && m.from !== me).length;
      if (atBottom.current || (last && last.from === me && newOnes === 0)) { el.scrollTop = el.scrollHeight; setPill(0); }
      else if (newOnes) setPill((n) => n + newOnes);
    }
    prev.current = {first:firstId, last:lastId, cid:th.cid || th.other};
  });
  const onScroll = () => { const el = body.current; atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48; if (atBottom.current && pill) setPill(0); };
  const older = () => { const el = body.current; snap.current = {h:el.scrollHeight, top:el.scrollTop}; onOlder(); };
  const toBottom = () => { const el = body.current; el.scrollTop = el.scrollHeight; setPill(0); };
  const groups = dmGroups(me, th.msgs, th.pending);
  const isNew = !th.cid && !th.msgs.length;
  return (
    <section className={`uc-th dm-th ${mobile ? "m" : ""}`} aria-labelledby="th-h">
      <div className="uc-th-hd">
        {mobile && <button className="uc-ib" aria-label="Back to messages" onClick={onBack}><Ic n="arrow-left" /></button>}
        <Av name={o.name} size={mobile ? 32 : 40} />
        <div className="who"><h2 className="nm" id="th-h" style={mobile ? {fontSize:15} : null}><span className="sr">Conversation with </span>{o.name}<Role r={o.role} /></h2><div className="ctx">{th.course}</div></div>
      </div>
      <div className="dm-bodywrap">
        <div className="uc-th-body dm-scroll" ref={body} onScroll={onScroll} role="log" aria-label={`Messages with ${o.name}`} aria-busy={th.loading ? "true" : undefined}>
          <div className="dm-top">
            {th.hasMore && <button className="uc-btn s sm dm-older" onClick={older} disabled={th.loadingOlder}>{th.loadingOlder ? <><Ic n="circle-notch" className="dm-spin" />Loading earlier messages</> : <><Ic n="arrow-up" />Load earlier messages</>}</button>}
            {!th.hasMore && th.msgs.length > 0 && <div className="dm-begin">Start of your conversation with {o.name}</div>}
          </div>
          {th.loading && <div className="dm-loading"><Ic n="circle-notch" className="dm-spin" />Loading conversation</div>}
          {isNew && !th.loading && <div className="uc-start"><Av name={o.name} size={56} /><h2>{o.name} <Role r={o.role} /></h2><p>{th.course}</p><p>This is the start of your conversation.</p></div>}
          {groups.map((g) => g.sep ? <div className="uc-sep" key={g.key}>{g.sep}</div> : (
            <div className={`uc-mg ${g.from === me ? "me" : ""}`} key={g.key}>
              {g.from !== me && <Av name={U(g.from).name} size={32} />}
              <div className="uc-mg-c">
                <div className="uc-mg-hd"><strong>{g.from === me ? "You" : U(g.from).name}</strong>{g.from !== me && <Role r={U(g.from).role} />}<time dateTime={new Date(g.ts).toISOString()}>{dmHM(g.ts)}</time></div>
                {g.items.map((m) => (
                  <div className="uc-mrow" key={m.id}>
                    <div className={`uc-bub ${m.status === "sending" ? "dm-sending" : ""} ${m.status === "failed" || m.status === "refused" ? "failed" : ""}`}>{dmLinkify(m.body)}</div>
                  </div>
                ))}
                {g.status === "sending" && <div className="dm-st" aria-hidden="true"><Ic n="circle-notch" className="dm-spin" />Sending…</div>}
                {g.status === "failed" && <div className="uc-fail" role="alert"><Ic n="warning-circle" fill />Not sent. Check your connection.<button onClick={() => onRetry(g.items[0].key)}>Retry</button><button onClick={() => onDiscard(g.items[0].key)}>Discard</button></div>}
                {g.status === "refused" && <div className="uc-fail" role="alert"><Ic n="warning-circle" fill />Not sent. {dmFirst(th.other)} can't receive messages from you here.<button onClick={() => onDiscard(g.items[0].key)}>Discard</button></div>}
              </div>
            </div>
          ))}
        </div>
        {pill > 0 && <button className="dm-pill" onClick={toBottom}><Ic n="arrow-down" />{pill === 1 ? "1 new message" : `${pill} new messages`}</button>}
      </div>
      {th.canReply === false
        ? <div className={`uc-cmp ${mobile ? "m" : ""}`}><div className="uc-note" role="status"><Ic n="lock-simple" /><div><div className="h">{th.reason.h}</div><div className="b">{th.reason.b}</div></div></div></div>
        : th.loading ? null : <DMComposer other={th.other} value={draft} onChange={setDraft} onSend={onSend} mobile={mobile} autoFocus={isNew} />}
    </section>
  );
}

function DMPicker({groups, mobile, onPick, onClose}) {
  const [q, setQ] = React.useState(""), inp = React.useRef();
  React.useEffect(() => { inp.current && inp.current.focus(); const k = (e) => e.key === "Escape" && onClose(); document.addEventListener("keydown", k); return () => document.removeEventListener("keydown", k); }, []);
  const ql = q.trim().toLowerCase();
  const fg = groups.map((g) => ({...g, people:g.people.filter((p) => !ql || U(p.id).name.toLowerCase().includes(ql))})).filter((g) => g.people.length);
  const count = fg.reduce((s, g) => s + g.people.length, 0);
  const hl = (name) => { if (!ql) return name; const i = name.toLowerCase().indexOf(ql); return i < 0 ? name : <>{name.slice(0, i)}<mark>{name.slice(i, i + ql.length)}</mark>{name.slice(i + ql.length)}</>; };
  return (
    <div className={`uc-scrim ${mobile ? "full" : ""}`} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="uc-dlg" role="dialog" aria-modal="true" aria-labelledby="pk-h" style={mobile ? null : {width:520,height:groups.length ? 560 : "auto"}}>
        <div className="uc-dlg-hd">
          <div><h2 id="pk-h">New message</h2>{groups.length > 0 && <p style={{fontSize:13,marginTop:2}}>Only people you're allowed to message are listed.</p>}</div>
          <button className="uc-ib" aria-label="Close" onClick={onClose}><Ic n="x" /></button>
        </div>
        {groups.length === 0 ? (
          <div className="uc-dlg-bd" style={{alignItems:"center",textAlign:"center",padding:"8px 28px 28px"}}>
            <div className="uc-empty-ic"><Ic n="users" /></div>
            <h3>There's no one you can message yet</h3>
            <p>Your instructors can message you here, and you can reply to them.</p>
          </div>
        ) : (
          <div className="uc-dlg-bd" style={{flex:1}}>
            <label className="uc-search"><Ic n="magnifying-glass" /><input ref={inp} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name" aria-label="Search people you can message" /></label>
            <div className="dm-pk-list dm-scroll">
              {fg.map((g) => (
                <div key={g.label} role="group" aria-label={g.label}>
                  <div className="uc-gl"><Ic n="book-open" />{g.label}</div>
                  {g.people.map((p) => (
                    <button key={p.id} className="uc-pr" onClick={() => onPick(p.id)}>
                      <Av name={U(p.id).name} size={36} />
                      <span style={{flex:1,minWidth:0}}><span className="nm">{hl(U(p.id).name)}<Role r={U(p.id).role} /></span>{p.hasConv && <span className="sb" style={{display:"block"}}>You already have a conversation</span>}</span>
                      <Ic n="caret-right" style={{color:"var(--muted)"}} />
                    </button>
                  ))}
                </div>
              ))}
              {count === 0 && <p style={{padding:"16px 4px"}}>No one you can message matches “{q}”.</p>}
            </div>
            <p className="sr" role="status">{ql ? `${count} ${count === 1 ? "person matches" : "people match"}` : ""}</p>
          </div>
        )}
        {groups.length === 0 && <div className="uc-dlg-ft"><button className="uc-btn s" onClick={onClose}>Close</button></div>}
      </div>
    </div>
  );
}

Object.assign(window, {DMHeader, DMNotifPanel, DMConvList, DMComposer, DMThread, DMPicker});
