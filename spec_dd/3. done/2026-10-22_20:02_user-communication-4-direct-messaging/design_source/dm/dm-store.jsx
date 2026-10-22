/* Simulated server for direct messaging: conversations, MessagingPolicy, idempotent send, notifications. */
const DM_PAGE = 12, DM_MAX = 2000;
const DM_USERS = {
  amara:{name:"Amara Okafor",role:"Learner"}, kat:{name:"Katherine Johnson",role:"Learner"}, marcus:{name:"Marcus Webb",role:"Learner"}, tomas:{name:"Tomás Rivera",role:"Learner"},
  ada:{name:"Ada Lovelace",role:"Instructor"}, alan:{name:"Alan Turing",role:"TA"}, grace:{name:"Grace Hopper",role:"TA"},
};
const dmIsEdu = (id) => DM_USERS[id].role !== "Learner";
const dmFirst = (id) => DM_USERS[id].name.split(" ")[0];
const DM_COURSES = [
  {id:"py",name:"Introduction to Python",group:"Introduction to Python · September 2026 cohort",educators:["ada","alan"],learners:["amara","kat","marcus","tomas"]},
  {id:"db",name:"Data Basics",group:"Data Basics",educators:["grace"],learners:["amara","tomas"]},
];
const dmMembers = (c) => [...c.educators, ...c.learners];
const dmShared = (a, b) => DM_COURSES.filter((c) => dmMembers(c).includes(a) && dmMembers(c).includes(b));

const dmDay0 = (t) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
const dmDaysAgo = (t) => Math.round((dmDay0(Date.now()) - dmDay0(t)) / 864e5);
const dmHM = (t) => new Date(t).toLocaleTimeString("en-GB", {hour:"2-digit", minute:"2-digit"});
const dmDayLabel = (t) => { const d = dmDaysAgo(t); return d === 0 ? "Today" : d === 1 ? "Yesterday" : new Date(t).toLocaleDateString("en-GB", {weekday:"long", day:"numeric", month:"long"}); };
const dmListTime = (t) => { const d = dmDaysAgo(t); return d === 0 ? dmHM(t) : d === 1 ? "Yesterday" : d < 7 ? new Date(t).toLocaleDateString("en-GB", {weekday:"short"}) : new Date(t).toLocaleDateString("en-GB", {day:"numeric", month:"short"}); };
const dmAgo = (t) => { const m = Math.floor((Date.now() - t) / 6e4); return m < 1 ? "Just now" : m < 60 ? `${m} min ago` : dmDaysAgo(t) === 0 ? dmHM(t) : dmListTime(t); };

const DMServer = (() => {
  let mid = 1, cid = 1, nid = 1;
  const cfg = {learnerStart:"none", revoked:new Set(), latency:700, failNext:null};
  const convs = [], notifs = [], keys = new Map(), log = [], subs = new Set();
  const L = (s, kind = "") => { log.unshift({t:Date.now(), s, kind}); log.length = Math.min(log.length, 40); subs.forEach((f) => f()); };
  const pk = (a, b) => [a, b].sort().join("|");
  const oth = (c, me) => (c.a === me ? c.b : c.a);
  const find = (a, b) => convs.find((c) => pk(c.a, c.b) === pk(a, b));
  const byId = (id) => convs.find((c) => c.id === id);
  const lastTs = (c) => (c.msgs.length ? c.msgs[c.msgs.length - 1].ts : 0);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const pub = (m, me) => ({id:m.id, from:m.from, ts:m.ts, body:m.body, key:m.from === me ? m.key : undefined});

  /* MessagingPolicy. c = existing conversation or null (starting). */
  function policy(me, o, c) {
    const nm = DM_USERS[o].name, shared = dmShared(me, o), course = (c && c.course) || (shared[0] && shared[0].name);
    if (!shared.length) return {ok:false, h:`${nm} is no longer on your courses`, b:"You can't reply, but you can still read earlier messages."};
    if (cfg.revoked.has(pk(me, o))) return {ok:false, h:"You can't reply to this conversation", b:`Messaging between you and ${nm} on ${course} has been turned off. You can still read earlier messages.`};
    const eMe = dmIsEdu(me), eO = dmIsEdu(o);
    if (eMe && !eO) return shared.some((s) => s.educators.includes(me)) ? {ok:true} : {ok:false, h:"You can't message this learner", b:"They aren't on a course you teach."};
    if (!eMe && eO) {
      if (c && c.msgs.length) return {ok:true};
      return cfg.learnerStart !== "none" ? {ok:true} : {ok:false, h:"Learners can't start conversations here", b:"Your instructors can message you, and you can reply."};
    }
    if (!eMe && !eO) return cfg.learnerStart === "peers" ? {ok:true} : {ok:false, h:"You can't reply to this conversation", b:`Messaging between learners is turned off on ${course}. You can still read earlier messages.`};
    return {ok:false, h:"You can't message this person", b:"Messaging between staff isn't part of this inbox."};
  }

  function notify(to, c, from) {
    const n = notifs.find((x) => x.user === to && x.cid === c.id && x.unread);
    if (n) { n.count++; n.ts = Date.now(); L(`notify ${to} · notification #${n.id} updated to ${n.count} messages · no new email`, "n"); }
    else { const id = nid++; notifs.push({id, user:to, cid:c.id, from, count:1, unread:true, ts:Date.now(), cat:"message"}); L(`notify ${to} · notification #${id} raised · 1 email queued (task gets site_id, user_id)`, "n"); }
  }

  /* seed */
  const T0 = dmDay0(Date.now());
  const at = (day, hm) => { const [h, m] = hm.split(":").map(Number); return T0 - day * 864e5 + h * 36e5 + m * 6e4; };
  const ago = (min) => Date.now() - min * 6e4;
  function seed(a, b, course, rows, unread = {}) {
    const c = {id:"c" + cid++, a, b, course, msgs:[], lastRead:{}};
    rows.forEach(([from, ts, body]) => c.msgs.push({id:mid++, from, ts, body}));
    [a, b].forEach((u) => {
      const n = unread[u] || 0, idx = c.msgs.length - 1 - n;
      c.lastRead[u] = idx >= 0 ? c.msgs[idx].ts : 0;
      if (n) notifs.push({id:nid++, user:u, cid:c.id, from:oth(c, u), count:n, unread:true, ts:lastTs(c), cat:"message"});
    });
    convs.push(c);
  }
  seed("ada", "amara", "Introduction to Python", [
    ["ada",at(34,"09:00"),"Welcome to Introduction to Python, Amara. Message me here if anything is unclear."],
    ["amara",at(34,"12:15"),"Thanks! Is the week 1 recording up yet?"],
    ["ada",at(34,"12:40"),"Yes, it's under Module 1 → Recordings."],
    ["amara",at(31,"19:44"),"Quick one: do we submit exercises in the player or by email?"],
    ["ada",at(31,"20:15"),"In the player. Each exercise has a Submit button at the bottom. Email isn't checked for submissions."],
    ["amara",at(31,"20:16"),"Got it, thanks."],
    ["amara",at(27,"10:02"),"I missed Tuesday's live session. Will the slides be shared?"],
    ["ada",at(27,"11:30"),"They're in the course resources now: https://firstclass.example/python/resources"],
    ["amara",at(27,"11:34"),"Found them, thank you."],
    ["ada",at(22,"08:50"),"Reminder: assignment 1 is due on Friday."],
    ["amara",at(22,"09:10"),"Is it fine to submit a day early?"],
    ["ada",at(22,"09:25"),"Of course. Early is always fine."],
    ["amara",at(20,"21:05"),"I submitted assignment 1. I wasn't sure about question 3, so I left a note in the comments."],
    ["ada",at(19,"14:20"),"Thanks, I'll read your note when I mark it."],
    ["ada",at(15,"16:00"),"Your assignment 1 mark is up. Nice work on question 3."],
    ["amara",at(15,"16:45"),"Thank you! That's a relief."],
    ["amara",at(12,"18:30"),"Which chapter covers dictionaries?"],
    ["ada",at(12,"19:02"),"Chapter 5. Start with 5.1, the rest builds on it."],
    ["amara",at(8,"16:05"),"Hi Ada, I'm stuck on exercise 4 in the loops module. My loop never stops. Can you take a look?"],
    ["ada",at(8,"17:20"),"Hi Amara. Check where you change the counter. If it's outside the loop, the condition never becomes false."],
    ["ada",at(8,"17:21"),"Paste the loop here if you're still stuck."],
    ["amara",ago(95),"That was it, thank you! It runs now."],
    ["ada",ago(22),"Nice work on the loops exercise."],
    ["ada",ago(21),"One thing to try next: rewrite it with a list comprehension. It's in section 4.3."],
  ], {amara:2});
  seed("grace", "amara", "Data Basics", [
    ["grace",at(2,"10:00"),"Hi Amara, welcome to Data Basics. Ask me anything about the exercises."],
    ["amara",at(1,"14:10"),"What's the difference between a left and an inner join?"],
    ["grace",at(1,"15:02"),"A left join keeps every row from the first table, even where there's no match.\nAn inner join keeps only the rows that match in both."],
  ], {amara:1});
  seed("kat", "amara", "Introduction to Python", [
    ["kat",at(5,"18:02"),"Hey! Want to go through the week 3 notes together?"],
    ["amara",at(5,"18:30"),"Sure. Are you doing the week 3 quiz tonight?"],
  ]);
  seed("alan", "amara", "Introduction to Python", [
    ["alan",at(28,"10:00"),"Hi Amara, your environment setup request is done. Try logging in again."],
    ["amara",at(28,"10:20"),"Thanks, that's sorted now."],
  ]);
  seed("ada", "tomas", "Introduction to Python", [
    ["ada",at(6,"09:00"),"Hi Tomás, I noticed you haven't submitted assignment 1 yet. Is everything OK?"],
    ["tomas",ago(48),"Could I get an extension on assignment 2? I've been ill this week."],
  ], {ada:1});
  seed("ada", "marcus", "Introduction to Python", [
    ["ada",at(3,"11:00"),"Hi Marcus, please keep your quiz answers to yourself. Sharing them breaks the course rules."],
    ["marcus",at(3,"11:40"),"Understood."],
  ]);
  const statics = {
    amara:[{id:"s1",cat:"registration",text:"You're registered for Introduction to Python",ts:at(3,"09:00")}],
    ada:[{id:"s2",cat:"registration",text:"Chen Wei registered for Introduction to Python",ts:at(2,"13:00")}],
    kat:[{id:"s3",cat:"completion",text:"You completed Spreadsheet Skills",ts:at(4,"17:00")}],
  };

  const summary = (c, me) => {
    const o = oth(c, me), last = c.msgs[c.msgs.length - 1], p = policy(me, o, c);
    return {id:c.id, other:o, course:c.course, last:pub(last, me), unread:c.msgs.filter((m) => m.from !== me && m.ts > (c.lastRead[me] || 0)).length, canReply:p.ok};
  };

  return {
    cfg, log, subscribe:(f) => { subs.add(f); return () => subs.delete(f); },
    setLearnerStart(v) { cfg.learnerStart = v; L(`config · learners may start: ${v}`, "c"); },
    setRevoked(a, b, on) { const k = pk(a, b); if (on === cfg.revoked.has(k)) return; on ? cfg.revoked.add(k) : cfg.revoked.delete(k); L(`config · ${a} ↔ ${b} ${on ? "no longer permitted" : "permitted"}`, "c"); },
    armFailure(kind) { cfg.failNext = kind; L(`armed · next send: ${kind === "network" ? "network error before save" : "saved, response lost"}`, "c"); },
    async list(me) { await wait(120); return convs.filter((c) => c.a === me || c.b === me).sort((x, y) => lastTs(y) - lastTs(x)).map((c) => summary(c, me)); },
    async info(me, id) { const c = byId(id), o = oth(c, me), p = policy(me, o, c); return {other:o, course:c.course, canReply:p.ok, reason:p.ok ? null : {h:p.h, b:p.b}}; },
    async page(me, id, beforeId, limit = DM_PAGE) {
      await wait(beforeId ? 450 : 160);
      const c = byId(id), older = beforeId ? c.msgs.filter((m) => m.id < beforeId) : c.msgs, slice = older.slice(-limit);
      L(`GET thread ${id}${beforeId ? ` before #${beforeId}` : ""} → ${slice.length} messages${older.length > limit ? ", more available" : ""}`);
      return {msgs:slice.map((m) => pub(m, me)), hasMore:older.length > limit};
    },
    async since(me, id, afterId) {
      await wait(120);
      const c = byId(id), o = oth(c, me), p = policy(me, o, c), msgs = c.msgs.filter((m) => m.id > afterId).map((m) => pub(m, me));
      if (msgs.length) L(`poll ${id} after #${afterId} → ${msgs.length} new`);
      return {msgs, canReply:p.ok, reason:p.ok ? null : {h:p.h, b:p.b}};
    },
    async send(me, {cid:id, to, body, key}) {
      await wait(cfg.latency);
      const k = key.slice(0, 6);
      if (cfg.failNext === "network") { cfg.failNext = null; L(`POST send ${k} → network error · nothing stored`, "e"); throw {kind:"network"}; }
      if (keys.has(key)) { const r = keys.get(key); L(`POST send ${k} → 200 · key already used, returned #${r.msg.id} · no duplicate`, "ok"); return {cid:r.cid, msg:pub(r.msg, me)}; }
      body = (body || "").trim();
      if (!body || body.length > DM_MAX) { L(`POST send ${k} → 400 · body empty or over ${DM_MAX}`, "e"); throw {kind:"invalid"}; }
      let c = id ? byId(id) : find(me, to);
      const p = policy(me, to, c);
      if (!p.ok) { L(`POST send ${k} → 403 · refused by MessagingPolicy`, "e"); throw {kind:"policy", reason:{h:p.h, b:p.b}}; }
      if (!c) { c = {id:"c" + cid++, a:me, b:to, course:dmShared(me, to)[0].name, msgs:[], lastRead:{[me]:0, [to]:0}}; convs.push(c); L(`conversation ${c.id} created · ${me} ↔ ${to}`); }
      const msg = {id:mid++, from:me, ts:Date.now(), body, key};
      c.msgs.push(msg); c.lastRead[me] = msg.ts; keys.set(key, {cid:c.id, msg});
      L(`POST send ${k} → 201 · #${msg.id} stored in ${c.id}`, "ok");
      notify(to, c, me);
      if (cfg.failNext === "lost") { cfg.failNext = null; L(`response for ${k} lost in transit · client sees an error`, "e"); throw {kind:"network"}; }
      return {cid:c.id, msg:pub(msg, me)};
    },
    async markRead(me, id) {
      const c = byId(id); if (!c) return;
      const before = c.lastRead[me] || 0; c.lastRead[me] = lastTs(c);
      const n = notifs.find((x) => x.user === me && x.cid === id && x.unread);
      if (n) n.unread = false;
      if (lastTs(c) > before && c.msgs.some((m) => m.from !== me && m.ts > before)) L(`read ${id} by ${me}${n ? ` · notification #${n.id} marked read` : ""} · no receipt sent`);
    },
    async notifs(me) {
      await wait(100);
      const ms = notifs.filter((n) => n.user === me).map((n) => ({...n, text:n.count > 1 ? `${DM_USERS[n.from].name} sent you ${n.count} new messages` : `${DM_USERS[n.from].name} sent you a message`}));
      return [...ms, ...(statics[me] || []).map((s) => ({...s, unread:false}))].sort((a, b) => b.ts - a.ts);
    },
    async readAllNotifs(me) { notifs.forEach((n) => { if (n.user === me) n.unread = false; }); L(`notifications · all marked read for ${me}`); },
    async recipients(me) {
      const seen = new Set(), groups = [];
      DM_COURSES.forEach((c) => {
        if (!dmMembers(c).includes(me)) return;
        const people = dmMembers(c).filter((p) => p !== me && !seen.has(p) && policy(me, p, null).ok);
        people.forEach((p) => seen.add(p));
        if (people.length) groups.push({label:c.group, people:people.map((p) => ({id:p, hasConv:!!find(me, p)}))});
      });
      return groups;
    },
    findConv(a, b) { const c = find(a, b); return c ? c.id : null; },
    partners(me) { return convs.filter((c) => c.a === me || c.b === me).map((c) => oth(c, me)); },
    inject(from, to, body) {
      const c = find(from, to), p = policy(from, to, c);
      if (!p.ok) { L(`${from} → ${to} refused by MessagingPolicy · not delivered`, "e"); return false; }
      const msg = {id:mid++, from, ts:Date.now(), body, key:"srv" + mid};
      let cc = c;
      if (!cc) { cc = {id:"c" + cid++, a:from, b:to, course:dmShared(from, to)[0].name, msgs:[], lastRead:{[from]:0, [to]:0}}; convs.push(cc); }
      cc.msgs.push(msg); cc.lastRead[from] = msg.ts;
      L(`${from} sent #${msg.id} to ${to} in ${cc.id}`, "ok");
      notify(to, cc, from);
      return true;
    },
  };
})();

const DM_REPLIES = {
  ada:["Good question. Have a look at section 4.3 first, then tell me where you get stuck.","Yes, that's right.","I'll cover that in Thursday's session too."],
  grace:["Exactly. Try it on the sample dataset and compare the row counts.","Happy to help. Shout if the exercise still doesn't add up."],
  alan:["Thanks, I'll look into it today."],
  amara:["Thanks, Ada! I'll try that tonight.","Okay, that makes sense now."],
  tomas:["Thank you, that really helps.","I'll get it in by Monday."],
  marcus:["Okay."], kat:["Sounds good, see you then!","Ha, same here."],
};

Object.assign(window, {DM_PAGE, DM_MAX, DM_USERS, DM_COURSES, DMServer, DM_REPLIES, dmIsEdu, dmMembers, dmFirst, dmDay0, dmHM, dmDayLabel, dmListTime, dmAgo});
