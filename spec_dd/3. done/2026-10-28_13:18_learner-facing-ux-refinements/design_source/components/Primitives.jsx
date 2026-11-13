/* Shared learner-platform UI primitives.
   Re-exports kit primitives and adds a few new ones for richer screens. */

const FCButton = ({ variant = "primary", size, icon, iconAfter, children, style, ...rest }) => {
  const cls = ["fc-btn", `fc-btn-${variant}`, size === "lg" ? "fc-btn-lg" : "", size === "sm" ? "fc-btn-sm" : ""]
    .filter(Boolean).join(" ");
  return (
    <button className={cls} style={style} {...rest}>
      {icon ? <i className={`ph ph-${icon}`}></i> : null}
      {children ? <span>{children}</span> : null}
      {iconAfter ? <i className={`ph ph-${iconAfter}`}></i> : null}
    </button>
  );
};

const FCChip = ({ tone = "neutral", icon, children, style }) => (
  <span className={`fc-chip fc-chip-${tone}`} style={style}>
    {icon ? <i className={`ph ph-${icon}`}></i> : null}
    {children}
  </span>
);

const FCProgress = ({ value, label, height, accent }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
    <div className="fc-track" style={{ flex: 1, height: height || 6 }}>
      <div className="fc-fill" style={{
        width: `${Math.max(0, Math.min(100, value))}%`,
        background: accent || "var(--color-secondary)"
      }} />
    </div>
    {label !== false ? (
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-3)", width: 38, textAlign: "right" }}>
        {Math.round(value)}%
      </span>
    ) : null}
  </div>
);

const FCEyebrow = ({ children, style }) => <div className="fc-eyebrow" style={style}>{children}</div>;

/* Course thumbnail — solid + iconographic, brand palette. */
const CourseThumb = ({ kind, size = "md", chip }) => {
  const map = {
    rpas:        { bg: "linear-gradient(135deg, #283593 0%, #1A237E 100%)", icon: "drone",          color: "#00CEC9" },
    weather:     { bg: "linear-gradient(135deg, #1f4496 0%, #283593 100%)", icon: "cloud-sun",      color: "#FFD580" },
    airspace:    { bg: "linear-gradient(135deg, #00A8A4 0%, #007570 100%)", icon: "map-trifold",    color: "#FFFFFF" },
    instrument:  { bg: "linear-gradient(135deg, #00CEC9 0%, #009A97 100%)", icon: "compass",        color: "#1A1A2E" },
    examiner:    { bg: "linear-gradient(135deg, #1A1A2E 0%, #0F0F1F 100%)", icon: "graduation-cap", color: "#FF6B35" },
    night:       { bg: "linear-gradient(135deg, #14143b 0%, #283593 100%)", icon: "moon-stars",     color: "#FFD580" },
    rules:       { bg: "linear-gradient(135deg, #2D3748 0%, #1A202C 100%)", icon: "scales",         color: "#00CEC9" },
    comms:       { bg: "linear-gradient(135deg, #283593 0%, #4F86F7 100%)", icon: "broadcast",      color: "#FFFFFF" },
    photogram:   { bg: "linear-gradient(135deg, #FF6B35 0%, #C43F1A 100%)", icon: "camera",         color: "#FFFFFF" },
    emergency:   { bg: "linear-gradient(135deg, #C53030 0%, #742A2A 100%)", icon: "first-aid",      color: "#FFFFFF" },
  }[kind] || { bg: "linear-gradient(135deg, #283593, #1A237E)", icon: "circle", color: "#00CEC9" };

  const heights = { sm: 96, md: 132, lg: 160, hero: 168 };
  const iconSizes = { sm: 36, md: 48, lg: 56, hero: 64 };
  const h = heights[size];
  return (
    <div className="fc-thumb" style={{ height: h, background: map.bg }}>
      <i className={`ph-fill ph-${map.icon}`} style={{ fontSize: iconSizes[size], color: map.color, opacity: 0.92 }}></i>
      {/* subtle altitude line */}
      <div className="fc-thumb-grid" />
      {chip ? <div className="fc-thumb-chip">{chip}</div> : null}
      <div className="fc-thumb-stamp" style={{ fontFamily: "var(--font-mono)" }}>FC · {kind.toUpperCase()}</div>
    </div>
  );
};

Object.assign(window, { FCButton, FCChip, FCProgress, FCEyebrow, CourseThumb });
