/* @ds-bundle: {"format":3,"namespace":"FirstClassDesignSystem3_019df6","components":[],"sourceHashes":{"ui_kits/learner-platform/App.jsx":"5b3d0cd1b066","ui_kits/learner-platform/CoursePlayer.jsx":"94fba0a504d6","ui_kits/learner-platform/Dashboard.jsx":"0be62df76cb4","ui_kits/learner-platform/LoginScreen.jsx":"29ea24aeba23","ui_kits/learner-platform/Primitives.jsx":"13d651000bd9","ui_kits/learner-platform/QuizScreen.jsx":"b838297af357","ui_kits/learner-platform/ResultsScreen.jsx":"2600cc9a4c04","ui_kits/learner-platform/Sidebar.jsx":"4a0ab28f2f55","ui_kits/learner-platform/TopBar.jsx":"5fbacfa7382d"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.FirstClassDesignSystem3_019df6 = window.FirstClassDesignSystem3_019df6 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// ui_kits/learner-platform/App.jsx
try { (() => {
/* App — top-level state machine + screen router. */
const App = () => {
  const [screen, setScreen] = React.useState("login"); // login | dashboard | course | quiz | results

  // Login flow
  if (screen === "login") {
    return /*#__PURE__*/React.createElement("div", {
      className: "fc-app"
    }, /*#__PURE__*/React.createElement(LoginScreen, {
      onLogin: () => setScreen("dashboard")
    }), /*#__PURE__*/React.createElement(ScreenSwitcher, {
      current: screen,
      setScreen: setScreen
    }));
  }

  // Authenticated screens — share TopBar
  return /*#__PURE__*/React.createElement("div", {
    className: "fc-app"
  }, /*#__PURE__*/React.createElement(TopBar, {
    active: screen === "dashboard" ? "courses" : "courses",
    onNav: id => {
      if (id === "courses") setScreen("dashboard");
    }
  }), screen === "dashboard" && /*#__PURE__*/React.createElement("div", {
    className: "fc-content"
  }, /*#__PURE__*/React.createElement(Dashboard, {
    onContinue: () => setScreen("course"),
    onOpenCourse: () => setScreen("course")
  })), screen === "course" && /*#__PURE__*/React.createElement(CoursePlayer, {
    onOpenQuiz: () => setScreen("quiz")
  }), screen === "quiz" && /*#__PURE__*/React.createElement(QuizScreen, {
    onSubmit: () => setScreen("results"),
    onBack: () => setScreen("course")
  }), screen === "results" && /*#__PURE__*/React.createElement(ResultsScreen, {
    onContinue: () => setScreen("dashboard"),
    onRetry: () => setScreen("course"),
    onBack: () => setScreen("dashboard")
  }), /*#__PURE__*/React.createElement(ScreenSwitcher, {
    current: screen,
    setScreen: setScreen
  }));
};

/* Floating screen switcher — lets reviewers jump between flows
   without having to play through them in sequence. */
const ScreenSwitcher = ({
  current,
  setScreen
}) => {
  const screens = [{
    id: "login",
    label: "Login",
    icon: "sign-in"
  }, {
    id: "dashboard",
    label: "Dashboard",
    icon: "squares-four"
  }, {
    id: "course",
    label: "Course",
    icon: "book-open"
  }, {
    id: "quiz",
    label: "Quiz",
    icon: "question"
  }, {
    id: "results",
    label: "Results",
    icon: "medal"
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "fixed",
      bottom: 16,
      left: "50%",
      transform: "translateX(-50%)",
      background: "var(--grey-900)",
      color: "white",
      borderRadius: 999,
      padding: 6,
      display: "flex",
      gap: 4,
      boxShadow: "var(--shadow-lg)",
      zIndex: 100
    }
  }, screens.map(s => {
    const active = current === s.id;
    return /*#__PURE__*/React.createElement("button", {
      key: s.id,
      onClick: () => setScreen(s.id),
      style: {
        background: active ? "var(--color-primary)" : "transparent",
        color: active ? "white" : "rgba(255,255,255,.65)",
        border: "none",
        padding: "8px 14px",
        borderRadius: 999,
        fontFamily: "var(--font-body)",
        fontWeight: 600,
        fontSize: 12,
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: 6,
        transition: "background 200ms var(--ease-out), color 200ms"
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: `ph ph-${s.icon}`,
      style: {
        fontSize: 14
      }
    }), s.label);
  }));
};
ReactDOM.createRoot(document.getElementById("root")).render(/*#__PURE__*/React.createElement(App, null));
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/App.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/CoursePlayer.jsx
try { (() => {
/* Course player — sidebar + reading area + footer nav. */
const CoursePlayer = ({
  onNext,
  onOpenQuiz
}) => {
  const [currentId, setCurrentId] = React.useState("m3");
  const modules = [{
    id: "m1",
    title: "Airspace fundamentals",
    complete: true,
    locked: false
  }, {
    id: "m2",
    title: "Aircraft systems",
    complete: true,
    locked: false
  }, {
    id: "m3",
    title: "Pre-flight checklist",
    complete: false,
    locked: false
  }, {
    id: "m4",
    title: "Weather minima",
    complete: false,
    locked: false
  }, {
    id: "m5",
    title: "Flight planning",
    complete: false,
    locked: true
  }, {
    id: "m6",
    title: "Emergency procedures",
    complete: false,
    locked: true
  }, {
    id: "m7",
    title: "Practical assessment",
    complete: false,
    locked: true
  }, {
    id: "m8",
    title: "Final examination",
    complete: false,
    locked: true
  }];
  return /*#__PURE__*/React.createElement("div", {
    className: "fc-shell",
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement(Sidebar, {
    modules: modules,
    currentId: currentId,
    onSelect: setCurrentId
  }), /*#__PURE__*/React.createElement("main", {
    className: "fc-main"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      borderBottom: "1px solid var(--border)",
      padding: "20px 48px",
      background: "#fff"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement(FCEyebrow, null, "RPAS Standard \xB7 Module 3 of 8"), /*#__PURE__*/React.createElement(FCChip, {
    tone: "info"
  }, "Practical"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      color: "var(--fg-3)",
      marginLeft: "auto",
      fontFamily: "var(--font-mono)"
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "ph ph-clock",
    style: {
      verticalAlign: -2,
      marginRight: 4
    }
  }), "~12 min remaining")), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 700,
      fontSize: 30,
      letterSpacing: "-0.02em",
      color: "var(--fg-1)",
      margin: "4px 0 14px"
    }
  }, "Pre-flight checklist"), /*#__PURE__*/React.createElement(FCProgress, {
    value: 62
  })), /*#__PURE__*/React.createElement("div", {
    className: "fc-content",
    style: {
      background: "var(--bg)"
    }
  }, /*#__PURE__*/React.createElement("article", {
    style: {
      maxWidth: 760,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 24,
      color: "var(--fg-1)",
      marginBottom: 16
    }
  }, "Section 3.2 \u2014 Battery and propulsion check"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 17,
      lineHeight: 1.65,
      color: "var(--fg-2)",
      marginBottom: 16
    }
  }, "Before every flight, verify your battery's terminal voltage with an independent voltmeter \u2014 not just the flight controller's onboard reading. A 4S LiPo at ", /*#__PURE__*/React.createElement("strong", null, "15.8V"), " resting indicates a healthy charge; anything below ", /*#__PURE__*/React.createElement("strong", null, "15.0V"), " should be recharged before takeoff."), /*#__PURE__*/React.createElement("div", {
    className: "fc-alert fc-alert-info",
    style: {
      margin: "20px 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "h"
  }, "Hint."), "Battery voltage drops under load. Always check resting voltage first, then verify the controller's telemetry matches within \xB10.1V before arming the motors."), /*#__PURE__*/React.createElement("div", {
    className: "fc-img-ph",
    style: {
      height: 220,
      margin: "24px 0"
    }
  }, "[diagram \xB7 battery terminal layout]"), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 19,
      color: "var(--fg-1)",
      margin: "8px 0 10px"
    }
  }, "Propeller integrity"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 17,
      lineHeight: 1.65,
      color: "var(--fg-2)",
      marginBottom: 12
    }
  }, "Inspect each propeller for chips, hairline cracks, and lateral play at the hub. A propeller with even a", /*#__PURE__*/React.createElement("em", null, " 2\xA0mm "), "nick should be replaced \u2014 fatigue propagates rapidly under flight loads."), /*#__PURE__*/React.createElement("ul", {
    style: {
      fontSize: 16,
      lineHeight: 1.7,
      color: "var(--fg-2)",
      paddingLeft: 20,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("li", null, "Check rotational symmetry \u2014 spin each prop and observe wobble."), /*#__PURE__*/React.createElement("li", null, "Verify torque on retaining nuts to manufacturer spec."), /*#__PURE__*/React.createElement("li", null, "Replace as a matched set; never mix new and worn props on the same airframe.")), /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--grey-900)",
      color: "#E2E8F0",
      padding: "16px 18px",
      borderRadius: 10,
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      lineHeight: 1.7,
      margin: "20px 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: "#A0AEC0"
    }
  }, "// pre-flight verification log"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#00CEC9"
    }
  }, "BAT"), ".", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#FF6B35"
    }
  }, "verify"), "(", /*#__PURE__*/React.createElement("span", null, "\"voltage_min\""), ", ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#FFD580"
    }
  }, "15.0"), ");"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#00CEC9"
    }
  }, "PROP"), ".", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#FF6B35"
    }
  }, "inspect"), "(", /*#__PURE__*/React.createElement("span", null, "\"all\""), ");"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#00CEC9"
    }
  }, "GPS"), ".", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#FF6B35"
    }
  }, "lock"), "(", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#FFD580"
    }
  }, "10"), "); ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#A0AEC0"
    }
  }, "// satellites"))))), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: "1px solid var(--border)",
      background: "#fff",
      padding: "16px 48px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(FCButton, {
    variant: "ghost",
    icon: "arrow-left"
  }, "Section 3.1"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6
    }
  }, [1, 2, 3, 4, 5].map(n => /*#__PURE__*/React.createElement("span", {
    key: n,
    style: {
      width: 24,
      height: 4,
      borderRadius: 2,
      background: n <= 2 ? "var(--color-secondary)" : "var(--grey-200)"
    }
  }))), /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    iconAfter: "arrow-right",
    onClick: onOpenQuiz
  }, "Section quiz"))));
};
Object.assign(window, {
  CoursePlayer
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/CoursePlayer.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/Dashboard.jsx
try { (() => {
/* Dashboard — greeting, continue card, course grid. */
const Dashboard = ({
  onContinue,
  onOpenCourse
}) => {
  const courses = [{
    id: "rpas",
    title: "RPAS Standard",
    subtitle: "8 modules · 14 hours",
    progress: 62,
    status: "in-progress",
    tag: "Practical",
    img: "drone"
  }, {
    id: "ifr",
    title: "IFR Foundations",
    subtitle: "6 modules · 9 hours",
    progress: 100,
    status: "complete",
    tag: "Theory",
    img: "instrument"
  }, {
    id: "wx",
    title: "Aviation Weather",
    subtitle: "4 modules · 5 hours",
    progress: 28,
    status: "in-progress",
    tag: "Theory",
    img: "weather"
  }, {
    id: "exam",
    title: "Examiner Pathway",
    subtitle: "12 modules · 22 hours",
    progress: 0,
    status: "locked",
    tag: "Advanced",
    img: "examiner"
  }];
  const ImgPlaceholder = ({
    kind
  }) => {
    const map = {
      drone: {
        bg: "linear-gradient(135deg, #283593, #1A237E)",
        icon: "drone",
        color: "#00CEC9"
      },
      instrument: {
        bg: "linear-gradient(135deg, #00CEC9, #009A97)",
        icon: "compass",
        color: "#FFFFFF"
      },
      weather: {
        bg: "linear-gradient(135deg, #4F86F7, #3F70D9)",
        icon: "cloud-sun",
        color: "#FFFFFF"
      },
      examiner: {
        bg: "linear-gradient(135deg, #1A1A2E, #0F0F1F)",
        icon: "graduation-cap",
        color: "#FF6B35"
      }
    }[kind];
    return /*#__PURE__*/React.createElement("div", {
      style: {
        height: 110,
        borderRadius: 10,
        background: map.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 14,
        position: "relative",
        overflow: "hidden"
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: `ph ph-${map.icon}`,
      style: {
        fontSize: 44,
        color: map.color,
        opacity: 0.92
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        position: "absolute",
        right: 10,
        top: 10
      }
    }, /*#__PURE__*/React.createElement(FCChip, {
      tone: kind === "examiner" ? "neutral" : "primary"
    }, kind === "examiner" ? "Locked" : "Enrolled")));
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "fc-prose-wrap"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 28
    }
  }, /*#__PURE__*/React.createElement(FCEyebrow, null, "Friday \xB7 14 February"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 700,
      fontSize: 36,
      letterSpacing: "-0.02em",
      margin: "8px 0 6px",
      color: "var(--fg-1)"
    }
  }, "Welcome back, Amara."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 16,
      color: "var(--fg-3)"
    }
  }, "You're 38% away from completing your RPAS certification.")), /*#__PURE__*/React.createElement("div", {
    className: "fc-card-elev",
    style: {
      display: "grid",
      gridTemplateColumns: "180px 1fr auto",
      gap: 24,
      alignItems: "center",
      marginBottom: 28,
      padding: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 120,
      width: 180,
      borderRadius: 10,
      background: "linear-gradient(135deg, #283593, #1A237E)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "ph-fill ph-drone",
    style: {
      fontSize: 56,
      color: "#00CEC9"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      bottom: 8,
      left: 10,
      fontFamily: "var(--font-mono)",
      fontSize: 10,
      color: "rgba(255,255,255,.7)",
      letterSpacing: "0.06em"
    }
  }, "RPAS \xB7 MOD 3 / 8")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement(FCChip, {
    tone: "primary",
    icon: "play-circle"
  }, "Continue learning"), /*#__PURE__*/React.createElement(FCChip, {
    tone: "info"
  }, "Practical")), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 22,
      color: "var(--fg-1)",
      margin: "0 0 4px"
    }
  }, "Module 3 \u2014 Pre-flight checklist"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      color: "var(--fg-3)",
      marginBottom: 12
    }
  }, "Section 3.2 of 5 \xB7 12 minutes remaining"), /*#__PURE__*/React.createElement(FCProgress, {
    value: 62
  })), /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    size: "lg",
    iconAfter: "arrow-right",
    onClick: onContinue
  }, "Resume")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      justifyContent: "space-between",
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 20,
      color: "var(--fg-1)"
    }
  }, "Your courses"), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      color: "var(--color-primary)",
      fontWeight: 600,
      fontSize: 14,
      textDecoration: "none"
    }
  }, "Browse catalogue \u2192")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
      gap: 16
    }
  }, courses.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.id,
    className: "fc-card-interactive",
    onClick: () => onOpenCourse?.(c.id),
    style: {
      opacity: c.status === "locked" ? 0.6 : 1
    }
  }, /*#__PURE__*/React.createElement(ImgPlaceholder, {
    kind: c.img
  }), /*#__PURE__*/React.createElement(FCEyebrow, null, "Course \xB7 ", c.tag), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 17,
      margin: "6px 0 4px",
      color: "var(--fg-1)"
    }
  }, c.title), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--fg-3)",
      marginBottom: 14
    }
  }, c.subtitle), c.status === "locked" ? /*#__PURE__*/React.createElement(FCChip, {
    tone: "neutral",
    icon: "lock-key"
  }, "Prerequisites required") : c.status === "complete" ? /*#__PURE__*/React.createElement(FCChip, {
    tone: "success",
    icon: "check-circle"
  }, "Complete \xB7 Certified") : /*#__PURE__*/React.createElement(FCProgress, {
    value: c.progress
  })))));
};
Object.assign(window, {
  Dashboard
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/Dashboard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/LoginScreen.jsx
try { (() => {
/* Login screen — clean split-pane: brand panel + form. */
const LoginScreen = ({
  onLogin
}) => {
  const [email, setEmail] = React.useState("amara.okafor@skybridge.aero");
  const [pw, setPw] = React.useState("••••••••••");
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100vh",
      display: "grid",
      gridTemplateColumns: "1fr 1fr"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--color-primary)",
      color: "white",
      padding: "64px 56px",
      display: "flex",
      flexDirection: "column",
      justifyContent: "space-between",
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      inset: 0,
      opacity: 0.18,
      pointerEvents: "none"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 800 1000",
    preserveAspectRatio: "xMidYMid slice",
    style: {
      width: "100%",
      height: "100%"
    }
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("pattern", {
    id: "grid",
    width: "80",
    height: "80",
    patternUnits: "userSpaceOnUse"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M 80 0 L 0 0 0 80",
    fill: "none",
    stroke: "white",
    strokeWidth: "0.5"
  }))), /*#__PURE__*/React.createElement("rect", {
    width: "100%",
    height: "100%",
    fill: "url(#grid)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M 50 800 Q 300 600, 500 500 T 800 200",
    stroke: "var(--color-secondary)",
    strokeWidth: "2",
    fill: "none"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "500",
    cy: "500",
    r: "6",
    fill: "var(--color-secondary)"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "800",
    cy: "200",
    r: "6",
    fill: "var(--color-accent)"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-white-variation.png",
    alt: "First Class",
    style: {
      height: 36
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement(FCEyebrow, null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "rgba(255,255,255,.7)"
    }
  }, "Training, elevated.")), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 700,
      fontSize: 44,
      lineHeight: 1.1,
      letterSpacing: "-0.02em",
      margin: "12px 0 16px"
    }
  }, "Built for the standard your operations demand."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 16,
      lineHeight: 1.6,
      color: "rgba(255,255,255,.78)",
      maxWidth: 460
    }
  }, "Aviation-grade learning for drone operators, examiners, and certified flight schools across Africa.")), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      gap: 24,
      fontSize: 13,
      color: "rgba(255,255,255,.65)",
      fontFamily: "var(--font-mono)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "SACAA-aligned"), /*#__PURE__*/React.createElement("span", null, "\xB7"), /*#__PURE__*/React.createElement("span", null, "RPAS standard"), /*#__PURE__*/React.createElement("span", null, "\xB7"), /*#__PURE__*/React.createElement("span", null, "v2.0 syllabus"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 48,
      background: "var(--bg)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: "100%",
      maxWidth: 380
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 28,
      marginBottom: 8,
      color: "var(--fg-1)"
    }
  }, "Sign in to continue"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 14,
      color: "var(--fg-3)",
      marginBottom: 32
    }
  }, "Pick up where you left off in ", /*#__PURE__*/React.createElement("strong", {
    style: {
      color: "var(--fg-2)"
    }
  }, "RPAS Standard \u2014 Module 3"), "."), /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      onLogin?.();
    },
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 18
    }
  }, /*#__PURE__*/React.createElement(FCField, {
    label: "Email"
  }, /*#__PURE__*/React.createElement("input", {
    className: "fc-input",
    type: "email",
    value: email,
    onChange: e => setEmail(e.target.value)
  })), /*#__PURE__*/React.createElement(FCField, {
    label: "Password",
    helper: "Forgot password?"
  }, /*#__PURE__*/React.createElement("input", {
    className: "fc-input",
    type: "password",
    value: pw,
    onChange: e => setPw(e.target.value)
  })), /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    size: "lg",
    iconAfter: "arrow-right"
  }, "Sign in")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 28,
      fontSize: 13,
      color: "var(--fg-3)",
      textAlign: "center"
    }
  }, "New to First Class?", " ", /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      color: "var(--color-primary)",
      fontWeight: 600,
      textDecoration: "none"
    }
  }, "Browse the catalogue \u2192")))));
};
Object.assign(window, {
  LoginScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/LoginScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/Primitives.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Primitives — small, reusable building blocks for the kit. */

const FCButton = ({
  variant = "primary",
  size,
  icon,
  iconAfter,
  children,
  ...rest
}) => {
  const cls = ["fc-btn", `fc-btn-${variant}`, size === "lg" ? "fc-btn-lg" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("button", _extends({
    className: cls
  }, rest), icon ? /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon}`
  }) : null, /*#__PURE__*/React.createElement("span", null, children), iconAfter ? /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${iconAfter}`
  }) : null);
};
const FCChip = ({
  tone = "neutral",
  icon,
  children
}) => /*#__PURE__*/React.createElement("span", {
  className: `fc-chip fc-chip-${tone}`
}, icon ? /*#__PURE__*/React.createElement("i", {
  className: `ph ph-${icon}`
}) : null, children);
const FCProgress = ({
  value,
  label
}) => /*#__PURE__*/React.createElement("div", {
  style: {
    display: "flex",
    alignItems: "center",
    gap: 12
  }
}, /*#__PURE__*/React.createElement("div", {
  className: "fc-track",
  style: {
    flex: 1
  }
}, /*#__PURE__*/React.createElement("div", {
  className: "fc-fill",
  style: {
    width: `${Math.max(0, Math.min(100, value))}%`
  }
})), label !== false ? /*#__PURE__*/React.createElement("span", {
  style: {
    fontFamily: "var(--font-mono)",
    fontSize: 12,
    color: "var(--fg-3)",
    width: 38,
    textAlign: "right"
  }
}, Math.round(value), "%") : null);
const FCEyebrow = ({
  children
}) => /*#__PURE__*/React.createElement("div", {
  className: "fc-eyebrow"
}, children);
const FCField = ({
  label,
  helper,
  error,
  children
}) => /*#__PURE__*/React.createElement("div", null, label ? /*#__PURE__*/React.createElement("label", {
  className: "fc-label"
}, label) : null, children, helper && !error ? /*#__PURE__*/React.createElement("div", {
  style: {
    fontSize: 13,
    color: "var(--fg-3)",
    marginTop: 4
  }
}, helper) : null, error ? /*#__PURE__*/React.createElement("div", {
  style: {
    fontSize: 13,
    color: "var(--color-error)",
    marginTop: 4
  }
}, error) : null);
Object.assign(window, {
  FCButton,
  FCChip,
  FCProgress,
  FCEyebrow,
  FCField
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/Primitives.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/QuizScreen.jsx
try { (() => {
/* Quiz screen — single question with selectable answers + immediate feedback. */
const QuizScreen = ({
  onSubmit,
  onBack
}) => {
  const [selected, setSelected] = React.useState(null);
  const [submitted, setSubmitted] = React.useState(false);
  const correctIdx = 1;
  const answers = ["12.0 V — anything above flight-controller cut-off", "15.0 V — verified resting, before takeoff", "16.8 V — the cell maximum, always charge fully", "It depends on the manufacturer's spec sheet only"];
  const submit = () => {
    if (selected == null) return;
    setSubmitted(true);
  };
  const isCorrect = selected === correctIdx;
  return /*#__PURE__*/React.createElement("div", {
    className: "fc-content",
    style: {
      background: "var(--bg)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 720,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement(FCEyebrow, null, "RPAS Standard \xB7 Section 3.2 quiz \xB7 Question 1 of 4"), /*#__PURE__*/React.createElement(FCChip, {
    tone: "primary"
  }, "Untimed")), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 26,
      color: "var(--fg-1)",
      lineHeight: 1.3,
      marginBottom: 6
    }
  }, "What is the minimum acceptable resting voltage for a 4S LiPo before takeoff?"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 14,
      color: "var(--fg-3)",
      marginBottom: 24
    }
  }, "Choose the answer that reflects the standard pre-flight threshold."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 10
    }
  }, answers.map((text, i) => {
    const letter = String.fromCharCode(65 + i);
    let cls = "fc-answer";
    if (submitted) {
      if (i === correctIdx) cls += " correct";else if (i === selected) cls += " wrong";
    } else if (selected === i) cls += " selected";
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: cls,
      onClick: () => !submitted && setSelected(i)
    }, /*#__PURE__*/React.createElement("div", {
      className: "marker"
    }, submitted && i === correctIdx ? /*#__PURE__*/React.createElement("i", {
      className: "ph ph-check",
      style: {
        fontSize: 14
      }
    }) : submitted && i === selected ? /*#__PURE__*/React.createElement("i", {
      className: "ph ph-x",
      style: {
        fontSize: 14
      }
    }) : letter), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, text));
  })), submitted && /*#__PURE__*/React.createElement("div", {
    className: `fc-alert ${isCorrect ? "fc-alert-success" : "fc-alert-error"}`,
    style: {
      marginTop: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "h"
  }, isCorrect ? "Correct." : "Not quite."), isCorrect ? "15.0V resting is the SACAA-aligned threshold — below that, recharge before takeoff." : "The standard is 15.0V resting. Anything lower risks an in-flight cut-out under load."), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 28,
      paddingTop: 18,
      borderTop: "1px solid var(--border)",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement(FCButton, {
    variant: "ghost",
    icon: "arrow-left",
    onClick: onBack
  }, "Back to lesson"), submitted ? /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    iconAfter: "arrow-right",
    onClick: onSubmit
  }, "See full results") : /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    disabled: selected == null,
    onClick: submit
  }, "Submit answer"))));
};
Object.assign(window, {
  QuizScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/QuizScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/ResultsScreen.jsx
try { (() => {
/* Results screen — module-level outcome with breakdown + next step. */
const ResultsScreen = ({
  onContinue,
  onRetry,
  onBack
}) => {
  const [outcome, setOutcome] = React.useState("pass"); // 'pass' | 'fail'
  const score = outcome === "pass" ? 84 : 58;
  const breakdown = [{
    name: "Airspace classification",
    score: outcome === "pass" ? 100 : 80
  }, {
    name: "Battery & propulsion",
    score: outcome === "pass" ? 92 : 60
  }, {
    name: "Weather minima",
    score: outcome === "pass" ? 72 : 45
  }, {
    name: "Emergency procedures",
    score: outcome === "pass" ? 78 : 48
  }];
  const passed = outcome === "pass";
  return /*#__PURE__*/React.createElement("div", {
    className: "fc-content",
    style: {
      background: "var(--bg)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 760,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "inline-flex",
      padding: 4,
      gap: 4,
      marginBottom: 24,
      background: "var(--grey-100)",
      borderRadius: 999
    }
  }, ["pass", "fail"].map(o => /*#__PURE__*/React.createElement("button", {
    key: o,
    onClick: () => setOutcome(o),
    style: {
      padding: "6px 14px",
      borderRadius: 999,
      border: "none",
      background: outcome === o ? "#fff" : "transparent",
      boxShadow: outcome === o ? "var(--shadow-sm)" : "none",
      fontFamily: "var(--font-body)",
      fontWeight: 600,
      fontSize: 12,
      color: outcome === o ? "var(--color-primary)" : "var(--fg-3)",
      cursor: "pointer",
      textTransform: "capitalize"
    }
  }, o === "pass" ? "Passed state" : "Failed state"))), /*#__PURE__*/React.createElement("div", {
    className: "fc-card-elev",
    style: {
      padding: 32,
      marginBottom: 20,
      display: "grid",
      gridTemplateColumns: "auto 1fr",
      gap: 32,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      width: 140,
      height: 140
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 120 120",
    width: "140",
    height: "140",
    style: {
      transform: "rotate(-90deg)"
    }
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "60",
    cy: "60",
    r: "52",
    stroke: "var(--grey-200)",
    strokeWidth: "10",
    fill: "none"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "60",
    cy: "60",
    r: "52",
    stroke: passed ? "var(--color-success)" : "var(--color-error)",
    strokeWidth: "10",
    fill: "none",
    strokeLinecap: "round",
    strokeDasharray: `${score / 100 * 2 * Math.PI * 52} ${2 * Math.PI * 52}`
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 700,
      fontSize: 32,
      color: "var(--fg-1)"
    }
  }, score, "%"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: "var(--fg-3)",
      textTransform: "uppercase",
      letterSpacing: ".12em",
      fontWeight: 600
    }
  }, "your score"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(FCChip, {
    tone: passed ? "success" : "error",
    icon: passed ? "check-circle" : "warning"
  }, passed ? "Passed · 80% threshold" : "Below 80% threshold"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 700,
      fontSize: 30,
      letterSpacing: "-0.02em",
      color: "var(--fg-1)",
      margin: "12px 0 8px",
      lineHeight: 1.15
    }
  }, passed ? "You've completed Module 3." : "You scored 58%. Let's review and try again."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 15,
      color: "var(--fg-3)",
      lineHeight: 1.55
    }
  }, passed ? "Strong performance on practical procedures. Module 4 — Weather minima — is now unlocked." : "You're close. Review the flagged sections below, then retake when you're ready — there's no penalty for retakes."))), /*#__PURE__*/React.createElement("div", {
    className: "fc-card",
    style: {
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: "var(--font-heading)",
      fontWeight: 600,
      fontSize: 17,
      color: "var(--fg-1)",
      marginBottom: 14
    }
  }, "Topic breakdown"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 12
    }
  }, breakdown.map(b => {
    const weak = b.score < 70;
    return /*#__PURE__*/React.createElement("div", {
      key: b.name,
      style: {
        display: "grid",
        gridTemplateColumns: "1fr 200px 60px 90px",
        gap: 14,
        alignItems: "center"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 14,
        color: "var(--fg-2)",
        fontWeight: 500
      }
    }, b.name), /*#__PURE__*/React.createElement("div", {
      className: "fc-track"
    }, /*#__PURE__*/React.createElement("div", {
      className: "fc-fill",
      style: {
        width: `${b.score}%`,
        background: weak ? "var(--color-error)" : "var(--color-secondary)"
      }
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        color: "var(--fg-3)",
        textAlign: "right"
      }
    }, b.score, "%"), weak ? /*#__PURE__*/React.createElement(FCChip, {
      tone: "error"
    }, "Review") : /*#__PURE__*/React.createElement(FCChip, {
      tone: "success"
    }, "On standard"));
  }))), /*#__PURE__*/React.createElement("div", {
    className: "fc-alert fc-alert-primary",
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "h",
    style: {
      color: "var(--color-primary)"
    }
  }, passed ? "Up next" : "Recommended next"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--fg-2)",
      fontSize: 14
    }
  }, passed ? "Module 4 — Weather minima · ~1 hr 20 min" : "Review Section 3.3 (Weather minima) before retaking the assessment")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(FCButton, {
    variant: "ghost",
    onClick: onBack
  }, "Back to dashboard"), passed ? /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    iconAfter: "arrow-right",
    onClick: onContinue
  }, "Start Module 4") : /*#__PURE__*/React.createElement(FCButton, {
    variant: "primary",
    icon: "arrow-clockwise",
    onClick: onRetry
  }, "Review & retake")))));
};
Object.assign(window, {
  ResultsScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/ResultsScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/Sidebar.jsx
try { (() => {
/* Course-player sidebar with module tree. */
const Sidebar = ({
  modules,
  currentId,
  onSelect
}) => /*#__PURE__*/React.createElement("aside", {
  className: "fc-sidebar"
}, /*#__PURE__*/React.createElement("h4", null, "Course modules"), modules.map((m, i) => {
  const cls = ["module-link", m.id === currentId ? "active" : "", m.locked ? "locked" : ""].filter(Boolean).join(" ");
  const icon = m.complete ? "ph-check-circle" : m.locked ? "ph-lock-key" : m.id === currentId ? "ph-play-circle" : "ph-circle";
  const iconColor = m.complete ? "var(--color-success)" : m.id === currentId ? "var(--color-primary)" : "currentColor";
  return /*#__PURE__*/React.createElement("div", {
    key: m.id,
    className: cls,
    onClick: () => !m.locked && onSelect?.(m.id)
  }, /*#__PURE__*/React.createElement("i", {
    className: `ph ${icon}`,
    style: {
      color: iconColor
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      minWidth: 0,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
    }
  }, m.title), /*#__PURE__*/React.createElement("span", {
    className: "num"
  }, String(i + 1).padStart(2, "0")));
}));
Object.assign(window, {
  Sidebar
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/Sidebar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/learner-platform/TopBar.jsx
try { (() => {
const TopBar = ({
  active = "courses",
  onNav,
  learnerName = "Amara Okafor",
  learnerInitials = "AO"
}) => {
  const items = [{
    id: "courses",
    label: "My courses"
  }, {
    id: "catalog",
    label: "Catalogue"
  }, {
    id: "records",
    label: "Records"
  }, {
    id: "support",
    label: "Support"
  }];
  return /*#__PURE__*/React.createElement("header", {
    className: "fc-topbar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "left"
  }, /*#__PURE__*/React.createElement("div", {
    className: "logo"
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-color.png",
    alt: "First Class"
  }), /*#__PURE__*/React.createElement("span", null, "First Class")), /*#__PURE__*/React.createElement("nav", {
    className: "fc-nav"
  }, items.map(it => /*#__PURE__*/React.createElement("a", {
    key: it.id,
    href: "#",
    className: active === it.id ? "active" : "",
    onClick: e => {
      e.preventDefault();
      onNav?.(it.id);
    }
  }, it.label)))), /*#__PURE__*/React.createElement("div", {
    className: "right"
  }, /*#__PURE__*/React.createElement("button", {
    className: "fc-btn fc-btn-ghost",
    "aria-label": "Notifications",
    style: {
      padding: 8
    }
  }, /*#__PURE__*/React.createElement("i", {
    className: "ph ph-bell",
    style: {
      fontSize: 20
    }
  })), /*#__PURE__*/React.createElement("div", {
    className: "fc-avatar",
    title: learnerName
  }, learnerInitials)));
};
Object.assign(window, {
  TopBar
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/learner-platform/TopBar.jsx", error: String((e && e.message) || e) }); }

})();
