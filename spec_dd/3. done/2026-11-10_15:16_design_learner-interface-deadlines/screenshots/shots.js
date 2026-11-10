async (page) => {
  const OUT = '/home/sheena/workspace/lms/freedom-ls-worktrees/design_learner-interface-deadlines/spec_dd/2. in progress/design_learner-interface-deadlines/screenshots/final/';
  const BASE = 'http://127.0.0.1:8078';
  const browser = page.context().browser();
  const learners = {fresh: 'qa_deadline_fresh@email.com', late: 'qa_deadline_solo@email.com', restored: 'qa_deadline_restored@email.com', cohort: 'qa_deadline_cohort@email.com'};
  const sizes = {m: [375, 812], t: [1024, 768], d: [1920, 1080]};
  const done = [];
  const go = async (p, u) => { for (let i = 0; i < 4; i++) { try { await p.goto(u, {waitUntil: 'commit'}); break; } catch (e) { await p.waitForTimeout(1500); } } await p.waitForTimeout(1500); };
  const hide = async (p) => { await p.addStyleTag({content: '#djDebug{display:none!important}'}).catch(()=>{}); };
  for (const [who, email] of Object.entries(learners)) {
    const ctx = await browser.newContext({timezoneId: 'Africa/Johannesburg', viewport: {width: 1920, height: 1080}});
    const p = await ctx.newPage();
    await p.goto(BASE + '/accounts/login/');
    await p.fill('input[name=login]', email);
    await p.fill('input[name=password]', email);
    await p.press('input[name=password]', 'Enter');
    await p.waitForURL(u => !u.toString().includes('/login'), {timeout: 20000}).catch(() => {});
    await p.waitForTimeout(1500);
    if (p.url().includes('/login')) { done.push(`${who}: LOGIN FAILED`); await ctx.close(); continue; }
    for (const [sk, [w, h]] of Object.entries(sizes)) {
      await p.setViewportSize({width: w, height: h});
      await go(p, BASE + '/'); await hide(p);
      await p.screenshot({path: `${OUT}${who}-dashboard-${sk}.png`, fullPage: true}); done.push(`${who}-dashboard-${sk}`);
      if (who === 'cohort') continue;
      await go(p, BASE + '/courses/functionality-demo-course-parts/'); await hide(p);
      // follow to first item (Welcome)
      await go(p, BASE + '/courses/functionality-demo-course-parts/1/');
      await hide(p);
      await p.screenshot({path: `${OUT}${who}-player-${sk}.png`, fullPage: true}); done.push(`${who}-player-${sk}:${p.url()}`);
      if (sk === 'm') {
        const btn = p.getByRole('button', {name: /course outline/i}).first();
        if (await btn.count()) { await btn.click(); await p.waitForTimeout(600);
          await p.screenshot({path: `${OUT}${who}-outline-sheet-m.png`}); done.push(`${who}-outline-sheet-m`); }
      }
    }
    await ctx.close();
  }
  return done;
}
