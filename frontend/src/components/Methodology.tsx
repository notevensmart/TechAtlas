export function Methodology() {
  return (
    <div className="grid gap-4">
      <section className="rounded border border-line bg-white p-5">
        <h2 className="text-base font-semibold text-ink">Methodology</h2>
        <div className="mt-3 grid gap-3 text-sm leading-6 text-slate-700">
          <p>
            TechAtlas V1 is import-first. It accepts permitted CSV or JSONL job-posting exports, validates each row,
            normalizes job metadata, extracts skills with a versioned taxonomy, and computes analytics from listed
            posting dates.
          </p>
          <p>
            The dashboard reports posting demand during the selected period. It does not claim live active-listing
            status unless a future source supplies repeated observations or close dates.
          </p>
          <p>
            Skill extraction is rule-based by design: aliases and explicit regular-expression rules are auditable,
            easy to review, and safer for portfolio analytics than opaque extraction.
          </p>
        </div>
      </section>
      <section className="rounded border border-line bg-white p-5">
        <h2 className="text-base font-semibold text-ink">Market Signals</h2>
        <div className="mt-3 grid gap-3 text-sm leading-6 text-slate-700">
          <p>
            Signals are deterministic rules over postings, detected skills, titles, descriptions, seniority, city,
            salary visibility, and listed dates. They do not use LLM-generated advice.
          </p>
          <p>
            Recruiter signals summarize demand concentration, momentum, seniority skew, and hiring difficulty.
            Candidate signals summarize opportunity, role pathways, adjacent skills, and stretch skills.
          </p>
          <p>
            Difficulty and opportunity scores are transparent proxies. Each score includes reasons so the signal can be
            inspected rather than accepted as perfect market truth.
          </p>
        </div>
      </section>
      <section className="rounded border border-line bg-white p-5">
        <h2 className="text-base font-semibold text-ink">Roadmap Layers</h2>
        <div className="mt-3 grid gap-2 text-sm text-slate-700">
          <p>1. Market Demand: posting counts, growth, city and role breakdowns.</p>
          <p>2. Skill Relationships: co-occurrence now, graph explorer later.</p>
          <p>3. Career Pathways: rule-based market pathways now, personalization later.</p>
          <p>4. Salary and Scarcity: guarded salary views now, leverage scoring later.</p>
          <p>5. Technology Evolution: trend history now, timeline playback later.</p>
        </div>
      </section>
    </div>
  );
}
