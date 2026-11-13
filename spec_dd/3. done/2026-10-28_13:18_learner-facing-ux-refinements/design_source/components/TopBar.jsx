/* TopBar — sticky, white, with course-context breadcrumb when in a course. */
const TopBar = ({ active = "courses", onNav, learnerName = "Amara Okafor", learnerInitials = "AO", crumb, coBrand = null }) => {
  const items = [
    { id: "courses",  label: "My courses" },
    { id: "catalog",  label: "Catalogue" },
    { id: "records",  label: "Records" },
    { id: "support",  label: "Support" },
  ];
  return (
    <header className="fc-topbar">
      <div className="left">
        <div className="logo">
          <img src="design-system/assets/logo-color.png" alt="First Class" />
          <span>First Class</span>
        </div>
        {coBrand}
        {crumb ? (
          <div className="fc-crumb">
            <i className="ph ph-caret-right"></i>
            <a href="#" onClick={(e) => { e.preventDefault(); onNav?.("courses"); }}>{crumb.course}</a>
            <i className="ph ph-caret-right"></i>
            <span>{crumb.module}</span>
          </div>
        ) : (
          <nav className="fc-nav">
            {items.map((it) => (
              <a key={it.id}
                 href="#"
                 className={active === it.id ? "active" : ""}
                 onClick={(e) => { e.preventDefault(); onNav?.(it.id); }}>
                {it.label}
              </a>
            ))}
          </nav>
        )}
      </div>
      <div className="right">
        {/* Search */}
        <div className="fc-search">
          <i className="ph ph-magnifying-glass"></i>
          <input placeholder="Search courses, modules, glossary…" />
          <kbd>⌘K</kbd>
        </div>
        <button className="fc-icon-btn" aria-label="Notifications">
          <i className="ph ph-bell"></i>
          <span className="fc-dot" />
        </button>
        <div className="fc-avatar" title={learnerName}>{learnerInitials}</div>
      </div>
    </header>
  );
};

Object.assign(window, { TopBar });
