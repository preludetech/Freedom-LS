/* Long-format course rows for a course index / catalogue page, with provider branding slots. */
const PV_INDEX = [
  { id: "airspace", org: "rt", img: "airspace", tag: "Foundation", title: "Airspace Classes for sub-25kg RPAS", desc: "Read a VFR chart, identify controlled and restricted airspace, and plan a legal flight area before you take off.", meta: ["6 modules", "2 hrs", "Self-paced"], price: "Free", mode: "open" },
  { id: "examiner", org: "rt", img: "examiner", tag: "Advanced", title: "Examiner Pathway", desc: "Train to assess RPAS pilots for licensing. Includes supervised practical assessments and a moderated final.", meta: ["12 modules", "22 hrs", "Cohort starts Apr 6"], price: "Application", mode: "apply" },
  { id: "night", img: "night", tag: "Foundation", title: "Night Operations primer", desc: "Lighting, visual illusions and risk controls for flying after civil twilight.", meta: ["3 modules", "90 min", "Self-paced"], price: "Free", mode: "open" },
  { id: "photogram", org: "rt", img: "photogram", tag: "Specialist", title: "Aerial Photogrammetry — Intro", desc: "Plan survey grids, set overlap and ground sampling distance, and process your first orthomosaic.", meta: ["5 modules", "3 hrs", "Self-paced"], price: "Free", mode: "open" },
  { id: "weather", img: "weather", tag: "Theory", title: "Aviation Weather", desc: "METARs, TAFs and the weather conditions that ground small aircraft.", meta: ["4 modules", "5 hrs", "Self-paced"], price: "R 1 450", mode: "paid" },
];

const PvTagChip = ({ c }) => c.mode === "apply" ? <FCChip tone="warning" icon="lock-key">Application</FCChip>
  : c.mode === "open" ? <FCChip tone="success" icon="lightning">Free</FCChip>
  : <FCChip>{c.price}</FCChip>;

const PvIndexRow = ({ c, brand, side, layout }) => {
  const b = (s) => (brand && c.org ? brand(c, s) : null);
  const sideNode = side && c.org ? side(c) : null;
  return (
    <div className="pvx-row">
      <div className="pvx-thumb"><CourseThumb kind={c.img} size="md" badge={b("thumb")} /></div>
      <div className="pvx-body">
        {b("top") || <div className="fc-card-eyebrow">{c.tag}</div>}
        <div className="pvx-title">{c.title}</div>
        <p className="pvx-desc">{c.desc}</p>
        <div className="pvx-meta">{c.meta.map((m) => <span key={m}>{m}</span>)}</div>
        {b("foot")}
      </div>
      {layout === "tagged" ? (
        <div className="pvx-side tagged">
          <PvTagChip c={c} />
          <button className="fc-btn fc-btn-secondary fc-btn-sm"><span>Details</span><i className="ph ph-arrow-right"></i></button>
        </div>
      ) : <div className="pvx-side">
        {sideNode}
        <div className="pvx-price">{c.price === "Application" ? <><i className="ph ph-lock-key"></i>Application</> : c.price}</div>
        {c.mode === "apply"
          ? <button className="fc-btn fc-btn-primary fc-btn-sm"><span>Apply</span><i className="ph ph-arrow-right"></i></button>
          : <button className="fc-btn fc-btn-secondary fc-btn-sm"><span>View course</span></button>}
      </div>}
    </div>
  );
};

const pvSideLogo = (c) => <img className="pvx-sidelogo" src={PROVIDERS[c.org].logoDark} alt={PROVIDERS[c.org].name} />;
const pvSplitRow = (c, s) => s === "top" ? (
  <div className="pvx-split"><PvBadge p={PROVIDERS[c.org]} size={22} /><span className="nm">{PROVIDERS[c.org].name}</span><span className="sep">·</span><span className="tag">{c.tag}</span></div>
) : null;

const PvIndexFrame = ({ brand, side, layout }) => (
  <div className="ato-frame">
    <TopBar active="catalog" />
    <div className="ato-body">
      <div className="pvx-page">
        <div className="pvx-head">
          <h1>Course catalogue</h1>
          <div className="pvx-filters">
            <span className="pvx-chip on">All</span>
            <span className="pvx-chip">Foundation</span>
            <span className="pvx-chip">Specialist</span>
            <span className="pvx-chip">Advanced</span>
            <span className="pvx-div"></span>
            <span className="pvx-chip prov"><PvBadge p={PROVIDERS.rt} size={18} />RPAS Training Academy</span>
          </div>
        </div>
        <div className="pvx-list">{PV_INDEX.map((c) => <PvIndexRow key={c.id} c={c} brand={brand} side={side} layout={layout} />)}</div>
      </div>
    </div>
  </div>
);

Object.assign(window, { PV_INDEX, PvIndexRow, PvIndexFrame, pvSideLogo, pvSplitRow });
