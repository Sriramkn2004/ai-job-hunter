import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertCircle, ArrowUpRight, BriefcaseBusiness, Building2,
  CheckCircle2, Clock3, ExternalLink, Filter, Globe2, LoaderCircle,
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
    throw new Error(body.detail || body.message || \`Request failed (\${response.status})\`);
  }
  return response.json();
}

function Metric({ icon: Icon, label, value, detail, tone = "blue" }) {
  return <article className="metric">
    <div className={\`metric-icon \${tone}\`}><Icon size={19} /></div>
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
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (query.trim()) params.set("q", query.trim());
      if (status) params.set("status", status);
      if (country) params.set("country", country);
      const [stats, jobRows, boardRows, prefs, catalogData] = await Promise.all([
        request(\`\${API}/monitoring/status\`),
        request(\`\${API}/jobs?\${params.toString()}\`),
        request(\`\${API}/monitoring/boards\`),
        request(\`\${API}/preferences\`),
      ]);
      setSummary(stats);
      setJobs(jobRows);
      setBoards(boardRows);
      setPreferences(prefs);
      setCatalog(catalogData.boards || []);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message || "Could not connect to the API.");
    } finally {
      setLoading(false);
    }
  }, [query, status, country]);

  useEffect(() => { load(); }, [load]);

  const boardFailures = useMemo(() => boards.filter((board) => (board.consecutive_failures || 0) > 0).length, [boards]);

  function toggleBoard(key) {
    setSelectedBoards((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  async function importSelectedBoards() {
    const selections = catalog.filter((board) => selectedBoards.includes(\`\${board.provider}:\${board.slug}\`));
    if (!selections.length) return;
    setImporting(true);
    setImportMessage("");
    try {
      const result = await request(\`\${API}/sources/catalog/import\`, {
        method: "POST",
        body: JSON.stringify(selections.map(({ provider, slug }) => ({ provider, slug }))),
      });
      setImportMessage(\`\${result.imported_count} imported · \${result.skipped_count} already registered · \${result.rejected_count} could not be imported\`);
      setSelectedBoards([]);
      await load();
    } catch (err) {
      setImportMessage(err.message || "Catalog import failed.");
    } finally {
      setImporting(false);
    }
  }

  async function runScan() {
    setScanning(true);
    setError("");
    try {
      await request(\`\${API}/discovery/run\`, { method: "POST" });
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
      <nav><a className="nav-item active"><Activity size={18} /> Overview</a><a className="nav-item" href="#jobs"><BriefcaseBusiness size={18} /> Job matches</a><a className="nav-item" href="#sources"><Globe2 size={18} /> Sources</a></nav>
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
        <div className="profile-copy"><b>Screening profile</b><span>{preferences ? \`India floor ₹\${preferences.india_min_ctc_lpa} LPA · USA floor $\${Number(preferences.usa_min_salary_usd_annual || 0).toLocaleString()} / year · \${preferences.preferred_locations?.join(", ") || "No preferred location"}\` : "Loading your preferences…"}</span></div>
        <span className="profile-tag">Unknown salary → review</span>
      </section>

      <section className="content-section catalog-section">
        <div className="section-heading"><div><p className="eyebrow">GET STARTED</p><h2>Curated employer boards</h2><p>Select public company feeds; each is checked live before registration.</p></div><span className="count-pill">{catalog.length} curated</span></div>
        <div className="catalog-grid">{catalog.map((board) => {
          const key = \`\${board.provider}:\${board.slug}\`;
          const alreadyAdded = boards.some((item) => item.provider === board.provider && item.slug === board.slug);
          return <label className={\`catalog-card \${alreadyAdded ? "catalog-added" : ""}\`} key={key}>
            <input type="checkbox" checked={alreadyAdded || selectedBoards.includes(key)} disabled={alreadyAdded || importing} onChange={() => toggleBoard(key)} />
            <span className="catalog-card-copy"><b>{board.company_name}</b><small>{board.provider} · {board.market}</small><a href={board.careers_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Careers page <ArrowUpRight size={12} /></a></span>
            {alreadyAdded && <span className="added-label">Added</span>}
          </label>;
        })}</div>
        <div className="catalog-actions"><span>{importMessage || "Import verifies the selected public feed and saves only reachable boards."}</span><button className="button primary" onClick={importSelectedBoards} disabled={!selectedBoards.length || importing}>{importing ? "Checking feeds…" : \`Import selected (\${selectedBoards.length})\`}</button></div>
      </section>

      <section className="content-section" id="jobs">
        <div className="section-heading"><div><p className="eyebrow">OPPORTUNITIES</p><h2>Job inbox</h2><p>Review discovered roles and open the original employer application page.</p></div><span className="count-pill">{jobs.length} shown</span></div>
        <div className="filters">
          <label className="search-box"><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title, company, skills or location" /></label>
          <label className="select-box"><Filter size={16} /><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option value="matched">Matched</option><option value="review">Needs review</option><option value="skipped">Skipped</option></select></label>
          <label className="select-box"><Globe2 size={16} /><select value={country} onChange={(e) => setCountry(e.target.value)}><option value="">All markets</option><option value="India">India</option><option value="USA">USA</option><option value="UK">UK</option><option value="Canada">Canada</option><option value="Australia">Australia</option></select></label>
        </div>
        {loading ? <div className="empty-state"><LoaderCircle className="spin" size={24} /> Loading jobs…</div> : jobs.length === 0 ? <div className="empty-state"><BriefcaseBusiness size={26} /><b>No jobs found yet</b><span>Run discovery after adding employer boards, or adjust your filters.</span></div> :
          <div className="job-list">{jobs.map((job) => <article className="job-card" key={job.source_job_id}>
            <div className="company-avatar">{(job.company || "?").slice(0, 1).toUpperCase()}</div>
            <div className="job-main"><div className="job-title-row"><h3>{job.title}</h3><span className={\`status-badge \${statusClass(job.screening?.status)}\`}>{job.screening?.status || "unscored"}</span></div>
              <div className="job-company"><Building2 size={14} /> {job.company} <span>·</span><Globe2 size={14} /> {job.location || job.country || "Location not specified"}</div>
              <div className="job-meta"><span>{job.source}</span><span><Clock3 size={13} /> {formatDate(job.posted_at)}</span>{job.salary_min || job.salary_max ? <span>{job.salary_currency || ""} {job.salary_min ?? "—"}–{job.salary_max ?? "—"} {job.salary_period || ""}</span> : <span>Salary not listed</span>}</div>
              {job.screening?.reasons?.length > 0 && <p className="job-reason">{job.screening.reasons.slice(0, 2).join(" · ")}</p>}
            </div>
            <a className="open-job" href={job.apply_url} target="_blank" rel="noreferrer" aria-label={\`Open \${job.title}\`}><ExternalLink size={17} /></a>
          </article>)}</div>}
        <p className="list-footnote">Showing up to 100 latest jobs. Listings link to their original source; verify details before applying.</p>
      </section>

      <section className="content-section" id="sources">
        <div className="section-heading"><div><p className="eyebrow">DISCOVERY NETWORK</p><h2>Source health</h2><p>Recent check status for your registered public job feeds.</p></div><span className="count-pill">{boards.length} sources</span></div>
        {boards.length === 0 ? <div className="empty-state compact">No sources registered yet.</div> : <div className="source-table">
          <div className="source-row source-head"><span>Employer / feed</span><span>Provider</span><span>Last scan</span><span>Jobs found</span><span>Status</span></div>
          {boards.map((board) => <div className="source-row" key={board.id || \`\${board.provider}-\${board.slug}\`}>
            <b>{board.company_name}</b><span className="provider-name">{board.provider}</span><span>{formatDate(board.last_checked_at)}</span><span>{board.last_job_count ?? "—"}</span>
            <span className={board.consecutive_failures ? "health-bad" : board.last_success_at ? "health-good" : "health-unknown"}>{board.consecutive_failures ? \`\${board.consecutive_failures} failures\` : board.last_success_at ? "Healthy" : "Not checked"}</span>
          </div>)}
        </div>}
      </section>
      <footer className="footer"><span>AI Job Hunter · Built around permitted public job feeds</span><span>{lastUpdated ? \`Updated \${lastUpdated.toLocaleTimeString()}\` : "Waiting for API"}</span></footer>
    </main>
  </div>;
}