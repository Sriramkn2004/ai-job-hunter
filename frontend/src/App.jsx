import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertCircle, ArrowUpRight, BriefcaseBusiness, Building2,
  CheckCircle2, ClipboardCheck, Clock3, ExternalLink, Filter, Globe2, LoaderCircle,
  RefreshCw, Search, ShieldCheck, Workflow
} from "lucide-react";

const API = "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `Request failed (${response.status})`);
  }
  return response.json();
}

function Metric({ icon: Icon, label, value, detail, tone = "blue" }) {
  return <article className="metric">
    <div className={`metric-icon ${tone}`}><Icon size={19} /></div>
    <div className="metric-copy"><span>{label}</span><strong>{value ?? "—"}</strong><small>{detail}</small></div>
  </article>;
}

function statusClass(status) {
  return status === "matched" ? "matched" : status === "review" ? "review" : "skipped";
}

function formatDate(value) {
  if (!value) return "Date not provided";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date not provided" : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [boards, setBoards] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [selectedBoards, setSelectedBoards] = useState([]);
  const [importMessage, setImportMessage] = useState("");
  const [importing, setImporting] = useState(false);
  const [preferences, setPreferences] = useState(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [country, setCountry] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [applications, setApplications] = useState([]);
  const [applicationEmail, setApplicationEmail] = useState("sriramkn2004@gmail.com");
  const [applicationBusy, setApplicationBusy] = useState(false);
  const [applicationMessage, setApplicationMessage] = useState("");
  const [submissionReferences, setSubmissionReferences] = useState({});
  const [adzunaCountry, setAdzunaCountry] = useState("in");
  const [adzunaWhat, setAdzunaWhat] = useState("Python Developer");
  const [adzunaWhere, setAdzunaWhere] = useState("Bangalore");
  const [adzunaBusy, setAdzunaBusy] = useState(false);
  const [adzunaMessage, setAdzunaMessage] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const params = new URLSearchParams({ limit: "50", offset: String(offset) });
      if (query.trim()) params.set("q", query.trim());
      if (status) params.set("status", status);
      if (country) params.set("country", country);
      const [stats, jobRows, boardRows, prefs, catalogData, applicationRows] = await Promise.all([
        request(`${API}/monitoring/status`),
        request(`${API}/jobs?${params.toString()}`),
        request(`${API}/monitoring/boards`),
        request(`${API}/preferences`),
        request(`${API}/sources/catalog`),
        request(`${API}/applications`),
      ]);
      setSummary(stats);
      setJobs(jobRows);
      setHasMore(jobRows.length === 50);
      setBoards(boardRows);
      setPreferences(prefs);
      setCatalog(catalogData.boards || []);
      setApplications(applicationRows);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message || "Could not connect to the API.");
    } finally {
      setLoading(false);
    }
  }, [query, status, country, offset]);

  useEffect(() => { load(); }, [load]);

  const boardFailures = useMemo(() => boards.filter((board) => (board.consecutive_failures || 0) > 0).length, [boards]);

  function toggleBoard(key) {
    setSelectedBoards((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  async function importSelectedBoards() {
    const selections = catalog.filter((board) => selectedBoards.includes(`${board.provider}:${board.slug}`));
    if (!selections.length) return;
    setImporting(true);
    setImportMessage("");
    try {
      const result = await request(`${API}/sources/catalog/import`, {
        method: "POST",
        body: JSON.stringify(selections.map(({ provider, slug }) => ({ provider, slug }))),
      });
      setImportMessage(`${result.imported_count} imported · ${result.skipped_count} already registered · ${result.rejected_count} could not be imported`);
      setSelectedBoards([]);
      await load();
    } catch (err) {
      setImportMessage(err.message || "Catalog import failed.");
    } finally {
      setImporting(false);
    }
  }

  async function prepareApplication(job) {
    setApplicationBusy(true);
    setApplicationMessage("");
    try {
      await request(`${API}/applications/drafts`, {
        method: "POST",
        body: JSON.stringify({ source_job_id: job.source_job_id, candidate_email: applicationEmail }),
      });
      setApplicationMessage(`Prepared a truthful draft for ${job.title} at ${job.company}.`);
      await load();
    } catch (err) {
      setApplicationMessage(err.message || "Could not prepare application.");
    } finally {
      setApplicationBusy(false);
    }
  }

  async function saveApplication(application) {
    setApplicationBusy(true);
    try {
      await request(`${API}/applications/${application.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          cover_letter: application.cover_letter,
          account_required: application.account_required,
          account_status: application.account_status,
          notes: application.notes,
        }),
      });
      setApplicationMessage(`Saved application for ${application.company}.`);
      await load();
    } catch (err) {
      setApplicationMessage(err.message || "Could not save application.");
    } finally {
      setApplicationBusy(false);
    }
  }

  async function approveApplication(application) {
    if (!window.confirm(`Approve the prepared application for ${application.title} at ${application.company}? This records approval but does not submit it to the employer.`)) return;
    setApplicationBusy(true);
    try {
      await request(`${API}/applications/${application.id}/approve`, { method: "POST" });
      setApplicationMessage("Approved and added to your application tracker. A supported employer submission connector is not available yet.");
      await load();
    } catch (err) {
      setApplicationMessage(err.message || "Could not approve application.");
    } finally {
      setApplicationBusy(false);
    }
  }

  async function recordSubmission(application) {
    const reference = submissionReferences[application.id]?.trim();
    if (!reference) {
      setApplicationMessage("Add the employer confirmation reference before marking an application submitted.");
      return;
    }
    if (!window.confirm("Record this application as submitted? Only do this after the employer confirms successful submission.")) return;
    setApplicationBusy(true);
    try {
      await request(`${API}/applications/${application.id}/record-submission?confirmation_reference=${encodeURIComponent(reference)}`, { method: "POST" });
      setApplicationMessage("Submission recorded.");
      await load();
    } catch (err) {
      setApplicationMessage(err.message || "Could not record submission.");
    } finally {
      setApplicationBusy(false);
    }
  }

  async function runAdzunaSearch() {
    if (!adzunaWhat.trim()) {
      setAdzunaMessage("Enter a job title or keyword.");
      return;
    }
    setAdzunaBusy(true);
    setAdzunaMessage("");
    try {
      const params = new URLSearchParams({
        country: adzunaCountry,
        what: adzunaWhat.trim(),
        where: adzunaWhere.trim(),
      });
      const result = await request(`${API}/discovery/adzuna?${params.toString()}`, { method: "POST" });
      setAdzunaMessage(`Found ${result.discovered} · saved ${result.inserted} new · ${result.duplicates} duplicates`);
      await load();
    } catch (err) {
      setAdzunaMessage(err.message || "Adzuna search failed. Check API credentials in .env.");
    } finally {
      setAdzunaBusy(false);
    }
  }

  async function runScan() {
    setScanning(true);
    setError("");
    try {
      await request(`${API}/discovery/run`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message || "Discovery scan failed.");
    } finally {
      setScanning(false);
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Workflow size={22} /></div><div><b>AI Job Hunter</b><span>DISCOVERY WORKSPACE</span></div></div>
      <nav><a className="nav-item active"><Activity size={18} /> Overview</a><a className="nav-item" href="#jobs"><BriefcaseBusiness size={18} /> Job matches</a><a className="nav-item" href="#applications"><ClipboardCheck size={18} /> Applications</a><a className="nav-item" href="#sources"><Globe2 size={18} /> Sources</a></nav>
      <div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={17} /><span>Public-source discovery<br />No automatic applications</span></div><small>Personal job search workspace</small></div>
    </aside>

    <main className="main-content">
      <header className="topbar"><div><p className="eyebrow">YOUR CAREER COMMAND CENTER</p><h1>Overview</h1><p className="subheading">Discover relevant opportunities and monitor your job sources.</p></div>
        <div className="top-actions"><button className="button secondary" onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button><button className="button primary" onClick={runScan} disabled={scanning}><Activity size={16} /> {scanning ? "Scanning…" : "Run discovery"}</button></div>
      </header>

      {error && <div className="alert"><AlertCircle size={18} /><span>{error}</span><button onClick={() => setError("")}>Dismiss</button></div>}

      <section className="metrics-grid">
        <Metric icon={BriefcaseBusiness} label="Jobs discovered" value={summary?.jobs_stored ?? "—"} detail="Saved in your workspace" />
        <Metric icon={CheckCircle2} label="Need your attention" value={summary?.jobs_needing_attention ?? "—"} detail="Matched + review" tone="green" />
        <Metric icon={Globe2} label="Registered sources" value={summary?.registered_boards ?? "—"} detail="Public job feeds" tone="purple" />
        <Metric icon={Activity} label="Source issues" value={boardFailures} detail="Boards with recent failures" tone={boardFailures ? "orange" : "green"} />
      </section>

      <section className="profile-strip">
        <div className="profile-icon"><ShieldCheck size={19} /></div>
        <div className="profile-copy"><b>Screening profile</b><span>{preferences ? `India floor ₹${preferences.india_min_ctc_lpa} LPA · USA floor $${Number(preferences.usa_min_salary_usd_annual || 0).toLocaleString()} / year · ${preferences.preferred_locations?.join(", ") || "No preferred location"}` : "Loading your preferences…"}</span></div>
        <span className="profile-tag">Unknown salary → review</span>
      </section>

      <section className="content-section catalog-section">
        <div className="section-heading"><div><p className="eyebrow">GET STARTED</p><h2>Curated employer boards</h2><p>Select public company feeds; each is checked live before registration.</p></div><span className="count-pill">{catalog.length} curated</span></div>
        <div className="catalog-grid">{catalog.map((board) => {
          const key = `${board.provider}:${board.slug}`;
          const alreadyAdded = boards.some((item) => item.provider === board.provider && item.slug === board.slug);
          return <label className={`catalog-card ${alreadyAdded ? "catalog-added" : ""}`} key={key}>
            <input type="checkbox" checked={alreadyAdded || selectedBoards.includes(key)} disabled={alreadyAdded || importing} onChange={() => toggleBoard(key)} />
            <span className="catalog-card-copy"><b>{board.company_name}</b><small>{board.provider} · {board.market}</small><a href={board.careers_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Careers page <ArrowUpRight size={12} /></a></span>
            {alreadyAdded && <span className="added-label">Added</span>}
          </label>;
        })}</div>
        <div className="catalog-actions"><span>{importMessage || "Import verifies the selected public feed and saves only reachable boards."}</span><button className="button primary" onClick={importSelectedBoards} disabled={!selectedBoards.length || importing}>{importing ? "Checking feeds…" : `Import selected (${selectedBoards.length})`}</button></div>
      </section>

      <section className="content-section adzuna-section">
        <div className="section-heading"><div><p className="eyebrow">AGGREGATOR SEARCH</p><h2>Search India & USA jobs</h2><p>Run an on-demand Adzuna search. Add your own API credentials in the private .env file.</p></div><span className="count-pill">Optional API</span></div>
        <div className="filters adzuna-filters">
          <label className="select-box"><Globe2 size={16} /><select value={adzunaCountry} onChange={(event) => { setAdzunaCountry(event.target.value); setAdzunaWhere(event.target.value === "in" ? "Bangalore" : "United States"); }}><option value="in">India</option><option value="us">USA</option></select></label>
          <label className="search-box"><Search size={17} /><input value={adzunaWhat} onChange={(event) => setAdzunaWhat(event.target.value)} placeholder="Role or keywords" /></label>
          <label className="search-box"><Globe2 size={17} /><input value={adzunaWhere} onChange={(event) => setAdzunaWhere(event.target.value)} placeholder="City or region" /></label>
          <button className="button primary" onClick={runAdzunaSearch} disabled={adzunaBusy}>{adzunaBusy ? "Searching…" : "Search jobs"}</button>
        </div>
        {adzunaMessage && <p className="list-footnote">{adzunaMessage}</p>}
      </section>

      <section className="content-section" id="jobs">
        <div className="section-heading"><div><p className="eyebrow">OPPORTUNITIES</p><h2>Job inbox</h2><p>Review discovered roles and open the original employer application page.</p></div><span className="count-pill">{jobs.length} shown</span></div>
        <div className="filters">
          <label className="search-box"><Search size={17} /><input value={query} onChange={(e) => { setQuery(e.target.value); setOffset(0); }} placeholder="Search title, company, skills or location" /></label>
          <label className="select-box"><Filter size={16} /><select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}><option value="">All statuses</option><option value="matched">Matched</option><option value="review">Needs review</option><option value="skipped">Skipped</option></select></label>
          <label className="select-box"><Globe2 size={16} /><select value={country} onChange={(e) => { setCountry(e.target.value); setOffset(0); }}><option value="">All markets</option><option value="India">India</option><option value="USA">USA</option><option value="UK">UK</option><option value="Canada">Canada</option><option value="Australia">Australia</option></select></label>
        </div>
        {loading ? <div className="empty-state"><LoaderCircle className="spin" size={24} /> Loading jobs…</div> : jobs.length === 0 ? <div className="empty-state"><BriefcaseBusiness size={26} /><b>No jobs found yet</b><span>Run discovery after adding employer boards, or adjust your filters.</span></div> :
          <div className="job-list">{jobs.map((job) => <article className="job-card" key={job.source_job_id}>
            <div className="company-avatar">{(job.company || "?").slice(0, 1).toUpperCase()}</div>
            <div className="job-main"><div className="job-title-row"><h3>{job.title}</h3><span className={`status-badge ${statusClass(job.screening?.status)}`}>{job.screening?.status || "unscored"}</span></div>
              <div className="job-company"><Building2 size={14} /> {job.company} <span>·</span><Globe2 size={14} /> {job.location || job.country || "Location not specified"}</div>
              <div className="job-meta"><span>{job.source}</span><span><Clock3 size={13} /> {formatDate(job.posted_at)}</span>{job.salary_min || job.salary_max ? <span>{job.salary_currency || ""} {job.salary_min ?? "—"}–{job.salary_max ?? "—"} {job.salary_period || ""}</span> : <span>Salary not listed</span>}</div>
              {job.screening?.reasons?.length > 0 && <p className="job-reason">{job.screening.reasons.slice(0, 2).join(" · ")}</p>}
            </div>
            <div className="job-actions"><button className="button secondary prepare-button" onClick={() => prepareApplication(job)} disabled={applicationBusy || !job.apply_url}>{applications.some((item) => item.source_job_id === job.source_job_id) ? "Draft prepared" : "Prepare application"}</button><a className="open-job" href={job.apply_url} target="_blank" rel="noreferrer" aria-label={`Open ${job.title}`}><ExternalLink size={17} /></a></div>
          </article>)}</div>}
        <div className="pagination"><span>Showing {jobs.length ? offset + 1 : 0}–{offset + jobs.length} jobs</span><div><button className="button secondary" onClick={() => setOffset((value) => Math.max(0, value - 50))} disabled={offset === 0 || loading}>Previous</button><button className="button secondary" onClick={() => setOffset((value) => value + 50)} disabled={!hasMore || loading}>Next</button></div></div><p className="list-footnote">Listings link to their original source; verify details before applying.</p>
      </section>

      <section className="content-section" id="applications">
        <div className="section-heading"><div><p className="eyebrow">APPLICATION PIPELINE</p><h2>Application tracker</h2><p>Prepare truthful, editable applications and track account setup and confirmed submissions.</p></div><span className="count-pill">{applications.length} applications</span></div>
        <div className="application-profile">
          <label>Application email<input value={applicationEmail} onChange={(event) => setApplicationEmail(event.target.value)} type="email" /></label>
          <span>Use an inbox you control. Never enter passwords or OTPs here.</span>
        </div>
        {applicationMessage && <div className="application-message">{applicationMessage}</div>}
        {applications.length === 0 ? <div className="empty-state compact">No application drafts yet. Choose Prepare application on a matched or review job.</div> :
          <div className="application-list">{applications.map((application) => <article className="application-card" key={application.id}>
            <div className="application-card-head"><div><h3>{application.title}</h3><p>{application.company} · {application.candidate_email}</p></div><span className={`application-status ${application.status}`}>{application.status.replaceAll("_", " ")}</span></div>
            <label className="application-field">Cover letter<textarea value={application.cover_letter} onChange={(event) => setApplications((rows) => rows.map((row) => row.id === application.id ? { ...row, cover_letter: event.target.value } : row))} rows={7} disabled={application.status === "submitted" || application.status === "withdrawn"} /></label>
            <div className="application-controls">
              <label><input type="checkbox" checked={application.account_required} disabled={application.status === "submitted"} onChange={(event) => setApplications((rows) => rows.map((row) => row.id === application.id ? { ...row, account_required: event.target.checked, account_status: event.target.checked ? "required" : "not_required" } : row))} /> Employer account required</label>
              <select value={application.account_status} disabled={application.status === "submitted"} onChange={(event) => setApplications((rows) => rows.map((row) => row.id === application.id ? { ...row, account_status: event.target.value, account_required: event.target.value !== "not_required" } : row))}>
                <option value="not_required">No account needed</option><option value="required">Account needed</option><option value="created">Account created</option><option value="blocked">Unable to create / blocked</option>
              </select>
            </div>
            <label className="application-field">Notes<textarea value={application.notes} onChange={(event) => setApplications((rows) => rows.map((row) => row.id === application.id ? { ...row, notes: event.target.value } : row))} rows={2} placeholder="Recruiter, account setup notes, questions to verify…" disabled={application.status === "submitted"} /></label>
            <div className="application-controls application-actions">
              <a href={application.apply_url} target="_blank" rel="noreferrer">Open employer application <ExternalLink size={13} /></a>
              <button className="button secondary" onClick={() => saveApplication(application)} disabled={applicationBusy || application.status === "submitted"}>Save draft</button>
              {application.status === "draft" || application.status === "ready" ? <button className="button primary" onClick={() => approveApplication(application)} disabled={applicationBusy}>Approve application</button> : null}
            </div>
            {application.status === "approved" && <div className="submission-note"><b>Approved, not submitted.</b> No authorized submission connector is configured for this employer yet. Complete the employer's form yourself, then record its confirmation below.</div>}
            {application.status === "approved" && <div className="record-submission"><input value={submissionReferences[application.id] || ""} onChange={(event) => setSubmissionReferences((rows) => ({ ...rows, [application.id]: event.target.value }))} placeholder="Employer confirmation URL or reference" /><button className="button secondary" onClick={() => recordSubmission(application)} disabled={applicationBusy}>Record confirmed submission</button></div>}
            {application.status === "submitted" && <p className="job-reason">Recorded submission: {application.submission_reference}</p>}
          </article>)}</div>}
      </section>

      <section className="content-section" id="sources">
        <div className="section-heading"><div><p className="eyebrow">DISCOVERY NETWORK</p><h2>Source health</h2><p>Recent check status for your registered public job feeds.</p></div><span className="count-pill">{boards.length} sources</span></div>
        {boards.length === 0 ? <div className="empty-state compact">No sources registered yet.</div> : <div className="source-table">
          <div className="source-row source-head"><span>Employer / feed</span><span>Provider</span><span>Last scan</span><span>Jobs found</span><span>Status</span></div>
          {boards.map((board) => <div className="source-row" key={board.id || `${board.provider}-${board.slug}`}>
            <b>{board.company_name}</b><span className="provider-name">{board.provider}</span><span>{formatDate(board.last_checked_at)}</span><span>{board.last_job_count ?? "—"}</span>
            <span className={board.consecutive_failures ? "health-bad" : board.last_success_at ? "health-good" : "health-unknown"}>{board.consecutive_failures ? `${board.consecutive_failures} failures` : board.last_success_at ? "Healthy" : "Not checked"}</span>
          </div>)}
        </div>}
      </section>
      <footer className="footer"><span>AI Job Hunter · Built around permitted public job feeds</span><span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Waiting for API"}</span></footer>
    </main>
  </div>;
}