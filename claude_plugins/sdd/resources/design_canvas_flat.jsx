// Flat stand-in for Claude Design's design-canvas.jsx. Same exports
// (DesignCanvas, DCSection, DCArtboard, DCPostIt), but every artboard renders
// at 1:1 in normal document flow, so a browser can screenshot each one by
// selector: [data-artboard="<section-id>/<artboard-id>"].
function DesignCanvas({ children }) {
  return <div style={{ padding: 40, background: "#ECEEF3" }}>{children}</div>;
}

function DCArtboard() { return null; }

function DCSection({ id, title, subtitle, children }) {
  const boards = React.Children.toArray(children).filter((c) => c && c.type === DCArtboard);
  return (
    <section data-section={id} style={{ marginBottom: 80 }}>
      <h2 style={{ font: "600 24px system-ui", margin: "0 0 4px" }}>{title}</h2>
      {subtitle && <p style={{ font: "14px system-ui", margin: "0 0 24px", color: "#555" }}>{subtitle}</p>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 48, alignItems: "flex-start" }}>
        {boards.map((b) => {
          const { id: aid, label, width = 260, height = 480, children: body } = b.props;
          return (
            <figure key={aid} style={{ margin: 0 }}>
              <figcaption style={{ font: "13px system-ui", marginBottom: 6 }}>{label}</figcaption>
              <div data-artboard={`${id}/${aid}`} data-label={label}
                style={{ width, height, overflow: "hidden", background: "#fff" }}>{body}</div>
            </figure>
          );
        })}
      </div>
    </section>
  );
}

function DCPostIt({ children }) { return <aside>{children}</aside>; }

Object.assign(window, { DesignCanvas, DCSection, DCArtboard, DCPostIt });
