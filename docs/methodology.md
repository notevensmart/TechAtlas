# Methodology

TechAtlas V1 prioritizes transparent, defensible analytics over opaque extraction.

## Data Semantics

The primary demand metric is job postings listed during the selected period. V1 does not claim a posting is currently active unless a future data source supplies repeated observations or close dates.

Trend dates use `listed_at`. Import timestamps are used only for freshness and audit status.

## Skill Extraction

Skills are detected with a YAML taxonomy. Matching is case-insensitive and whole-word by default. Ambiguous skills such as `Go`, `R`, and `Spark` use custom case-sensitive regex rules to reduce false positives.

The taxonomy includes about 70 skills across:

- language
- frontend
- backend
- cloud
- database
- devops
- data
- AI/ML
- testing
- tooling

AI/ML and GenAI terms are first-class, including LLMs, RAG, embeddings, vector databases, LangChain, PyTorch, TensorFlow, scikit-learn, and MLOps.

## Normalization

V1 normalizes:

- location into Australian city buckets, Remote, or Other
- work mode into remote, hybrid, onsite, or unknown
- seniority into grad, junior, mid, senior, or unknown
- role family into a compact product taxonomy
- visible salaries into annual AUD where feasible

Unknown values remain unknown rather than being guessed.

## Salary Guardrails

Salary is stored only when explicitly visible in imported data. Skill salary comparisons are displayed only when at least 10 salary-bearing listings exist for that skill under the selected filters.

## Source Compliance

TechAtlas ships with a source-agnostic importer rather than a default web crawler. This keeps the project defensible as source terms, robots rules, and access policies change.

Crawler logic, when used, starts from explicit seed URLs, obeys `robots.txt`, rate limits requests, and extracts only structured `JobPosting` data from HTML pages. Job-board-specific crawling should only be added when permission and source rules are clear.

## Recent Data Source

For recent production-style data, the recommended adapter is JobDataAPI. It provides API-authenticated current job listings with title, company, location, description, published date, salary, remote/work-mode, and pagination fields. TechAtlas maps those records into the same canonical import contract used by CSV/JSONL files.

## Market Signals V1

Market Signals V1 turns postings into recruiter and candidate signals with deterministic rules. It does not use LLMs, personal profiles, hidden embeddings, or synthetic advice.

### Recruiter Signals

Recruiter signals answer: what does this market data say about demand and hiring difficulty?

The recruiter view groups matching postings by skill cluster and role archetype, then reports demand, city concentration, seniority skew, period-over-period momentum, and a hiring difficulty proxy. The output is meant to support market sizing and hiring planning, not to replace compensation benchmarking or recruiter judgment.

### Candidate Signals

Candidate signals answer: what does this market data say about target roles and skills that matter together?

The candidate view reports opportunity scores, common role pathways, core skills, adjacent skills, stretch skills, related archetypes, and deterministic market notes. The output is not personalized to an individual profile. It is a market-level guide to visible posting patterns.

### Skill Clusters

Skill clusters are fixed rule tables. A posting can belong to more than one cluster when its detected skills or title/description text match the cluster strongly enough.

- Modern Data Stack: SQL, Python, dbt, Snowflake, Databricks, Airflow
- Cloud Platform Engineering: AWS, Azure, GCP, Kubernetes, Terraform, Docker, CI/CD
- Frontend Product Engineering: TypeScript, JavaScript, React, Next.js, CSS
- Backend Services: Python, Node.js, Java, C#, .NET, REST APIs, Microservices
- AI Engineering: Machine Learning, LLMs, RAG, OpenAI API, Python, Vector Databases
- Cyber / Security Engineering: Security, IAM, SIEM, SOC, Cloud Security, Python
- Analytics / BI: SQL, Power BI, Tableau, Excel, dbt
- Mobile Engineering: iOS, Android, React Native, Swift, Kotlin

Common shared skills such as Python and SQL do not, by themselves, force every posting into every cluster that mentions them. A cluster match is strongest when a distinctive skill appears, at least two cluster skills appear together, or the title/role text supports that cluster.

### Archetype Inference

Role archetypes are inferred from ordered rules over title, description, normalized role family, and detected skills. More specific patterns are evaluated before broad software categories. For example, cloud security is evaluated before general cloud infrastructure, and AI product engineering is evaluated before generic backend services when LLM/RAG/OpenAI patterns are visible.

Supported archetypes are:

- AI Product Engineer
- Machine Learning Engineer
- Data Platform Engineer
- Analytics Engineer
- Cloud Infrastructure Engineer
- Cloud Security Engineer
- Full-stack Product Engineer
- Frontend Product Engineer
- Backend Services Engineer
- DevOps / SRE Engineer
- Cyber Security Analyst
- BI / Reporting Analyst
- Other / Unclear

### Demand Momentum

Momentum compares the selected period with the previous equivalent period using `listed_at`, not `imported_at`.

Returned fields are:

- `current_count`
- `previous_count`
- `delta_count`
- `delta_pct`
- `momentum`: `rising`, `stable`, `falling`, or `new`

For `days=all`, momentum uses the latest 30-day window against the previous 30-day window because an all-time period has no equivalent previous all-time period.

### Hiring Difficulty Score

The recruiter difficulty score is a transparent 0-100 proxy. It increases when:

- a larger share of matching listings are senior-level
- the segment is AI, security, cloud, or data-platform specialized
- listings contain more required or inferred skills
- the segment is rare relative to the selected market
- salary appears often enough to increase confidence in the proxy

Labels are `low`, `moderate`, `high`, and `very high`. Every score includes `reasons` describing the factors that moved it.

### Candidate Opportunity Score

The candidate opportunity score is a transparent 0-100 proxy. It increases when:

- demand is higher within the selected market
- more listings are grad, junior, or mid-level
- the skill cluster is clear rather than ambiguous
- adjacent skills form an obvious pathway

It decreases when the segment is heavily senior-only. Labels are `accessible`, `competitive`, `advanced`, and `niche`. Every score includes `reasons`.

### Skill Pathways

Pathways combine fixed role blueprints with observed adjacent skills in current postings. For each archetype TechAtlas returns:

- core skills
- common adjacent skills
- stretch skills
- related archetypes
- the candidate opportunity score for that archetype

Example: Analytics Engineer uses SQL, dbt, and Python as core skills, then looks for adjacent market signals such as Snowflake, Power BI, and Airflow.

### Plain-English Notes

Market notes are deterministic templates over the computed signals. They are not generated by an LLM. Examples include concentration notes, skill-pair notes, momentum notes, foundation-skill notes, and opportunity-pathway notes.

### Limitations

TechAtlas converts available postings into useful signals; it does not claim perfect market truth.

Known limitations:

- Posting volume is not the same as filled-role demand.
- The same vacancy can appear across multiple sources if the source does not provide stable IDs.
- Skill extraction depends on the visible posting text and taxonomy coverage.
- Archetypes are practical buckets, not official job families.
- Difficulty and opportunity scores are proxies, not guarantees.
- Salary-bearing listings increase confidence only when salary is visible and normalized.
- Candidate signals are not personalized recommendations.
