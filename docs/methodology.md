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
