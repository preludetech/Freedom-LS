/* Course provider branding — school/organisation logo + name on cards and course detail. */
const PROVIDERS = {
  rt: {
    name: "RPAS Training Academy",
    short: "RPAS Training",
    badge: "assets/providers/rt-badge.png",
    logoDark: "assets/providers/rt-navy-h.png",
    logoLight: "assets/providers/rt-gradient-h.png",
    logoLightV: "assets/providers/rt-gradient-v.png",
    color: "#111a27",
    courses: 6,
  },
};

const PvBadge = ({ p, size = 22, ring = false }) => (
  <span className={"pv-badge" + (ring ? " ring" : "")} style={{ width: size, height: size }}><img src={p.badge} alt="" /></span>
);

/* ---------- card renderers: brand(c, slot) -> node. slot: "thumb" | "top" | "foot" ---------- */
const P = (c) => PROVIDERS[c.org];
const brandThumb = (c, s) => s === "thumb" ? <span className="pv-pill"><PvBadge p={P(c)} size={20} />{P(c).short}</span> : null;
const brandRow = (c, s) => s === "top" ? <div className="pv-row"><PvBadge p={P(c)} size={20} /><span>{P(c).name}</span></div> : null;
const brandFoot = (c, s) => s === "foot" ? <div className="pv-foot"><span>Offered by</span><img src={P(c).logoDark} alt={P(c).name} /></div> : null;
const brandBand = (c, s) => s === "thumb" ? <div className="pv-band"><img src={P(c).logoLight} alt={P(c).name} /></div> : null;
const brandAvatar = (c, s) => s === "top" ? (
  <div className="pv-avatar"><PvBadge p={P(c)} size={44} ring /><span>{P(c).name}</span></div>
) : null;
const brandCorner = (c, s) => s === "thumb" ? <span title={P(c).name}><PvBadge p={P(c)} size={34} ring /></span> : null;

/* ---------- detail-level pieces ---------- */
const PvHeroBar = ({ p = PROVIDERS.rt }) => (
  <div className="pv-herobar">
    <PvBadge p={p} size={40} ring />
    <div className="id">
      <span className="k">Course provider</span>
      <span className="nm">{p.name}</span>
    </div>
    <a href="#" className="lnk">About the provider <i className="ph ph-arrow-right"></i></a>
  </div>
);
const PvHeroArt = ({ p = PROVIDERS.rt }) => (
  <div className="pv-heroart"><img src={p.logoLightV} alt={p.name} /></div>
);
const PvMasthead = ({ p = PROVIDERS.rt }) => (
  <div className="pv-masthead">
    <div className="in">
      <img src={p.logoDark} alt={p.name} />
      <span className="rule"></span>
      <div className="txt"><span className="k">Course provider</span><span>This course is written and run by <strong>{p.name}</strong>.</span></div>
      <a href="#" className="lnk">All {p.courses} courses <i className="ph ph-arrow-right"></i></a>
    </div>
  </div>
);
const PvTitleBadge = ({ p = PROVIDERS.rt }) => <PvBadge p={p} size={84} ring />;
const PvHeroCard = ({ p = PROVIDERS.rt }) => (
  <div className="pv-herocard">
    <span className="k">Offered by</span>
    <img src={p.logoLight} alt={p.name} />
    <div className="nm">{p.name}</div>
    <a href="#" className="lnk">{p.courses} courses from this provider <i className="ph ph-arrow-right"></i></a>
  </div>
);
const PvPanel = ({ p = PROVIDERS.rt }) => (
  <div className="pv-panel">
    <span className="pv-eyebrow">Course provider</span>
    <div className="pv-panel-id">
      <PvBadge p={p} size={52} />
      <div>
        <div className="nm">{p.name}</div>
        <div className="sub">{p.courses} courses on First Class</div>
      </div>
    </div>
    <p className="txt">This course is written and run by {p.name}. Their instructors mark your assessments and issue your certificate.</p>
    <a className="lnk" href="#">All courses from {p.short} <i className="ph ph-arrow-right"></i></a>
  </div>
);

const PvDashboardFrame = ({ brand }) => (
  <div className="ato-frame">
    <TopBar active="courses" />
    <div className="ato-body"><Dashboard brand={brand} /></div>
  </div>
);

/* header: "bar" | "theme" | "masthead" | "title" | "card" | null */
const PvDetailFrame = ({ header = null, panel = false }) => {
  const p = PROVIDERS.rt;
  return (
    <div className="ato-frame">
      <TopBar active="catalog" />
      <div className="ato-body">
        <CourseOverview course={COURSE_ENROLL}
          heroBrand={header === "bar" ? <PvHeroBar /> : null}
          heroCorner={header === "card" ? <PvHeroCard /> : null}
          preHero={header === "masthead" ? <PvMasthead /> : null}
          heroBg={header === "theme" ? `radial-gradient(120% 140% at 85% 30%, #24324a 0%, ${p.color} 60%)` : null}
          heroArt={header === "theme" ? <PvHeroArt /> : null}
          heroClass={header === "theme" ? "pv-themed" : header === "card" ? "pv-has-card" : ""}
          titleBrand={header === "title" ? <PvTitleBadge /> : null}
          atoPanel={panel ? <PvPanel /> : null} />
      </div>
    </div>
  );
};

Object.assign(window, { PROVIDERS, PvBadge, brandThumb, brandRow, brandFoot, brandBand, brandAvatar, brandCorner, PvHeroBar, PvHeroArt, PvMasthead, PvTitleBadge, PvHeroCard, PvPanel, PvDashboardFrame, PvDetailFrame });
