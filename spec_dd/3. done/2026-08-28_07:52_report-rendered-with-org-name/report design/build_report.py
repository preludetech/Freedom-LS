#!/usr/bin/env python3
"""
Co-branded cohort progress report (sample/template PDF). The training
partner (BRAND) is the primary brand; First Class appears as "Powered by".

Architecture notes
------------------
* THEME is the only place colour values exist. The stylesheet references
  $tokens which are substituted at build time — mirroring the production
  rule that report templates never name colours; a downstream theme
  (AppSettings) supplies them.
* AT_RISK_RULES is a registry of named rule objects. Each rule carries an
  id, a human label, a severity token, threshold params, and a function
  over already-gathered report data. The registry is evaluated ONCE per
  learner; both the at-a-glance page and the per-learner detail sections
  render from that single evaluation.
* Section 3 (cohort confusions) is derived from first attempts only;
  Section 2 personal rollups use all attempts. Both are computed from the
  same attempt records, so the views cannot disagree.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from string import Template
from typing import Callable, Optional

from weasyprint import HTML

# Fonts: place brand TTFs in ./fonts — Outfit-600/700, DMSans-400/500/600/700,
# IBMPlexMono-Regular/Medium/SemiBold (static weights instanced from the Google
# Fonts variable files with `fonttools varLib.instancer`), plus system DejaVu
# Sans as the glyph fallback for status marks (✓ → ▲ ✗ ○).
BASE = Path(__file__).resolve().parent
OUT = BASE / "out"
OUT.mkdir(exist_ok=True)

# ===========================================================================
# THEME LAYER — the only place colour values live (downstream-overridable).
# Semantic role tokens per the brand colour spec; on-*-light foregrounds are
# theme-supplied pairings for text set on the light tints.
# ===========================================================================
THEME = {
    # brand chrome
    "primary":        "#283593",  # deep indigo
    "accent":         "#00CEC9",  # electric teal
    "ink":            "#1A1A2E",  # cockpit dark
    "heading":        "#1A202C",
    "paper":          "#FFFFFF",
    "surface":        "#F8F9FC",
    "surfaceAlt":     "#EDF2F7",
    "border":         "#E2E8F0",
    "borderStrong":   "#CBD5E0",
    "mutedFg":        "#718096",
    "mutedFgStrong":  "#4A5568",
    # semantic roles
    "success":        "#38A169",
    "successLight":   "#F0FFF4",
    "onSuccess":      "#FFFFFF",
    "onSuccessLight": "#276749",
    "warning":        "#D69E2E",
    "warningLight":   "#FFFFF0",
    "onWarning":      "#1A1A2E",
    "onWarningLight": "#975A16",
    "error":          "#E53E3E",
    "errorLight":     "#FFF5F5",
    "onError":        "#FFFFFF",
    "onErrorLight":   "#9B2C2C",
    "info":           "#3182CE",
    "infoLight":      "#EBF8FF",
    "onInfo":         "#FFFFFF",
    "onInfoLight":    "#2C5282",
    "muted":          "#EDF2F7",
    "onMuted":        "#718096",
}

# Colour is never the only signal: every status carries a glyph + number.
GLYPH = {"success": "✓", "info": "→", "warning": "▲", "error": "✗", "muted": "○"}

# ===========================================================================
# REPORT PARAMETERS (would arrive via per-app settings in production)
# ===========================================================================
GENERATED = date(2026, 8, 14)
GENERATED_STR = "Friday 14 August 2026 · 09:42 SAST (UTC+02:00)"
GENERATED_BY = "Nomsa Dube — Programme coordinator, First Class"
COHORT_NAME = "RPC 2026-03 · Johannesburg intake"
COHORT_CODE = "RPC 2026-03"
# Co-branding (per-deployment, like THEME). The partner — the school or
# organisation the cohort belongs to — is the primary brand throughout;
# the platform appears only as the "Powered by" mark.
BRAND = {
    "partner_name": "AeroVista Flight Academy",
    "partner_descriptor": "SACAA ATO 0231",   # accreditation line under the name
    "powered_by": "First Class",
}
PASS_MARK = 75          # % — rule parameter, not a constant baked into a rule
INACTIVE_DAYS = 14      # N — placeholder pending spec sign-off
CONFUSION_CAP = 4       # worst-N questions shown per quiz (cap is disclosed)
SMALL_N = 30            # below this, show counts rather than percentages

# ===========================================================================
# COURSES, QUIZZES, QUESTION BANK
# ===========================================================================
RPC_ITEMS = [
    "1.1 Welcome and how the course works",
    "1.2 The SACAA and Part 101",
    "1.3 Categories of RPAS operation",
    "1.4 Operating limitations and approvals",
    "2.1 Weather for remote pilots",
    "2.2 Wind, gusts, and turbulence",
    "2.3 Cloud, visibility, and fog",
    "2.4 Reading METAR and TAF",
    "3.1 Principles of multirotor flight",
    "3.2 Lift, thrust, and power",
    "3.3 Stability and control",
    "3.4 Performance and loading",
    "4.1 Airspace classes for remote pilots",
    "4.2 Controlled, restricted, and prohibited areas",
    "4.3 Reading the VFR chart",
    "4.4 NOTAMs and pre-flight briefing",
    "5.1 Human factors and airmanship",
    "5.2 Crew resource management",
    "5.3 Batteries and energy management",
    "5.4 Incident and accident reporting",
    "6.1 Pre-flight checks and checklists",
    "6.2 Site survey and risk assessment",
    "6.3 Emergency procedures",
    "6.4 Mock exam briefing and next steps",
]
RADIO_ITEMS = [
    "R1 Why radio matters",
    "R2 The phonetic alphabet",
    "R3 Numbers and callsigns",
    "R4 Standard words and phrases",
    "R5 Readability and radio checks",
    "R6 Aerodrome broadcasts",
    "R7 Distress and urgency",
    "R8 Listening exercises",
    "R9 Practice circuit calls",
    "R10 Mock radio exam briefing",
]

COURSES = [
    {"id": "rpc",   "title": "RPC theory (multirotor)", "items": RPC_ITEMS,
     "quizzes": ["AL", "MET", "POF", "NAV"]},
    {"id": "radio", "title": "Radio licence primer",    "items": RADIO_ITEMS,
     "quizzes": ["PHR", "PROC"]},
]

# Quiz column order follows the quiz's position in the course, per spec.
QUIZZES = {
    "AL":   {"title": "Air law",                "total": 12, "course": "rpc"},
    "MET":  {"title": "Meteorology",            "total": 10, "course": "rpc"},
    "POF":  {"title": "Principles of flight",   "total": 10, "course": "rpc"},
    "NAV":  {"title": "Airspace and navigation", "total": 8,  "course": "rpc"},
    "PHR":  {"title": "Radio phraseology",      "total": 8,  "course": "radio"},
    "PROC": {"title": "Radio procedures",       "total": 8,  "course": "radio"},
}

# Only questions that appear in wrong-answer data need full text/options.
Q = {
    ("AL", 2):  {"text": "Maximum height above the surface for a standard RPAS operation",
                 "opts": {"A": "200 ft", "B": "400 ft", "C": "500 ft", "D": "1 000 ft"}, "correct": "B"},
    ("AL", 5):  {"text": "Minimum lateral distance from a person or structure not under the pilot's control",
                 "opts": {"A": "30 m", "B": "50 m", "C": "100 m", "D": "150 m"}, "correct": "B"},
    ("AL", 7):  {"text": "Distance from an aerodrome within which RPAS operations require approval",
                 "opts": {"A": "5 km", "B": "8 km", "C": "10 km", "D": "15 km"}, "correct": "C"},
    ("AL", 9):  {"text": "Final responsibility for the safe outcome of an RPAS flight rests with",
                 "opts": {"A": "The observer", "B": "The pilot in command", "C": "The ATO",
                          "D": "The operator's safety officer"}, "correct": "B"},
    ("AL", 11): {"text": "RPAS operations at night are permitted",
                 "opts": {"A": "Never", "B": "With the required approval in the operator's OpsSpec",
                          "C": "Whenever VLOS can be maintained", "D": "Only with anti-collision lighting fitted"},
                 "correct": "B"},
    ("MET", 1): {"text": "Conditions that most favour the formation of radiation fog",
                 "opts": {"A": "Clear skies and light wind", "B": "Overcast skies and strong wind",
                          "C": "Warm, gusty afternoons", "D": "The passage of a cold front"}, "correct": "A"},
    ("MET", 3): {"text": "Density altitude increases when",
                 "opts": {"A": "Air temperature rises", "B": "Air temperature falls",
                          "C": "Surface pressure rises", "D": "Humidity falls"}, "correct": "A"},
    ("MET", 6): {"text": "Wind direction in a METAR is given relative to",
                 "opts": {"A": "True north", "B": "Magnetic north", "C": "The runway heading",
                          "D": "Grid north"}, "correct": "A"},
    ("MET", 8): {"text": "Cloud base heights in a METAR are reported",
                 "opts": {"A": "Above ground level", "B": "Above mean sea level", "C": "As flight levels",
                          "D": "Above the highest obstacle"}, "correct": "A"},
    ("POF", 2): {"text": "Increasing the angle of attack beyond the critical angle causes",
                 "opts": {"A": "Lift to keep increasing", "B": "Airflow to separate and the surface to stall",
                          "C": "Drag to fall sharply", "D": "The lift-to-drag ratio to peak"}, "correct": "B"},
    ("POF", 4): {"text": "In a steady hover, total rotor thrust is",
                 "opts": {"A": "Greater than the aircraft's weight", "B": "Equal to the aircraft's weight",
                          "C": "Less than the aircraft's weight", "D": "Independent of the aircraft's weight"},
                 "correct": "B"},
    ("POF", 7): {"text": "Adding payload to a multirotor in the hover",
                 "opts": {"A": "Reduces the power required", "B": "Has no effect on the power required",
                          "C": "Increases the power required", "D": "Only affects endurance, not power"},
                 "correct": "C"},
    ("NAV", 3): {"text": "With QNH set, the altimeter indicates",
                 "opts": {"A": "Altitude above mean sea level", "B": "Height above the aerodrome",
                          "C": "Flight level", "D": "Height above the ground"}, "correct": "A"},
    ("NAV", 6): {"text": "On a South African chart, an area prefixed FAR is",
                 "opts": {"A": "A danger area", "B": "A prohibited area", "C": "A restricted area",
                          "D": "A control area"}, "correct": "C"},
    ("NAV", 7): {"text": "A CTR is best described as",
                 "opts": {"A": "Uncontrolled airspace around any airfield",
                          "B": "Controlled airspace around an aerodrome, from the surface up",
                          "C": "A military flying corridor", "D": "Airspace above FL195"}, "correct": "B"},
    ("PHR", 4): {"text": "The word WILCO means",
                 "opts": {"A": "Message received", "B": "I understand and will comply", "C": "Say again",
                          "D": "Cleared as requested"}, "correct": "B"},
    ("PHR", 5): {"text": "Readability is reported on a scale of",
                 "opts": {"A": "1 to 3", "B": "1 to 5", "C": "1 to 9", "D": "A to E"}, "correct": "B"},
    ("PROC", 1): {"text": "The VHF emergency frequency is",
                  "opts": {"A": "118.10 MHz", "B": "121.50 MHz", "C": "124.80 MHz", "D": "126.70 MHz"},
                  "correct": "B"},
    ("PROC", 5): {"text": "Before transmitting on a frequency, first",
                  "opts": {"A": "Increase the squelch", "B": "Transmit a radio check",
                           "C": "Listen out to confirm the frequency is clear",
                           "D": "Announce your callsign twice"}, "correct": "C"},
}

# ===========================================================================
# SAMPLE LEARNER DATA
# attempts: quiz -> list of (date, {question_no: incorrect_letter_chosen})
# Scores are computed from the wrong map, so numbers can never disagree.
# ===========================================================================
def d(m, day): return date(2026, m, day)

STUDENTS = [
    dict(id="abrahams", first="Fatima", last="Abrahams", sid="FC-26-0403", start=d(5, 18),
         done={"rpc": 17, "radio": 7}, ends={"rpc": d(8, 8), "radio": d(8, 10)},
         attempts={
             "AL":  [(d(6, 12), {7: "B", 2: "A"})],
             "MET": [(d(7, 2), {1: "B", 6: "B", 8: "B"}), (d(7, 9), {6: "B"})],
             "POF": [(d(7, 24), {2: "C"})],
             "PHR": [(d(7, 18), {4: "A"})],
         }),
    dict(id="bhengu", first="Sipho", last="Bhengu", sid="FC-26-0388", start=d(5, 18),
         done={"rpc": 20, "radio": 8}, ends={"rpc": d(8, 9), "radio": d(8, 12)},
         attempts={
             "AL":  [(d(6, 8), {2: "D"})],
             "MET": [(d(6, 28), {})],
             "POF": [(d(7, 14), {4: "B", 7: "A"})],
             "NAV": [(d(8, 2), {6: "A"})],
             "PHR": [(d(7, 20), {})],
             "PROC": [(d(8, 8), {5: "B"})],
         }),
    dict(id="dlamini", first="Amara", last="Dlamini", sid="FC-26-0391", start=d(5, 18),
         done={"rpc": 24, "radio": 10}, ends={"rpc": d(8, 5), "radio": d(8, 8)},
         attempts={
             "AL":  [(d(6, 5), {7: "A"})],
             "MET": [(d(6, 24), {})],
             "POF": [(d(7, 10), {})],
             "NAV": [(d(7, 26), {3: "B"})],
             "PHR": [(d(7, 15), {})],
             "PROC": [(d(8, 4), {1: "C"})],
         }),
    dict(id="khumalo", first="Naledi", last="Khumalo", sid="FC-26-0407", start=d(5, 18),
         done={"rpc": 0, "radio": 0}, ends={}, attempts={}),
    dict(id="mokoena", first="Thandi", last="Mokoena", sid="FC-26-0395", start=d(5, 25),
         done={"rpc": 11, "radio": 3}, ends={"rpc": d(7, 28), "radio": d(7, 22)},
         attempts={
             "AL": [(d(7, 10), {2: "D", 5: "A", 7: "B", 9: "A", 11: "C"}),
                    (d(7, 18), {2: "D", 5: "C", 7: "B", 9: "A"}),
                    (d(7, 26), {2: "A", 5: "A", 7: "D", 9: "A", 11: "C"})],
         }),
    dict(id="naidoo", first="Rajesh", last="Naidoo", sid="FC-26-0399", start=d(6, 1),
         done={"rpc": 15, "radio": 6}, ends={"rpc": d(8, 9), "radio": d(8, 11)},
         attempts={
             "AL":  [(d(6, 20), {2: "A", 7: "D"})],
             "MET": [(d(7, 12), {6: "B", 8: "C"})],
             "POF": [(d(7, 28), {2: "C", 4: "B", 7: "A"}), (d(8, 3), {4: "B"})],
             "PHR": [(d(8, 1), {5: "C"})],
         }),
    dict(id="okafor", first="Daniel", last="Okafor", sid="FC-26-0384", start=d(5, 18),
         done={"rpc": 24, "radio": 10}, ends={"rpc": d(8, 2), "radio": d(8, 9)},
         attempts={
             "AL":  [(d(6, 3), {5: "C"})],
             "MET": [(d(6, 20), {8: "B"})],
             "POF": [(d(7, 6), {})],
             "NAV": [(d(7, 22), {6: "B", 7: "A"})],
             "PHR": [(d(7, 25), {})],
             "PROC": [(d(8, 6), {})],
         }),
    dict(id="sithole", first="Lerato", last="Sithole", sid="FC-26-0411", start=d(6, 15),
         done={"rpc": 9, "radio": 2}, ends={"rpc": d(8, 4), "radio": d(8, 6)},
         attempts={
             "AL":  [(d(7, 6), {2: "D", 7: "B", 9: "C"})],
             "MET": [(d(7, 30), {1: "B", 3: "C", 6: "B"}), (d(8, 6), {1: "C", 3: "B", 6: "B", 8: "B"})],
         }),
    dict(id="vandermerwe", first="Pieter", last="van der Merwe", sid="FC-26-0415", start=d(7, 6),
         done={"rpc": 4, "radio": 0}, ends={"rpc": d(7, 14)},
         attempts={
             "AL": [(d(7, 20), {2: "D", 7: "B"})],
         }),
]

# ===========================================================================
# HELPERS
# ===========================================================================
def esc(s: str) -> str:
    return _html.escape(str(s), quote=True)

def fmt(dt: Optional[date], year=True) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d %b %Y" if year else "%d %b").lstrip("0")

def spread_dates(start: date, end: date, k: int) -> list[date]:
    """Evenly space k completion dates from start to end (inclusive)."""
    if k <= 0:
        return []
    if k == 1:
        return [end]
    span = (end - start).days
    return [start + timedelta(days=round(i * span / (k - 1))) for i in range(k)]

def quiz_score(code: str, wrong: dict) -> int:
    total = QUIZZES[code]["total"]
    return round((total - len(wrong)) / total * 100)

def comp_status(pct_done: int) -> tuple[str, str]:
    if pct_done >= 100: return "success", "Complete"
    if pct_done >= 50:  return "info", "In progress"
    if pct_done >= 20:  return "warning", "Behind"
    if pct_done >= 1:   return "error", "Significantly behind"
    return "muted", "Not started"

def score_status(score: int) -> str:
    if score >= PASS_MARK: return "success"
    if score >= 60:        return "warning"
    return "error"

def gspan(status: str) -> str:
    return f'<span class="g">{GLYPH[status]}</span>'

# ===========================================================================
# DERIVED DATA (one pass — no per-learner re-querying downstream)
# ===========================================================================
COURSE_BY_ID = {c["id"]: c for c in COURSES}

for s in STUDENTS:
    s["item_dates"] = {}
    for c in COURSES:
        k = s["done"].get(c["id"], 0)
        if k:
            start = s["start"] + (timedelta(days=14) if c["id"] == "radio" else timedelta(0))
            s["item_dates"][c["id"]] = spread_dates(start, s["ends"][c["id"]], k)
    # scored attempts, latest per quiz
    s["scored"] = {}
    for code, atts in s["attempts"].items():
        s["scored"][code] = [(dt, wrong, quiz_score(code, wrong)) for dt, wrong in atts]
    s["latest"] = {code: recs[-1] for code, recs in s["scored"].items()}
    # activity
    all_dates = [dt for ds in s["item_dates"].values() for dt in ds]
    all_dates += [dt for recs in s["scored"].values() for dt, _, _ in recs]
    s["last_active"] = max(all_dates) if all_dates else None
    s["total_done"] = sum(s["done"].values())
    s["total_items"] = sum(len(c["items"]) for c in COURSES)
    s["overall_pct"] = round(s["total_done"] / s["total_items"] * 100)

STUDENTS.sort(key=lambda s: (s["last"].lower(), s["first"].lower()))

# ===========================================================================
# AT-RISK RULE REGISTRY
# Named rule objects over already-gathered data. Adding, removing, or
# reordering a rule is a one-line change to AT_RISK_RULES; in production the
# list is supplied via per-app settings (AppSettings/declared_settings) so
# downstream projects can override it without forking.
# ===========================================================================
@dataclass
class AtRiskRule:
    id: str
    label: str
    severity: str                      # semantic role token
    fn: Callable[[dict], Optional[str]]
    params: dict = field(default_factory=dict)

    def evaluate(self, student: dict) -> Optional[str]:
        return self.fn(student, **self.params)

def rule_no_activity(s: dict) -> Optional[str]:
    if s["total_done"] == 0 and not s["scored"]:
        return (f"No recorded activity in any enrolled course since enrolment "
                f"on {fmt(s['start'])}.")
    return None

def rule_failed_latest(s: dict, pass_mark: int) -> Optional[str]:
    failed = [(code, rec[2]) for code, rec in s["latest"].items() if rec[2] < pass_mark]
    if not failed:
        return None
    parts = [f"{QUIZZES[c]['title']} ({c}) — {sc}%" for c, sc in failed]
    return (f"Failed the latest attempt at {'; '.join(parts)} "
            f"against a {pass_mark}% pass mark.")

def rule_inactive(s: dict, days: int) -> Optional[str]:
    if s["last_active"] and (GENERATED - s["last_active"]).days >= days:
        gap = (GENERATED - s["last_active"]).days
        return f"No activity for {gap} days (last seen {fmt(s['last_active'])})."
    return None

AT_RISK_RULES = [
    AtRiskRule("no-activity", "No activity", "error", rule_no_activity),
    AtRiskRule("failed-latest-quiz", "Failed latest quiz attempt", "error",
               rule_failed_latest, {"pass_mark": PASS_MARK}),
    AtRiskRule("inactive", f"Inactive {INACTIVE_DAYS}+ days", "warning",
               rule_inactive, {"days": INACTIVE_DAYS}),
]

# Evaluate ONCE; both the at-a-glance page and the detail sections read this.
for s in STUDENTS:
    s["flags"] = [(r, reason) for r in AT_RISK_RULES if (reason := r.evaluate(s))]

FLAGGED = [s for s in STUDENTS if s["flags"]]

# Cohort confusions — first attempts only (methodology: first-attempt rule).
CONFUSIONS = {}   # quiz -> dict(qno -> {"count": n, "opts": {letter: n}})
ATTEMPTED_BY = {} # quiz -> n learners with >= 1 attempt
for code in QUIZZES:
    per_q: dict[int, dict] = {}
    n_attempted = 0
    for s in STUDENTS:
        recs = s["scored"].get(code)
        if not recs:
            continue
        n_attempted += 1
        first_wrong = recs[0][1]
        for qno, letter in first_wrong.items():
            slot = per_q.setdefault(qno, {"count": 0, "opts": {}})
            slot["count"] += 1
            slot["opts"][letter] = slot["opts"].get(letter, 0) + 1
    CONFUSIONS[code] = per_q
    ATTEMPTED_BY[code] = n_attempted

# Cohort headline numbers.
COHORT_N = len(STUDENTS)
MEDIAN_PCT = sorted(s["overall_pct"] for s in STUDENTS)[COHORT_N // 2]
NOT_STARTED = sum(1 for s in STUDENTS if s["total_done"] == 0 and not s["scored"])
COMPLETE_ALL = sum(1 for s in STUDENTS if s["total_done"] == s["total_items"])

# ===========================================================================
# HTML BUILDERS
# ===========================================================================
def chip(status: str, text: str, solid=False) -> str:
    kind = "chip-solid" if solid else "chip"
    return f'<span class="{kind} st-{status}">{gspan(status)}&nbsp;{esc(text)}</span>'

def badge(rule: AtRiskRule) -> str:
    return f'<span class="badge bd-{rule.severity}">{esc(rule.label)}</span>'

def cover() -> str:
    course_lines = "".join(
        f'<li>{esc(c["title"])} <span class="mut">— {len(c["items"])} items, '
        f'{len(c["quizzes"])} quizzes</span></li>' for c in COURSES)
    return f"""
<section class="cover">
  <div class="cover-in">
    <div class="brandrow">
      <div><div class="wordmark">{esc(BRAND["partner_name"])}</div>
      <div class="tagline mono">{esc(BRAND["partner_descriptor"])}</div></div>
      <div class="accentline"></div>
    </div>
    <div class="cover-mid">
      <div class="cover-title">Cohort progress report</div>
      <div class="cover-cohort">{esc(COHORT_NAME)}</div>
      <div class="cover-card">
        <div class="overline">Courses covered</div>
        <ul class="courselist">{course_lines}</ul>
      </div>
      <div class="cover-meta mono">
        <div><span class="k">Generated</span>{esc(GENERATED_STR)}</div>
        <div><span class="k">Generated by</span>{esc(GENERATED_BY)}</div>
        <div><span class="k">Cohort size</span>{COHORT_N} learners</div>
      </div>
      <p class="caveat">Figures reflect data as of generation time. Activity recorded
      after 09:42 SAST on 14 August 2026 does not appear in this report.</p>
    </div>
  </div>
  <div class="cover-band">
    <span class="band-powered"><span class="pby">Powered by</span><span
      class="band-brand">{esc(BRAND["powered_by"])}</span></span>
    <span class="band-note">Learner progress · {esc(COHORT_CODE)}</span>
  </div>
</section>"""

def glance() -> str:
    stats = "".join(f"""
      <div class="stat"><div class="n">{v}</div><div class="l">{esc(l)}</div></div>"""
        for v, l in [
            (COHORT_N, "Learners in cohort"),
            (f"{MEDIAN_PCT}%", "Median completion"),
            (NOT_STARTED, "Not started"),
            (COMPLETE_ALL, "Completed everything"),
        ])
    rows = []
    for s in FLAGGED:
        reasons = "".join(
            f'<div class="reason">{badge(r)}<span>{esc(reason)}</span></div>'
            for r, reason in s["flags"])
        rows.append(f"""
        <div class="attn-row">
          <div class="attn-main">
            <div class="attn-name">{esc(s["last"])}, {esc(s["first"])}</div>
            {reasons}
          </div>
          <a class="pref" href="#stu-{s["id"]}">p.&#8202;</a>
        </div>""")
    return f"""
<section class="portrait" id="glance">
  <div class="kicker">Cohort overview</div>
  <h1>Cohort at a glance</h1>
  <p class="lede">Headline numbers for {esc(COHORT_NAME)}, followed by the learners the
  at-risk rules flagged at generation time. Median completion is measured across all
  enrolled course items.</p>
  <div class="stats">{stats}</div>
  <div class="attn-head">
    <h2>Learners needing attention</h2>
    <span class="chip-solid st-error"><span class="mono">{len(FLAGGED)} of {COHORT_N}</span>&nbsp;flagged</span>
  </div>
  <div class="attn">{''.join(rows)}</div>
  <p class="foot">All flagged learners fit on this page. When more qualify than fit, the
  count above stays complete and the remainder carry their flags in section 2. The active
  rules and their thresholds are listed under Contents and definitions; rule sets are
  configured per deployment.</p>
</section>"""

def toc_row(href: str, label: str, level=1, cls="") -> str:
    return (f'<a class="toc-row lv{level} {cls}" href="{href}">'
            f'<span class="t">{label}</span><span class="fill"></span></a>')

def contents() -> str:
    rows = [toc_row("#glance", "Cohort at a glance"),
            toc_row("#contents", "Contents and definitions"),
            toc_row("#sec-summary", "1&ensp;·&ensp;Summary of learner progress")]
    rows += [toc_row(f"#course-{c['id']}", esc(c["title"]), 2) for c in COURSES]
    rows.append(toc_row("#sec-details", "2&ensp;·&ensp;Details per learner"))
    rows += [toc_row(f"#stu-{s['id']}", f'{esc(s["last"])}, {esc(s["first"])}', 2)
             for s in STUDENTS]
    rows.append(toc_row("#sec-confusions", "3&ensp;·&ensp;Quiz confusions across the cohort"))
    rows += [toc_row(f"#quiz-{code}", f'{esc(QUIZZES[code]["title"])} ({code})', 2)
             for code in QUIZZES]

    legend_chips = "".join(
        f'<span class="chip lg st-{st}">{gspan(st)}&nbsp;{esc(role)} — {esc(meaning)}</span>'
        for st, role, meaning in [
            ("success", "success", "complete, or a score at or above the pass mark"),
            ("info", "info", "in progress (50%+ of items)"),
            ("warning", "warning", "behind (20–49%), or a marginal fail (60–74%)"),
            ("error", "error", "significantly behind (1–19%), or a clear fail (below 60%)"),
            ("muted", "muted", "not started, or no attempt"),
        ])
    rules_li = "".join(
        f'<li><strong>{esc(r.label)}</strong> <span class="mono mut">[{r.id}]</span> — '
        + esc({
            "no-activity": "0% complete with no quiz attempts recorded.",
            "failed-latest-quiz": f"latest submitted attempt at any quiz scored below the {PASS_MARK}% pass mark.",
            "inactive": f"no item completion or quiz submission in the last {INACTIVE_DAYS} days (N = {INACTIVE_DAYS} is a working value pending spec sign-off, and is set per deployment).",
        }[r.id]) + "</li>"
        for r in AT_RISK_RULES)
    return f"""
<section class="portrait" id="contents">
  <div class="kicker">How to read this report</div>
  <h1>Contents and definitions</h1>
  <div class="toc">{''.join(rows)}</div>

  <h2 class="defs-h">Definitions and method</h2>
  <div class="defs">
    <p><strong>Complete.</strong> A course counts as complete when every course item is
    marked complete. “Completed everything” on the at-a-glance page means every enrolled
    course is complete.</p>
    <p><strong>Quiz score.</strong> The score shown against a learner is always their
    <em>latest</em> submitted attempt, not their best.</p>
    <p><strong>Attempt.</strong> A submitted quiz sitting. Sittings opened but not
    submitted are not counted.</p>
    <p><strong>Cohort analysis.</strong> Section 3 counts <em>first</em> attempts only, so
    retakes do not double-count a question's difficulty. Personal rollups in section 2
    cover all of a learner's attempts.</p>
    <p><strong>Activity.</strong> Completing a course item or submitting a quiz attempt.</p>
    <p><strong>At-risk rules active in this report.</strong></p>
    <ul class="rules">{rules_li}</ul>
    <p><strong>Small cohorts.</strong> Where a group is smaller than {SMALL_N}, this report
    shows plain counts rather than percentages — a cohort of nine cannot support the
    precision a percentage implies.</p>
    <p><strong>Colour and print.</strong> Status is always shown as colour, a glyph, and a
    number together, so the report stays readable in greyscale print.</p>
  </div>
  <div class="legendstrip"><span class="overline">RAG legend</span> — the same tints
  and glyphs used in every status cell:<br/>{legend_chips}</div>
</section>"""

def summary_course_table(c: dict) -> str:
    codes = c["quizzes"]
    legend = " · ".join(f"{code} = {QUIZZES[code]['title']}" for code in codes)
    group_th = "".join(f'<th colspan="2" class="qgroup c">{code}</th>' for code in codes)
    sub_th = "".join('<th class="c sub qgroup">Score</th><th class="c sub">Att</th>'
                     for _ in codes)
    body = []
    for s in STUDENTS:
        done = s["done"].get(c["id"], 0)
        total = len(c["items"])
        pctv = round(done / total * 100)
        st, lab = comp_status(pctv)
        dates = s["item_dates"].get(c["id"], [])
        last_item = c["items"][done - 1] if done else None
        cells = [
            f'<td class="name">{esc(s["last"])}, {esc(s["first"])}</td>',
            (f'<td class="st-{st}"><div class="cmp">{gspan(st)}'
             f'<span class="mono pctv">{pctv}%</span>'
             f'<span class="mono frac">{done}/{total}</span></div>'
             f'<div class="bar"><i style="width:{pctv}%"></i></div></td>'),
            f'<td class="li">{esc(last_item) if last_item else "—"}</td>',
            f'<td class="mono when">{fmt(dates[-1], year=False) if dates else "—"}</td>',
        ]
        for code in codes:
            rec = s["latest"].get(code)
            if rec:
                score = rec[2]
                sst = score_status(score)
                cells.append(f'<td class="c qgroup st-{sst}">{gspan(sst)}&#8202;'
                             f'<span class="mono">{score}</span></td>')
                cells.append(f'<td class="c mono att">×{len(s["scored"][code])}</td>')
            else:
                cells.append(f'<td class="c qgroup st-muted">{gspan("muted")}</td>')
                cells.append('<td class="c mono att">—</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    qcols = "".join('<col class="w-qs"/><col class="w-qa"/>' for _ in codes)
    return f"""
  <div class="coursetbl" id="course-{c["id"]}">
    <h2>{esc(c["title"])}</h2>
    <p class="tbl-legend">{esc(legend)}. Score = latest attempt · ×n = attempts ·
    quiz columns follow course order · all dates 2026.</p>
    <table class="summary">
      <colgroup><col class="w-name"/><col class="w-cmp"/><col class="w-li"/><col class="w-when"/>{qcols}</colgroup>
      <thead>
        <tr><th rowspan="2">Learner</th><th rowspan="2">Completion</th>
            <th rowspan="2">Last item completed</th><th rowspan="2">When</th>{group_th}</tr>
        <tr>{sub_th}</tr>
      </thead>
      <tbody>{''.join(body)}</tbody>
    </table>
  </div>"""

def summary() -> str:
    return f"""
<section class="landscape" id="sec-summary">
  <div class="kicker">Section 1</div>
  <h1>Summary of learner progress</h1>
  <p class="lede">One table per course. Column headers repeat on every page a table spans;
  where a course carries more quizzes than fit, the table splits rather than shrinking
  the type.</p>
  {''.join(summary_course_table(c) for c in COURSES)}
</section>"""

def wrong_rollup(s: dict, code: str) -> str:
    """Per-question rollup across ALL attempts for one learner and quiz."""
    agg: dict[int, dict] = {}
    for _, wrong, _ in s["scored"][code]:
        for qno, letter in wrong.items():
            slot = agg.setdefault(qno, {"count": 0, "opts": {}})
            slot["count"] += 1
            slot["opts"][letter] = slot["opts"].get(letter, 0) + 1
    if not agg:
        return ('<p class="allclear">' + gspan("success") +
                ' No incorrect answers across attempts.</p>')
    rows = []
    for qno in sorted(agg):
        q = Q[(code, qno)]
        slot = agg[qno]
        picked = " · ".join(
            f'{L} — {esc(q["opts"][L])}' + (f' <span class="mono">×{n}</span>' if n > 1 else "")
            for L, n in sorted(slot["opts"].items()))
        rows.append(f"""
        <tr><td class="mono qn">Q{qno}</td><td>{esc(q["text"])}</td>
        <td class="c mono wr">×{slot["count"]}</td><td class="picked">{picked}</td></tr>""")
    return f"""
    <table class="rollup">
      <thead><tr><th class="qn">Q</th><th>Question</th><th class="c wr">Wrong</th>
      <th>Incorrect options picked</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""

def student_detail(s: dict, first: bool) -> str:
    # Flags panel — rendered from the SAME registry evaluation as the glance page.
    if s["flags"]:
        top_sev = "error" if any(r.severity == "error" for r, _ in s["flags"]) else "warning"
        frows = "".join(f'<div class="reason">{badge(r)}<span>{esc(reason)}</span></div>'
                        for r, reason in s["flags"])
        flags_html = f'<div class="flags sev-{top_sev}">{frows}</div>'
    else:
        flags_html = ('<p class="noflags">No flags — no at-risk rule tripped at '
                      'generation time.</p>')

    if s["total_done"] == 0 and not s["scored"]:
        body = '<p class="noact">No activity recorded.</p>'
        course_blocks = []
        for c in COURSES:
            n_items = len(c["items"])
            course_blocks.append(
                f'<div class="courseblk"><h3>{esc(c["title"])} '
                f'{chip("muted", f"Not started · 0/{n_items} items")}</h3></div>')
        body += "".join(course_blocks)
    else:
        blocks = []
        for c in COURSES:
            done = s["done"].get(c["id"], 0)
            total = len(c["items"])
            pctv = round(done / total * 100)
            st, lab = comp_status(pctv)
            head = (f'<h3>{esc(c["title"])} '
                    f'{chip(st, f"{lab} · {done}/{total} items · {pctv}%")}</h3>')
            # items completed, two-up table
            if done:
                dates = s["item_dates"][c["id"]]
                pairs = []
                half = (done + 1) // 2
                for i in range(half):
                    l_item = f'<td class="it">{esc(c["items"][i])}</td><td class="mono dt">{fmt(dates[i])}</td>'
                    j = i + half
                    if j < done:
                        r_item = f'<td class="it">{esc(c["items"][j])}</td><td class="mono dt">{fmt(dates[j])}</td>'
                    else:
                        r_item = '<td class="it"></td><td class="dt"></td>'
                    pairs.append(f"<tr>{l_item}{r_item}</tr>")
                items_html = (f'<div class="subhead">Items completed</div>'
                              f'<table class="items"><tbody>{"".join(pairs)}</tbody></table>')
            else:
                items_html = ('<div class="subhead">Items completed</div>'
                              '<p class="none">No items completed.</p>')
            # quiz attempts
            atts = []
            for code in c["quizzes"]:
                for i, (dt, wrong, score) in enumerate(s["scored"].get(code, []), 1):
                    sst = score_status(score)
                    atts.append(f"""
                    <tr><td>{esc(QUIZZES[code]["title"])} <span class="mono mut">({code})</span></td>
                    <td class="c mono">{i}</td><td class="mono">{fmt(dt)}</td>
                    <td class="c st-{sst}">{gspan(sst)}&#8202;<span class="mono">{score}%</span></td></tr>""")
            if atts:
                att_html = (f'<div class="subhead">Quiz attempts <span class="normal">'
                            f'(score = that attempt; pass mark {PASS_MARK}%)</span></div>'
                            f'<table class="attempts"><thead><tr><th>Quiz</th>'
                            f'<th class="c">Attempt</th><th>Date</th><th class="c">Score</th></tr></thead>'
                            f'<tbody>{"".join(atts)}</tbody></table>')
            else:
                att_html = ('<div class="subhead">Quiz attempts</div>'
                            '<p class="none">No quiz attempts.</p>')
            # wrong-answer rollups per attempted quiz
            roll = []
            for code in c["quizzes"]:
                if s["scored"].get(code):
                    roll.append(f'<div class="subhead">Incorrect answers — '
                                f'{esc(QUIZZES[code]["title"])} ({code}), all attempts</div>'
                                + wrong_rollup(s, code))
            blocks.append(f'<div class="courseblk">{head}{items_html}{att_html}{"".join(roll)}</div>')
        body = "".join(blocks)

    return f"""
<article class="student{' firststu' if first else ''}" id="stu-{s["id"]}">
  <div class="stu-head">
    <h2 class="stu-name">{esc(s["last"])}, {esc(s["first"])}</h2>
    <span class="mono sid">{esc(s["sid"])} · last activity {fmt(s["last_active"])}</span>
  </div>
  {flags_html}
  {body}
</article>"""

def details() -> str:
    arts = "".join(student_detail(s, i == 0) for i, s in enumerate(STUDENTS))
    return f"""
<section class="detail-sec" id="sec-details">
  <div class="kicker">Section 2</div>
  <h1>Details per learner</h1>
  <p class="lede">One section per learner, alphabetical by surname. Flags shown here are
  the same rule results as the at-a-glance page — one evaluation, two views.</p>
  {arts}
</section>"""

def confusions() -> str:
    blocks = []
    for code, meta in QUIZZES.items():
        per_q = CONFUSIONS[code]
        n_att = ATTEMPTED_BY[code]
        if not n_att:
            blocks.append(f'<div class="quizblk" id="quiz-{code}"><h2>{esc(meta["title"])} '
                          f'({code})</h2><p class="none">No attempts recorded.</p></div>')
            continue
        ranked = sorted(per_q.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        shown = ranked[:CONFUSION_CAP]
        total_err_q = len(ranked)
        if total_err_q > CONFUSION_CAP:
            cap_line = (f"Showing the worst {CONFUSION_CAP} of {total_err_q} questions with "
                        f"at least one incorrect first attempt.")
        else:
            cap_line = (f"All {total_err_q} question{'s' if total_err_q != 1 else ''} with at "
                        f"least one incorrect first attempt {'are' if total_err_q != 1 else 'is'} shown.")
        rows = []
        for qno, slot in shown:
            q = Q[(code, qno)]
            wrongopts = " &nbsp;".join(
                f'<span class="chip st-error">{gspan("error")}&nbsp;{L} — {esc(q["opts"][L])}'
                f'&nbsp;<span class="mono">×{n}</span></span>'
                for L, n in sorted(slot["opts"].items(), key=lambda kv: (-kv[1], kv[0])))
            share = slot["count"] / n_att * 100
            rows.append(f"""
            <tr>
              <td class="mono qn">Q{qno}</td>
              <td class="qtext">{esc(q["text"])}<br/>
                <span class="chip st-success">{gspan("success")}&nbsp;{q["correct"]} — {esc(q["opts"][q["correct"]])}</span></td>
              <td class="wopts">{wrongopts}</td>
              <td class="ratio"><span class="mono big">{slot["count"]} of {n_att}</span>
                <div class="bar err"><i style="width:{share:.0f}%"></i></div></td>
            </tr>""")
        blocks.append(f"""
    <div class="quizblk" id="quiz-{code}">
      <h2>{esc(meta["title"])} ({code})</h2>
      <p class="tbl-legend">{cap_line} Attempted by {n_att} of {COHORT_N} learners ·
      first attempts only · counts, not percentages, at this cohort size.</p>
      <table class="conf">
        <colgroup><col class="w-qn"/><col class="w-qt"/><col class="w-wo"/><col class="w-ra"/></colgroup>
        <thead><tr><th class="qn">Q</th><th>Question and correct answer</th>
        <th>Incorrect options chosen</th><th>Got it wrong</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>""")
    return f"""
<section class="portrait" id="sec-confusions">
  <div class="kicker">Section 3</div>
  <h1>Quiz confusions across the cohort</h1>
  <p class="lede caution">Read these tables as prompts, not verdicts. A high error rate can
  mean a hard but fair question as easily as a broken one — and with nine learners, one or
  two answers move a row up or down the ranking. Cross-check a flagged question against the
  course material before changing it.</p>
  {''.join(blocks)}
</section>"""

# ===========================================================================
# STYLESHEET — colours appear only as $tokens; THEME supplies the values.
# ===========================================================================
CSS_SRC = Template(r"""
@font-face { font-family:"Outfit"; font-weight:600; src:url("fonts/Outfit-600.ttf"); }
@font-face { font-family:"Outfit"; font-weight:700; src:url("fonts/Outfit-700.ttf"); }
@font-face { font-family:"DM Sans"; font-weight:400; src:url("fonts/DMSans-400.ttf"); }
@font-face { font-family:"DM Sans"; font-weight:500; src:url("fonts/DMSans-500.ttf"); }
@font-face { font-family:"DM Sans"; font-weight:600; src:url("fonts/DMSans-600.ttf"); }
@font-face { font-family:"DM Sans"; font-weight:700; src:url("fonts/DMSans-700.ttf"); }
@font-face { font-family:"IBM Plex Mono"; font-weight:400; src:url("fonts/IBMPlexMono-Regular.ttf"); }
@font-face { font-family:"IBM Plex Mono"; font-weight:500; src:url("fonts/IBMPlexMono-Medium.ttf"); }
@font-face { font-family:"IBM Plex Mono"; font-weight:600; src:url("fonts/IBMPlexMono-SemiBold.ttf"); }

@page {
  size: A4;
  margin: 16mm 15mm 18mm 15mm;
  @top-right { content: string(sectionTitle); font-family:"DM Sans"; font-weight:600;
    font-size:6.4pt; letter-spacing:.09em; text-transform:uppercase; color:$mutedFg; }
  @bottom-left { content: "$footPartner · $footCohort";
    font-family:"DM Sans"; font-size:7pt; color:$mutedFg; }
  @bottom-center { content: "Powered by $footPoweredBy";
    font-family:"DM Sans"; font-size:7pt; color:$mutedFg; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages);
    font-family:"IBM Plex Mono"; font-size:7pt; color:$mutedFg; }
}
@page cover { margin:0;
  @top-right { content:none } @bottom-left { content:none }
  @bottom-center { content:none } @bottom-right { content:none } }
@page summary { size: A4 landscape; margin: 12mm 14mm 16mm 14mm; }
@page detail {
  @top-left { content: "Section 2 · Details per learner"; font-family:"DM Sans";
    font-weight:600; font-size:6.4pt; letter-spacing:.09em; text-transform:uppercase;
    color:$mutedFg; }
  @top-right { content: string(learnerName); font-family:"Outfit"; font-weight:600;
    font-size:8pt; color:$primary; }
}

* { box-sizing: border-box; margin:0; padding:0; }
body { font-family:"DM Sans","DejaVu Sans",sans-serif; font-size:9.5pt; line-height:1.5;
  color:$ink; }
a { color:inherit; text-decoration:none; }
.mono { font-family:"IBM Plex Mono","DejaVu Sans",monospace; }
.g { font-family:"DejaVu Sans"; font-size:.9em; }
.mut { color:$mutedFg; }
.c { text-align:center; }

.portrait { page: auto; }
.landscape { page: summary; }
.detail-sec { page: detail; }
section { break-before: page; }
section.cover { break-before: auto; }

h1 { font-family:"Outfit"; font-weight:700; font-size:19pt; letter-spacing:-.01em;
  color:$heading; string-set: sectionTitle content(); margin:1pt 0 5pt; }
h2 { font-family:"Outfit"; font-weight:600; font-size:12.5pt; color:$heading;
  margin:0 0 4pt; }
h3 { font-family:"Outfit"; font-weight:600; font-size:10.5pt; color:$heading;
  margin:0 0 4pt; bookmark-level:none; }
h4,h5,h6 { bookmark-level:none; }
h2,h3 { break-after: avoid; }
.kicker { font-family:"DM Sans"; font-weight:600; font-size:7pt; letter-spacing:.14em;
  text-transform:uppercase; color:$mutedFg; margin-bottom:2pt; }
.lede { font-size:9pt; color:$mutedFgStrong; max-width:150mm; margin-bottom:10pt; }
.overline { font-family:"DM Sans"; font-weight:600; font-size:7pt; letter-spacing:.14em;
  text-transform:uppercase; color:$mutedFg; }

/* ---------- cover ---------- */
.cover { page: cover; height:297mm; position:relative; background:$paper; }
.cover-in { padding:20mm 20mm 0 20mm; }
.brandrow { border-bottom:1pt solid $border; padding-bottom:8pt; }
.wordmark { font-family:"Outfit"; font-weight:700; font-size:17pt; color:$primary;
  letter-spacing:-.01em; }
.tagline { font-family:"DM Sans"; font-weight:500; font-size:8pt; color:$mutedFg;
  letter-spacing:.06em; margin-top:1pt; }
.accentline { width:34pt; height:2.5pt; background:$accent; margin-top:8pt; }
.cover-mid { margin-top:42mm; }
.cover-title { font-family:"Outfit"; font-weight:700; font-size:30pt;
  letter-spacing:-.015em; color:$heading; margin:4pt 0 2pt; }
.cover-cohort { font-family:"Outfit"; font-weight:600; font-size:14pt; color:$primary;
  margin-bottom:3pt; }
.cover-partner { font-size:9pt; color:$mutedFgStrong; margin-bottom:14pt; }
.cover-card { background:$surface; border:1pt solid $border; border-radius:9pt;
  padding:10pt 12pt; width:120mm; margin-bottom:12pt; }
.courselist { list-style:none; margin-top:4pt; }
.courselist li { font-size:9.5pt; font-weight:500; padding:1.5pt 0; }
.courselist .mut { font-weight:400; }
.cover-meta { font-size:8pt; color:$mutedFgStrong; line-height:1.7; }
.cover-meta .k { display:inline-block; width:26mm; color:$mutedFg;
  text-transform:uppercase; font-size:6.6pt; letter-spacing:.08em; }
.caveat { font-size:8pt; color:$mutedFg; font-style:italic; margin-top:10pt;
  max-width:120mm; }
.cover-band { position:absolute; bottom:0; left:0; right:0; height:18mm;
  background:$primary; color:$paper; display:flex; align-items:center;
  justify-content:space-between; padding:0 20mm; }
.band-powered { white-space:nowrap; }
.pby { font-family:"DM Sans"; font-weight:500; font-size:7.5pt; color:$surfaceAlt;
  letter-spacing:.04em; margin-right:5pt; }
.band-brand { font-family:"Outfit"; font-weight:700; font-size:11pt; }
.band-note { font-family:"IBM Plex Mono"; font-size:7.5pt; color:$surfaceAlt; }

/* ---------- glance ---------- */
.stats { display:flex; gap:8pt; margin:6pt 0 14pt; }
.stat { flex:1; background:$surface; border:1pt solid $border; border-radius:8pt;
  padding:9pt 11pt; }
.stat .n { font-family:"Outfit"; font-weight:700; font-size:21pt; color:$primary;
  line-height:1.1; }
.stat .l { font-size:7pt; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
  color:$mutedFg; margin-top:2pt; }
.attn-head { display:flex; justify-content:space-between; align-items:baseline;
  margin-bottom:5pt; }
.attn { border:1pt solid $border; border-radius:8pt; overflow:hidden; }
.attn-row { display:flex; justify-content:space-between; padding:7pt 10pt;
  border-bottom:1pt solid $border; break-inside:avoid; }
.attn-row:last-child { border-bottom:none; }
.attn-row:nth-child(even) { background:$surface; }
.attn-name { font-family:"Outfit"; font-weight:600; font-size:10pt; margin-bottom:2pt; }
.reason { font-size:8.4pt; color:$mutedFgStrong; margin-top:1.5pt; }
.reason .badge { margin-right:5pt; }
.pref { font-family:"IBM Plex Mono"; font-size:8.4pt; color:$primary; font-weight:500;
  white-space:nowrap; padding-left:8pt; }
.pref::after { content: target-counter(attr(href), page); }
.foot { font-size:7.8pt; color:$mutedFg; margin-top:7pt; max-width:160mm; }

.badge { display:inline-block; font-size:6.6pt; font-weight:600; letter-spacing:.05em;
  text-transform:uppercase; border-radius:3pt; padding:.5pt 4.5pt; vertical-align:.5pt; }
.bd-error { background:$error; color:$onError; }
.bd-warning { background:$warning; color:$onWarning; }

/* ---------- contents ---------- */
.toc { margin:5pt 0 11pt; }
.toc-row { display:flex; align-items:flex-end; padding:1.5pt 0; font-size:9.3pt; }
.toc-row.lv1 { font-weight:600; font-family:"Outfit"; margin-top:2pt; }
.toc-row.lv2 { padding-left:14pt; font-size:8.6pt; color:$mutedFgStrong; }
.toc-row .fill { flex:1; border-bottom:.7pt dotted $borderStrong; margin:0 5pt 2.6pt; }
.toc-row::after { content: target-counter(attr(href), page);
  font-family:"IBM Plex Mono"; font-size:8pt; color:$mutedFgStrong; }
.defs-h { break-before:page; margin-top:2pt; }
.defs { columns:2; column-gap:9mm; margin-bottom:7pt; }
.defs p { font-size:8.6pt; margin-bottom:4pt; }
.defs .rules { margin:2pt 0 5pt 11pt; font-size:8.6pt; }
.defs .rules li { margin-bottom:2.5pt; }
.legendstrip { font-size:8.6pt; color:$mutedFgStrong; margin-top:6pt; }
.legendstrip .chip.lg { margin:3pt 3pt 0 0; font-size:8pt; }

/* ---------- tables (shared) ---------- */
table { border-collapse:collapse; width:100%; }
th,td { text-align:left; vertical-align:top; padding:3.2pt 5pt; font-size:8pt;
  line-height:1.35; border-bottom:.6pt solid $border; }
thead th { font-family:"DM Sans"; font-weight:600; font-size:6.6pt;
  text-transform:uppercase; letter-spacing:.07em; color:$mutedFgStrong;
  background:$surface; border-bottom:1pt solid $borderStrong; }
tbody tr:nth-child(even) td { background:$surface; }   /* banding */
tr { break-inside:avoid; }

/* status tints AFTER banding so they win on banded rows */
.st-success { background:$successLight; color:$onSuccessLight; }
.st-info    { background:$infoLight;    color:$onInfoLight; }
.st-warning { background:$warningLight; color:$onWarningLight; }
.st-error   { background:$errorLight;   color:$onErrorLight; }
.st-muted   { background:$muted;        color:$onMuted; }
td.st-success, td.st-info, td.st-warning, td.st-error, td.st-muted { font-weight:500; }
tbody tr:nth-child(even) td.st-success { background:$successLight; }
tbody tr:nth-child(even) td.st-info    { background:$infoLight; }
tbody tr:nth-child(even) td.st-warning { background:$warningLight; }
tbody tr:nth-child(even) td.st-error   { background:$errorLight; }
tbody tr:nth-child(even) td.st-muted   { background:$muted; }

.chip { display:inline-block; border-radius:3pt; padding:.4pt 4.5pt; font-size:7.4pt;
  font-weight:500; border:.6pt solid $border; }
.chip-solid { display:inline-block; border-radius:3pt; padding:.6pt 5.5pt;
  font-size:7.2pt; font-weight:600; }
.chip-solid.st-error { background:$error; color:$onError; }

/* ---------- summary (landscape) ---------- */
.coursetbl { margin-bottom:16pt; }
.coursetbl h2 { margin-top:2pt; }
.tbl-legend { font-size:7.6pt; color:$mutedFg; margin:0 0 4pt; }
table.summary { table-layout:fixed; }
.summary .w-name { width:34mm; } .summary .w-cmp { width:34mm; }
.summary .w-li { width:56mm; }   .summary .w-when { width:15mm; }
.summary .w-qs { width:15.5mm; } .summary .w-qa { width:10.5mm; }
.summary td.name { font-weight:600; }
.summary th.qgroup, .summary td.qgroup { border-left:1pt solid $borderStrong; }
.summary th.sub { font-size:6.2pt; }
.summary td.li { font-size:7.4pt; }
.summary .att { color:$mutedFgStrong; }
.cmp .pctv { font-weight:600; margin:0 4pt 0 4pt; }
.cmp .frac { font-size:6.8pt; color:inherit; opacity:.8; }
.bar { height:4pt; background:$border; border-radius:2pt; margin-top:2.6pt; }
.bar i { display:block; height:4pt; border-radius:2pt; background:$primary; }
.bar.err i { background:$error; }

/* ---------- details ---------- */
article.student { break-before:page; }
article.student.firststu { break-before:auto; }
.stu-head { display:flex; justify-content:space-between; align-items:baseline;
  border-bottom:1.6pt solid $primary; padding-bottom:3pt; margin-bottom:7pt; }
.stu-name { string-set: learnerName content(); font-size:14pt; margin:0; }
.sid { font-size:7.4pt; color:$mutedFg; }
.flags { border:1pt solid $border; border-radius:6pt; background:$surface;
  padding:6pt 9pt; margin-bottom:8pt; break-inside:avoid; }
.flags.sev-error { border-left:3pt solid $error; }
.flags.sev-warning { border-left:3pt solid $warning; }
.flags .reason { margin:1.5pt 0; }
.noflags { font-size:8.4pt; color:$mutedFg; margin-bottom:8pt; }
.noact { font-family:"Outfit"; font-weight:600; font-size:10.5pt; color:$onErrorLight;
  background:$errorLight; border-radius:6pt; padding:6pt 9pt; margin-bottom:8pt; }
.courseblk { margin-bottom:11pt; }
.courseblk h3 .chip { margin-left:6pt; vertical-align:1pt; }
.subhead { font-size:7.2pt; font-weight:600; letter-spacing:.09em;
  text-transform:uppercase; color:$mutedFg; margin:7pt 0 2.5pt; break-after:avoid; }
.subhead .normal { text-transform:none; letter-spacing:0; font-weight:400; }
.none { font-size:8.4pt; color:$mutedFg; }
.allclear { font-size:8.2pt; color:$onSuccessLight; }
table.items td { font-size:7.6pt; padding:1.8pt 5pt; }
.items .it { width:36%; } .items .dt { width:14%; color:$mutedFgStrong; font-size:7.2pt; }
table.attempts { width:130mm; }
table.rollup .qn { width:9mm; }
table.rollup .wr { width:13mm; }
table.rollup td.picked { font-size:7.6pt; }

/* ---------- confusions ---------- */
.quizblk { margin-bottom:13pt; break-inside:avoid-page; }
table.conf { table-layout:fixed; }
.conf .w-qn { width:10mm; } .conf .w-qt { width:66mm; }
.conf .w-wo { width:70mm; } .conf .w-ra { width:26mm; }
.conf td { font-size:7.8pt; }
.conf .qtext { line-height:1.45; }
.conf .qtext .chip { margin-top:2.5pt; }
.conf .wopts .chip { margin:1pt 2pt 1pt 0; }
.conf .ratio .big { font-weight:600; font-size:8.4pt; }
.caution { max-width:165mm; }
""")

# ===========================================================================
# ASSEMBLE + RENDER
# ===========================================================================
def build_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="en-ZA">
<head>
<meta charset="utf-8"/>
<title>{esc(BRAND["partner_name"])} — Cohort progress report · {esc(COHORT_CODE)}</title>
<meta name="author" content="{esc(BRAND["partner_name"])}"/>
<meta name="generator" content="{esc(BRAND["powered_by"])}"/>
<meta name="description"
  content="Cohort progress report — sample/template render · Powered by {esc(BRAND["powered_by"])}"/>
<style>{CSS_SRC.substitute(THEME | {
    "footCohort": COHORT_CODE,
    "footPartner": BRAND["partner_name"],
    "footPoweredBy": BRAND["powered_by"]})}</style>
</head>
<body>
{cover()}
{glance()}
{contents()}
{summary()}
{details()}
{confusions()}
</body>
</html>"""

def main():
    html_str = build_html()
    (OUT / "report.html").write_text(html_str, encoding="utf-8")
    pdf_path = OUT / "first-class-cohort-report-sample.pdf"
    HTML(string=html_str, base_url=str(BASE)).write_pdf(str(pdf_path))
    # quick QA readout
    from pypdf import PdfReader
    r = PdfReader(str(pdf_path))
    print(f"OK: {pdf_path.name} · {len(r.pages)} pages")
    print(f"flagged learners: {[s['id'] for s in FLAGGED]}")
    print(f"median {MEDIAN_PCT}% · not started {NOT_STARTED} · complete {COMPLETE_ALL}")
    def walk(items, depth=0):
        for it in items:
            if isinstance(it, list):
                walk(it, depth + 1)
            else:
                print("  " * depth + "▸ " + (it.title or "?"))
    print("bookmarks:")
    walk(r.outline)

if __name__ == "__main__":
    main()
