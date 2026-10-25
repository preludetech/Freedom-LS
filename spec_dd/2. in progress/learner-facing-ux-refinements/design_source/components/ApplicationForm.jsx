/* Application wizard — 5 steps, lean chrome, autosave. Also the submitted screen.
   variant: "empty" (nothing typed yet) | "filled" | "error" */

const Field = ({ label, opt, hint, err, children, full }) => (
  <div className={"lxa-field" + (full ? " full" : "")}>
    <label className="fc-label">{label}{opt ? <span> · optional</span> : null}</label>
    {children}
    {err ? <div className="lxa-err"><i className="ph-fill ph-warning-circle"></i>{err}</div> : hint ? <div className="lxa-hint">{hint}</div> : null}
  </div>
);

const Check = ({ on, t, d, onClick }) => (
  <div className={"lxa-check" + (on ? " on" : "")} onClick={onClick}>
    <div className="box">{on ? <i className="ph-bold ph-check"></i> : null}</div>
    <div><div className="t">{t}</div>{d ? <div className="d">{d}</div> : null}</div>
  </div>
);

function StepAboutYou({ v, error }) {
  const val = (k) => (v ? APP_VALUES[k] : "");
  return (
    <>
      <div className="lxa-fields">
        <Field label="Legal name" hint="As it appears on your licence.">
          <input className="fc-input" defaultValue={val("legalName")} placeholder="Given and family name" />
        </Field>
        <Field label="Preferred name" opt>
          <input className="fc-input" defaultValue={val("preferredName")} placeholder="What we'll call you" />
        </Field>
        <Field label="Date of birth" err={error ? "Enter your date of birth — it's checked against your licence." : null}>
          <input className={"fc-input" + (error ? " lxa-input-err" : "")} defaultValue={v && !error ? "14/03/1991" : ""} placeholder="DD / MM / YYYY" />
        </Field>
        <Field label="Email">
          <input className="fc-input" defaultValue={val("email")} placeholder="you@example.com" />
        </Field>
        <Field label="Mobile">
          <input className="fc-input" defaultValue={val("phone")} placeholder="+61 …" />
        </Field>
        <Field label="Country of residence">
          <select className="fc-select" defaultValue={v ? "au" : ""}>
            <option value="">Select…</option>
            <option value="au">Australia</option>
            <option value="nz">New Zealand</option>
          </select>
        </Field>
        <Field label="Street address" full>
          <input className="fc-input" defaultValue={v ? "18 Grevillea St" : ""} placeholder="Number and street" />
        </Field>
        <Field label="Suburb">
          <input className="fc-input" defaultValue={v ? "Fitzroy" : ""} />
        </Field>
        <Field label="State / postcode">
          <input className="fc-input" defaultValue={v ? "VIC 3065" : ""} />
        </Field>
      </div>
    </>
  );
}

function StepExperience({ v }) {
  const rat = ["Multirotor < 25 kg", "Fixed-wing < 7 kg", "Night VLOS", "Beyond visual line of sight", "Helicopter"];
  return (
    <div className="lxa-fields">
      <Field label="Licence held">
        <select className="fc-select" defaultValue={v ? "repl" : ""}>
          <option value="">Select…</option>
          <option value="repl">RePL — Remote Pilot Licence (CASA)</option>
          <option value="cpl">CPL — Commercial Pilot Licence</option>
        </select>
      </Field>
      <Field label="Licence number">
        <input className="fc-input" defaultValue={v ? "0091-4477" : ""} placeholder="e.g. 0091-4477" />
      </Field>
      <Field label="Expiry date">
        <input className="fc-input" defaultValue={v ? "31/01/2028" : ""} placeholder="DD / MM / YYYY" />
      </Field>
      <Field label="Total command hours" hint="Verified against the logbook extract you upload next.">
        <input className="fc-input" defaultValue={v ? "412" : ""} placeholder="Hours" />
      </Field>
      <Field label="Ratings and endorsements held" full>
        <div className="lxa-checks" style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 10 }}>
          {rat.map((r, i) => <Check key={r} on={v && i < 3} t={r} />)}
        </div>
      </Field>
      <Field label="Current operator or employer" full opt>
        <input className="fc-input" defaultValue={v ? "SkyLift Surveys Pty Ltd" : ""} placeholder="Organisation" />
      </Field>
      <Field label="Your role there">
        <input className="fc-input" defaultValue={v ? "Chief Remote Pilot" : ""} />
      </Field>
      <Field label="Hours in the last 12 months">
        <input className="fc-input" defaultValue={v ? "96" : ""} />
      </Field>
      <Field label="Reportable incidents in the last 3 years" full hint="Declaring an incident does not disqualify you. Omitting one does.">
        <textarea className="fc-input" rows={3} defaultValue={v ? "None reported." : ""} placeholder="Describe each incident and its outcome, or write “none”." />
      </Field>
    </div>
  );
}

function StepDocuments({ v }) {
  const docs = v ? APP_DOCS : APP_DOCS.map((d) => ({ ...d, nm: "", ok: false }));
  return (
    <div style={{ marginTop: 32, display: "flex", flexDirection: "column", gap: 12 }}>
      {docs.map((d, i) => (
        d.ok ? (
          <div className="lxa-doc ok" key={i}>
            <div className="ic"><i className="ph-fill ph-file-pdf"></i></div>
            <div>
              <div className="nm">{d.nm}</div>
              <div className="mt">{d.req} · {d.mt}</div>
            </div>
            <div className="sp" />
            <button className="fc-btn fc-btn-ghost fc-btn-sm"><i className="ph ph-arrow-clockwise"></i><span>Replace</span></button>
            <button className="fc-btn fc-btn-ghost fc-btn-sm" aria-label="Remove"><i className="ph ph-trash"></i></button>
          </div>
        ) : (
          <div key={i}>
            <div className="fc-label" style={{ marginBottom: 8 }}>{d.req}</div>
            <div className="lxa-drop">
              <i className="ph ph-upload-simple"></i>
              <div className="t">Drop a file here, or <span style={{ color: "var(--color-primary)", textDecoration: "underline" }}>browse</span></div>
              <div className="d">{d.hint}</div>
            </div>
          </div>
        )
      ))}
      <div className="lxa-hint" style={{ marginTop: 4 }}>Files are visible only to the admissions team and are deleted 12 months after a decision.</div>
    </div>
  );
}

function StepMotivation({ v }) {
  const text = v ? APP_VALUES.motivation : "";
  const slots = ["Weekdays", "Evenings", "The 11–12 Oct assessment weekend", "I need flexible scheduling"];
  return (
    <div className="lxa-fields">
      <Field label="Why do you want to become an examiner?" full hint="A few honest paragraphs. We read every one.">
        <textarea className="fc-input" rows={9} defaultValue={text} placeholder="Tell us about the assessing you already do, and what you want this accreditation to change." />
        <div className="lxa-count">{text.length} / 2000</div>
      </Field>
      <Field label="When can you attend the practical assessment?" full>
        <div className="lxa-checks">
          {slots.map((s, i) => <Check key={s} on={v && (i === 0 || i === 2)} t={s} />)}
        </div>
      </Field>
      <Field label="Anything we should know to support you?" full opt hint="Access needs, scheduling constraints, anything else.">
        <textarea className="fc-input" rows={3} defaultValue="" placeholder="Optional" />
      </Field>
    </div>
  );
}

const REVIEW_SECTIONS = [
  { step: 1, t: "About you", rows: [["Legal name", "legalName"], ["Preferred name", "preferredName"], ["Date of birth", "dob"], ["Email", "email"], ["Mobile", "phone"], ["Address", "address"]] },
  { step: 2, t: "Licences & experience", rows: [["Licence", "licence"], ["Expires", "licenceExpiry"], ["Ratings held", "ratings"], ["Command hours", "hours"], ["Operator & role", "operator"], ["Incidents declared", "incidents"]] },
  { step: 4, t: "Why you're applying", rows: [["Statement", "motivation", true], ["Assessment availability", "availability"]] },
];

function ReviewBody({ onEdit, declared, setDeclared, readOnly }) {
  return (
    <div className="lxa-rev">
      {REVIEW_SECTIONS.map((s) => (
        <div className="lxa-rev-sec" key={s.t}>
          <div className="lxa-rev-h">
            <div className="t">{s.t}</div>
            {readOnly ? <span className="lxa-lock"><i className="ph ph-lock-simple"></i>Locked</span>
              : <button className="lxa-rev-edit" onClick={() => onEdit?.(s.step)}><i className="ph ph-pencil-simple"></i>Edit</button>}
          </div>
          <dl className="lxa-kv">
            {s.rows.map(([k, key, pre]) => (
              <React.Fragment key={k}>
                <dt>{k}</dt>
                <dd className={pre ? "pre" : ""}>{APP_VALUES[key]}</dd>
              </React.Fragment>
            ))}
          </dl>
        </div>
      ))}
      <div className="lxa-rev-sec">
        <div className="lxa-rev-h">
          <div className="t">Documents</div>
          {readOnly ? <span className="lxa-lock"><i className="ph ph-lock-simple"></i>Locked</span>
            : <button className="lxa-rev-edit" onClick={() => onEdit?.(3)}><i className="ph ph-pencil-simple"></i>Edit</button>}
        </div>
        <div style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
          {APP_DOCS.filter((d) => d.ok).map((d) => (
            <div key={d.nm} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14 }}>
              <i className="ph-fill ph-file-pdf" style={{ color: "var(--color-primary)", fontSize: 18 }}></i>
              <span style={{ fontWeight: 600, color: "var(--fg-1)" }}>{d.nm}</span>
              <span style={{ color: "var(--fg-3)", fontSize: 12.5 }}>{d.req}</span>
            </div>
          ))}
        </div>
      </div>
      {readOnly ? null : (
        <>
          <Check on={declared} onClick={() => setDeclared(!declared)}
            t="Everything here is true and complete."
            d="Knowingly giving false information ends the application and any accreditation that follows from it." />
          <div className="lxa-hint">By submitting you agree to the programme terms and the assessment code of conduct.</div>
        </>
      )}
    </div>
  );
}

function ApplicationWizard({ step: initialStep = 1, variant = "filled", onExit, onSubmit, showExitModal = false }) {
  const [step, setStep] = React.useState(initialStep);
  const [declared, setDeclared] = React.useState(false);
  const [exit, setExit] = React.useState(showExitModal);
  const v = variant !== "empty";
  const error = variant === "error";
  const s = APP_STEPS[step - 1];
  const last = step === 5;

  return (
    <div className="lxa-wz">
      <aside className="lxa-wz-rail">
        <div className="lxa-wz-kicker">Application</div>
        <div className="lxa-wz-course">{APP_META.course}</div>
        <div className="lxa-wz-cohort">{APP_META.cohort}</div>
        <div className="lxa-steps">
          {APP_STEPS.map((st) => (
            <button key={st.n} className={"lxa-step" + (st.n < step ? " done" : st.n === step ? " active" : "")}
              onClick={() => setStep(st.n)}>
              <div className="n">{st.n < step ? <i className="ph-bold ph-check" style={{ fontSize: 11 }}></i> : st.n}</div>
              <div><div className="l">{st.label}</div><div className="sl">{st.sub}</div></div>
            </button>
          ))}
        </div>
        <div className="lxa-wz-save"><i className="ph-fill ph-check-circle"></i>Saved just now</div>
        <div className="lxa-wz-exit">
          <button className="fc-btn fc-btn-ghost fc-btn-sm" onClick={() => setExit(true)}>
            <i className="ph ph-arrow-left"></i><span>Save &amp; leave</span>
          </button>
        </div>
      </aside>

      <main className="lxa-wz-main">
        <div className="lxa-wz-count">STEP {step} OF 5</div>
        <h1 className="lxa-wz-h">{last ? "Check your application" : s.label}</h1>
        <p className="lxa-wz-lede">
          {step === 1 ? "We use this to verify your licence, so it needs to match your official records."
            : step === 2 ? "Your flying history. Hours are checked against the logbook extract you upload next."
            : step === 3 ? "Four documents. Photos of paper documents are fine as long as every edge is visible."
            : step === 4 ? "The part a human reads closely."
            : "Nothing is sent until you press submit. You can edit any section from here."}
        </p>

        {step === 1 ? <StepAboutYou v={v} error={error} />
          : step === 2 ? <StepExperience v={v} />
          : step === 3 ? <StepDocuments v={v} />
          : step === 4 ? <StepMotivation v={v} />
          : <ReviewBody onEdit={setStep} declared={declared} setDeclared={setDeclared} />}

        <div className="lxa-wz-nav">
          {step > 1 ? (
            <button className="fc-btn fc-btn-secondary" onClick={() => setStep(step - 1)}>
              <i className="ph ph-arrow-left"></i><span>Back</span>
            </button>
          ) : null}
          <div className="sp" />
          <span className="lxa-wz-note">{last ? (declared ? "Ready to send" : "Tick the declaration to submit") : "Progress saves as you type"}</span>
          {last ? (
            <button className="fc-btn fc-btn-primary fc-btn-lg" disabled={!declared} onClick={onSubmit}>
              <i className="ph ph-paper-plane-tilt"></i><span>Submit application</span>
            </button>
          ) : (
            <button className="fc-btn fc-btn-primary" onClick={() => setStep(step + 1)}>
              <span>Continue</span><i className="ph ph-arrow-right"></i>
            </button>
          )}
        </div>
      </main>

      {exit ? (
        <div className="lxa-modal-scrim" onClick={() => setExit(false)}>
          <div className="lxa-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Draft saved</h3>
            <p>Your application is saved as a draft — step {step} of 5. Pick it up from your dashboard, your applications page, or the link in the email we just sent.</p>
            <div className="lxa-hint" style={{ marginTop: 14 }}>{APP_META.closes}.</div>
            <div className="lxa-modal-acts">
              <button className="fc-btn fc-btn-ghost" onClick={() => setExit(false)}>Keep going</button>
              <button className="fc-btn fc-btn-primary" onClick={() => { setExit(false); onExit?.(); }}>Leave for now</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ApplicationSubmitted({ onStatus, onCourses }) {
  return (
    <div className="lxa-shell">
      <div className="lxa-done">
        <div className="lxa-done-mark"><i className="ph-fill ph-check"></i></div>
        <h1>Application sent</h1>
        <p>We've got everything for {APP_META.course}, {APP_META.cohort.replace(" · ", " — ")}. A copy is in your inbox.</p>
        <div className="lxa-ref"><i className="ph ph-hash"></i>{APP_META.ref}</div>
        <div className="lxa-next">
          <div className="h">What happens next</div>
          <ol>
            <li><strong>Eligibility check, 2–3 working days.</strong> We verify your licence and hours against CASA records.</li>
            <li><strong>Assessment interview.</strong> 45 minutes by video with a senior examiner — you'll pick from three time slots.</li>
            <li><strong>Decision within 3 working days of the interview.</strong> If you're offered a seat you'll have until 20 Sep to accept it.</li>
          </ol>
        </div>
        <div className="lxa-done-acts">
          <button className="fc-btn fc-btn-primary fc-btn-lg" onClick={onStatus}><i className="ph ph-file-text"></i><span>View my application</span></button>
          <button className="fc-btn fc-btn-secondary fc-btn-lg" onClick={onCourses}><span>Back to my courses</span></button>
        </div>
        <div className="lxa-hint" style={{ marginTop: 20 }}>You can still edit your answers until the eligibility check begins.</div>
      </div>
    </div>
  );
}

Object.assign(window, { ApplicationWizard, ApplicationSubmitted, ReviewBody, Field, Check });
