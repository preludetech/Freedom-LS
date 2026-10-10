/* Direct messaging app: routing, polling, send/retry, and the prototype controls. */
const dmKey = () => "k" + Math.random().toString(36).slice(2, 10);
const dmMerge = (a, b) => { const m = new Map(a.map((x) => [x.id, x])); b.forEach((x) => m.set(x.id, x)); return [...m.values()].sort((x, y) => x.id - y.id); };

function DMApp({t}) {
  const me = t.viewer, S = DMServer;
  const [route, setRoute] = React.useState("inbox");
  const [list, setList] = React.useState(null);
  const [notifs, setNotifs] = React.useState([]);
  const [canStart, setCanStart] = React.useState([]);
  const [th, setTh] = React.useState(null);
  const [drafts, setDrafts] = React.useState({});
  const [picker, setPicker] = React.useState(false);
  const [bell, setBell] = React.useState(false);
  const [say, setSay] = React.useState("");
  const [mobile, setMobile] = React.useState(false);
  const thRef = React.useRef(th); thRef.current = th;
  const tRef = React.useRef(t); tRef.current = t;
  const root = React.useRef(), bellRef = React.useRef(), panelRef = React.useRef(), prevUnread = React.useRef(null);
  const announce = (s) => { setSay(""); setTimeout(() => setSay(s), 60); };

  React.useLayoutEffect(() => { const ro = new ResizeObserver(([e]) => setMobile(e.contentRect.width < 760)); ro.observe(root.current); return () => ro.disconnect(); }, []);

  const refresh = async () => {
    const [l, n, r] = await Promise.all([S.list(me), S.notifs(me), S.recipients(me)]);
    setList(l); setNotifs(n); setCanStart(r);
    const u = l.filter((c) => c.unread).length;
    if (prevUnread.current != null && u > prevUnread.current) {
      const c = l.find((x) => x.unread && x.id !== (thRef.current && thRef.current.cid));
      if (c) announce(`New message from ${DM_USERS[c.other].name}. ${u} unread ${u === 1 ? "conversation" : "conversations"}.`);
    }
    prevUnread.current = u;
  };

  React.useEffect(() => { setTh(null); setRoute("inbox"); setList(null); setBell(false); setPicker(false); prevUnread.current = null; refresh(); }, [me]);

  const openConv = async (cid) => {
    setRoute("inbox"); setBell(false); setPicker(false);
    if (thRef.current && thRef.current.cid === cid) return;
    setTh({cid, other:null, msgs:[], pending:[], loading:true, synced:0});
    const [info, p] = await Promise.all([S.info(me, cid), S.page(me, cid, null)]);
    if (!thRef.current || thRef.current.cid !== cid) return;
    setTh({cid, ...info, msgs:p.msgs, hasMore:p.hasMore, pending:[], synced:p.msgs.length ? p.msgs[p.msgs.length - 1].id : 0});
    await S.markRead(me, cid); refresh();
  };
  const pick = (to) => {
    const cid = S.findConv(me, to);
    if (cid) return openConv(cid);
    setPicker(false); setRoute("inbox");
    setTh({cid:null, other:to, course:DM_COURSES.find((c) => dmMembers(c).includes(me) && dmMembers(c).includes(to)).name, canReply:true, msgs:[], pending:[], synced:0});
  };
  const older = async () => {
    const cur = thRef.current; if (!cur || !cur.msgs.length) return;
    setTh((x) => ({...x, loadingOlder:true}));
    const p = await S.page(me, cur.cid, cur.msgs[0].id);
    setTh((x) => (x && x.cid === cur.cid ? {...x, msgs:dmMerge(p.msgs, x.msgs), hasMore:p.hasMore, loadingOlder:false} : x));
  };

  const poll = async () => {
    await refresh();
    const cur = thRef.current; if (!cur || !cur.cid || cur.loading) return;
    const r = await S.since(me, cur.cid, cur.synced);
    if (!thRef.current || thRef.current.cid !== cur.cid) return;
    setTh((x) => {
      const keys = new Set(r.msgs.map((m) => m.key).filter(Boolean));
      return {...x, msgs:dmMerge(x.msgs, r.msgs), pending:x.pending.filter((p) => !keys.has(p.key)), synced:r.msgs.length ? r.msgs[r.msgs.length - 1].id : x.synced, canReply:r.canReply, reason:r.reason};
    });
    const inc = r.msgs.filter((m) => m.from !== me);
    if (inc.length) { announce(`${DM_USERS[inc[0].from].name}: ${inc[inc.length - 1].body}`); await S.markRead(me, cur.cid); refresh(); }
  };
  React.useEffect(() => { const i = setInterval(poll, t.poll * 1000); return () => clearInterval(i); }, [me, t.poll]);

  const dkey = th ? th.cid || "to:" + th.other : null;
  const deliver = async (key, body) => {
    const cur = thRef.current, same = (x) => x && (x.cid === cur.cid || (!cur.cid && x.other === cur.other));
    try {
      const r = await S.send(me, {cid:cur.cid, to:cur.other, body, key});
      setTh((x) => same(x) || (x && x.cid === r.cid) ? {...x, cid:r.cid, msgs:dmMerge(x.msgs, [r.msg]), pending:x.pending.filter((p) => p.key !== key)} : x);
      if (!cur.cid) setDrafts((d) => { const n = {...d}; delete n["to:" + cur.other]; return n; });
      refresh();
      if (tRef.current.autoReply) {
        const pool = DM_REPLIES[cur.other] || ["Thanks."], other = cur.other, viewer = me;
        setTimeout(() => S.inject(other, viewer, pool[Math.floor(Math.random() * pool.length)]), 4000 + Math.random() * 2500);
      }
    } catch (e) {
      setTh((x) => same(x) ? {...x, pending:x.pending.map((p) => (p.key === key ? {...p, status:e.kind === "policy" ? "refused" : "failed"} : p)), ...(e.kind === "policy" ? {canReply:false, reason:e.reason} : {})} : x);
      announce(e.kind === "policy" ? "Message not sent. You can no longer message this person here." : "Message not sent. Check your connection and retry.");
    }
  };
  const send = (text) => {
    const key = dmKey(), body = text.trim();
    setDrafts((d) => ({...d, [dkey]:""}));
    setTh((x) => ({...x, pending:[...x.pending, {key, body, ts:Date.now(), status:"sending"}]}));
    deliver(key, body);
  };
  const retry = (key) => { const p = th.pending.find((x) => x.key === key); setTh((x) => ({...x, pending:x.pending.map((q) => (q.key === key ? {...q, status:"sending"} : q))})); deliver(key, p.body); };
  const discard = (key) => setTh((x) => ({...x, pending:x.pending.filter((q) => q.key !== key)}));

  React.useEffect(() => {
    if (!bell) return;
    const h = (e) => { if (panelRef.current && !panelRef.current.contains(e.target) && !bellRef.current.contains(e.target)) setBell(false); };
    document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h);
  }, [bell]);
  React.useEffect(() => { if (bell) refresh(); }, [bell]);

  const unreadConvs = list ? list.filter((c) => c.unread).length : 0, bellCount = notifs.filter((n) => n.unread).length;
  const thread = th && th.other ? <DMThread me={me} th={th} mobile={mobile} draft={drafts[dkey] || ""} setDraft={(v) => setDrafts((d) => ({...d, [dkey]:v}))} onSend={send} onRetry={retry} onDiscard={discard} onOlder={older} onBack={() => { setTh(null); refresh(); }} />
    : th ? <section className="uc-th"><div className="dm-loading" style={{margin:"auto"}}><Ic n="circle-notch" className="dm-spin" />Loading conversation</div></section> : null;
  const head = (
    <div className="uc-ph" style={{marginBottom:16}}>
      <h1 style={mobile ? {fontSize:24} : null}>Messages</h1>
      {canStart.length > 0 && <button className="uc-btn p" onClick={() => setPicker(true)}><Ic n="pencil-simple-line" />New message</button>}
    </div>
  );
  const empty = list && list.length === 0 && (
    <div className="uc-card"><div className="uc-empty">
      <div className="uc-empty-ic"><Ic n="chat-circle-text" /></div>
      <h2>No conversations yet</h2>
      {canStart.length ? <><p>Conversations you start or receive appear here.</p><button className="uc-btn p" onClick={() => setPicker(true)}><Ic n="pencil-simple-line" />New message</button></> : <p>Your instructors can message you here, and you can reply to them.</p>}
    </div></div>
  );

  let main;
  if (route === "home") main = <main className={`uc-main ${mobile ? "m" : ""}`}><DashStub mobile={mobile} /></main>;
  else if (mobile && th) main = <main className="uc-main flush">{thread}</main>;
  else if (mobile) main = <main className="uc-main m dm-mlist">{head}{empty || (list && <div className="uc-card dm-mcard"><DMConvList me={me} list={list} onOpen={openConv} flat /></div>)}</main>;
  else main = (
    <main className="uc-main"><div className="dm-inbox">{head}
      {empty || <div className="uc-ibx">
        <div className="uc-cl">{list ? <DMConvList me={me} list={list} sel={th && th.cid} onOpen={openConv} /> : <div className="dm-loading"><Ic n="circle-notch" className="dm-spin" />Loading</div>}</div>
        {thread || <section className="uc-th"><div className="uc-empty" style={{margin:"auto"}}><div className="uc-empty-ic"><Ic n="chat-circle-text" /></div><p>Choose a conversation to read it.</p></div></section>}
      </div>}
    </div></main>
  );

  return (
    <div className="uc dm" ref={root}>
      <DMHeader me={me} mobile={mobile} route={route} unreadConvs={unreadConvs} bellCount={bellCount} bellOpen={bell} bellRef={bellRef}
        onBell={() => setBell((b) => !b)} onInbox={() => { setRoute("inbox"); if (mobile) setTh(null); setBell(false); }} onHome={() => { setRoute("home"); setBell(false); }} />
      {main}
      {bell && <DMNotifPanel items={notifs} mobile={mobile} panelRef={panelRef} onOpen={openConv} onReadAll={async () => { await S.readAllNotifs(me); refresh(); }} onClose={(f) => { setBell(false); f && bellRef.current && bellRef.current.focus(); }} />}
      {picker && <DMPicker groups={canStart} mobile={mobile} onPick={pick} onClose={() => setPicker(false)} />}
      <div className="sr" aria-live="polite" role="status">{say}</div>
    </div>
  );
}

function DMLog() {
  const [, f] = React.useReducer((x) => x + 1, 0);
  React.useEffect(() => DMServer.subscribe(f), []);
  return <div className="dm-log">{DMServer.log.length === 0 ? <span>No server activity yet.</span> : DMServer.log.slice(0, 14).map((l, i) => <div key={l.t + "-" + i} className={l.kind}><span>{new Date(l.t).toLocaleTimeString("en-GB")}</span> {l.s}</div>)}</div>;
}

Object.assign(window, {DMApp, DMLog});
