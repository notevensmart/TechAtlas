from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Listing, ListingSkill, Skill
from app.schemas.api import (
    CandidateOpportunitySignal,
    MarketNote,
    MarketSignalsSummary,
    MomentumSignal,
    RecruiterDifficultySignal,
    RoleArchetypeSignal,
    SkillClusterSignal,
    SkillPathwaySignal,
)
from app.services.analytics import filtered_listing_query


ROLE_ARCHETYPES = (
    "AI Product Engineer",
    "Machine Learning Engineer",
    "Data Platform Engineer",
    "Analytics Engineer",
    "Cloud Infrastructure Engineer",
    "Cloud Security Engineer",
    "Full-stack Product Engineer",
    "Frontend Product Engineer",
    "Backend Services Engineer",
    "DevOps / SRE Engineer",
    "Cyber Security Analyst",
    "BI / Reporting Analyst",
    "Other / Unclear",
)


@dataclass(frozen=True)
class SkillClusterDefinition:
    name: str
    skills: tuple[str, ...]
    title_hints: tuple[str, ...] = ()
    distinctive_skills: tuple[str, ...] = ()


SKILL_CLUSTERS: tuple[SkillClusterDefinition, ...] = (
    SkillClusterDefinition(
        name="Modern Data Stack",
        skills=("SQL", "Python", "dbt", "Snowflake", "Databricks", "Airflow"),
        title_hints=("data engineer", "analytics engineer", "data platform"),
        distinctive_skills=("dbt", "Snowflake", "Databricks", "Airflow"),
    ),
    SkillClusterDefinition(
        name="Cloud Platform Engineering",
        skills=("AWS", "Azure", "GCP", "Kubernetes", "Terraform", "Docker", "CI/CD"),
        title_hints=("cloud", "platform engineer", "infrastructure", "devops", "sre", "site reliability"),
        distinctive_skills=("AWS", "Azure", "GCP", "Kubernetes", "Terraform", "Docker", "CI/CD"),
    ),
    SkillClusterDefinition(
        name="Frontend Product Engineering",
        skills=("TypeScript", "JavaScript", "React", "Next.js", "CSS"),
        title_hints=("frontend", "front-end", "front end", "product engineer"),
        distinctive_skills=("TypeScript", "React", "Next.js"),
    ),
    SkillClusterDefinition(
        name="Backend Services",
        skills=("Python", "Node.js", "Java", "C#", ".NET", "REST APIs", "Microservices"),
        title_hints=("backend", "back-end", "back end", "api engineer", "services engineer"),
        distinctive_skills=("Node.js", "Java", "C#", ".NET", "REST APIs", "Microservices"),
    ),
    SkillClusterDefinition(
        name="AI Engineering",
        skills=("Machine Learning", "LLMs", "RAG", "OpenAI API", "Python", "Vector Databases"),
        title_hints=("ai engineer", "machine learning", "ml engineer", "genai", "llm"),
        distinctive_skills=("Machine Learning", "LLMs", "RAG", "OpenAI API", "Vector Databases"),
    ),
    SkillClusterDefinition(
        name="Cyber / Security Engineering",
        skills=("Security", "IAM", "SIEM", "SOC", "Cloud Security", "Python"),
        title_hints=("security", "cyber", "soc", "iam"),
        distinctive_skills=("Security", "IAM", "SIEM", "SOC", "Cloud Security"),
    ),
    SkillClusterDefinition(
        name="Analytics / BI",
        skills=("SQL", "Power BI", "Tableau", "Excel", "dbt"),
        title_hints=("analyst", "analytics", "bi ", "reporting"),
        distinctive_skills=("Power BI", "Tableau", "Excel", "dbt"),
    ),
    SkillClusterDefinition(
        name="Mobile Engineering",
        skills=("iOS", "Android", "React Native", "Swift", "Kotlin"),
        title_hints=("mobile", "ios", "android", "react native"),
        distinctive_skills=("iOS", "Android", "React Native", "Swift", "Kotlin"),
    ),
)


TERM_ALIASES: dict[str, tuple[str, ...]] = {
    ".NET": (".net", "dotnet", "asp.net", "asp net"),
    "AI": ("ai", "artificial intelligence", "genai", "generative ai"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure", "microsoft azure"),
    "C#": ("c#", "c sharp"),
    "CI/CD": ("ci/cd", "cicd", "ci cd", "github actions", "gitlab ci", "jenkins", "buildkite"),
    "Cloud Security": ("cloud security",),
    "CSS": ("css", "css3"),
    "Databricks": ("databricks",),
    "dbt": ("dbt", "data build tool"),
    "Docker": ("docker",),
    "Excel": ("excel", "microsoft excel"),
    "GCP": ("gcp", "google cloud", "google cloud platform"),
    "IAM": ("iam", "identity and access", "identity access management"),
    "iOS": ("ios", "iphone"),
    "JavaScript": ("javascript", "js", "ecmascript"),
    "Kubernetes": ("kubernetes", "k8s", "kube"),
    "LLMs": ("llm", "llms", "large language model", "large language models"),
    "Machine Learning": ("machine learning", "ml", "predictive modelling", "predictive modeling"),
    "Microservices": ("microservices", "microservice architecture"),
    "Next.js": ("next.js", "nextjs", "next js"),
    "Node.js": ("node.js", "nodejs", "node js", "node"),
    "OpenAI API": ("openai api", "openai", "chatgpt api"),
    "Power BI": ("power bi", "powerbi"),
    "RAG": ("rag", "retrieval augmented generation", "retrieval-augmented generation"),
    "React": ("react", "react.js", "reactjs"),
    "React Native": ("react native",),
    "REST APIs": ("rest api", "rest apis", "restful api", "restful apis"),
    "Security": ("security", "cybersecurity", "cyber security"),
    "SIEM": ("siem",),
    "SOC": ("soc", "security operations centre", "security operations center"),
    "SQL": ("sql", "structured query language"),
    "TypeScript": ("typescript", "ts"),
    "Vector Databases": ("vector database", "vector databases", "pgvector", "pinecone", "weaviate", "chroma"),
}


PATHWAY_BLUEPRINTS: dict[str, dict[str, list[str] | str]] = {
    "AI Product Engineer": {
        "cluster": "AI Engineering",
        "core": ["Python", "LLMs", "RAG", "REST APIs"],
        "adjacent": ["OpenAI API", "Vector Databases", "TypeScript", "React"],
        "stretch": ["MLOps", "Evaluation", "Cloud Security"],
        "related": ["Machine Learning Engineer", "Backend Services Engineer", "Full-stack Product Engineer"],
    },
    "Machine Learning Engineer": {
        "cluster": "AI Engineering",
        "core": ["Python", "Machine Learning", "SQL"],
        "adjacent": ["PyTorch", "TensorFlow", "Databricks", "MLOps"],
        "stretch": ["LLMs", "RAG", "Vector Databases"],
        "related": ["AI Product Engineer", "Data Platform Engineer"],
    },
    "Data Platform Engineer": {
        "cluster": "Modern Data Stack",
        "core": ["Python", "SQL", "Airflow"],
        "adjacent": ["Snowflake", "Databricks", "Terraform", "Spark"],
        "stretch": ["MLOps", "Kubernetes", "Streaming"],
        "related": ["Analytics Engineer", "Cloud Infrastructure Engineer"],
    },
    "Analytics Engineer": {
        "cluster": "Analytics / BI",
        "core": ["SQL", "dbt", "Python"],
        "adjacent": ["Snowflake", "Power BI", "Airflow"],
        "stretch": ["Databricks", "MLOps"],
        "related": ["Data Platform Engineer", "BI / Reporting Analyst"],
    },
    "Cloud Infrastructure Engineer": {
        "cluster": "Cloud Platform Engineering",
        "core": ["AWS", "Terraform", "Kubernetes"],
        "adjacent": ["Docker", "CI/CD", "Azure", "GCP"],
        "stretch": ["Cloud Security", "SRE", "Cost Optimisation"],
        "related": ["DevOps / SRE Engineer", "Cloud Security Engineer"],
    },
    "Cloud Security Engineer": {
        "cluster": "Cyber / Security Engineering",
        "core": ["Cloud Security", "IAM", "AWS"],
        "adjacent": ["Azure", "Terraform", "SIEM"],
        "stretch": ["Kubernetes Security", "Threat Modelling"],
        "related": ["Cyber Security Analyst", "Cloud Infrastructure Engineer"],
    },
    "Full-stack Product Engineer": {
        "cluster": "Frontend Product Engineering",
        "core": ["TypeScript", "React", "REST APIs"],
        "adjacent": ["Node.js", "Next.js", "SQL"],
        "stretch": ["Cloud", "CI/CD", "Observability"],
        "related": ["Frontend Product Engineer", "Backend Services Engineer"],
    },
    "Frontend Product Engineer": {
        "cluster": "Frontend Product Engineering",
        "core": ["React", "TypeScript", "CSS"],
        "adjacent": ["Next.js", "JavaScript", "Testing"],
        "stretch": ["Node.js", "Accessibility", "Design Systems"],
        "related": ["Full-stack Product Engineer"],
    },
    "Backend Services Engineer": {
        "cluster": "Backend Services",
        "core": ["Python", "REST APIs", "SQL"],
        "adjacent": ["Node.js", "Java", ".NET", "Microservices"],
        "stretch": ["Kubernetes", "Event Streaming", "Cloud Security"],
        "related": ["Full-stack Product Engineer", "Data Platform Engineer"],
    },
    "DevOps / SRE Engineer": {
        "cluster": "Cloud Platform Engineering",
        "core": ["Kubernetes", "Terraform", "CI/CD"],
        "adjacent": ["AWS", "Docker", "Linux"],
        "stretch": ["Observability", "Incident Management", "Platform Engineering"],
        "related": ["Cloud Infrastructure Engineer", "Cloud Security Engineer"],
    },
    "Cyber Security Analyst": {
        "cluster": "Cyber / Security Engineering",
        "core": ["Security", "SIEM", "SOC"],
        "adjacent": ["IAM", "Python", "Cloud Security"],
        "stretch": ["Threat Hunting", "Detection Engineering"],
        "related": ["Cloud Security Engineer"],
    },
    "BI / Reporting Analyst": {
        "cluster": "Analytics / BI",
        "core": ["SQL", "Power BI", "Excel"],
        "adjacent": ["Tableau", "dbt", "Python"],
        "stretch": ["Analytics Engineering", "Data Modelling"],
        "related": ["Analytics Engineer"],
    },
    "Other / Unclear": {
        "cluster": "",
        "core": [],
        "adjacent": [],
        "stretch": [],
        "related": [],
    },
}


SPECIALIZED_ARCHETYPES = {
    "AI Product Engineer",
    "Machine Learning Engineer",
    "Data Platform Engineer",
    "Cloud Infrastructure Engineer",
    "Cloud Security Engineer",
    "DevOps / SRE Engineer",
    "Cyber Security Analyst",
}


SPECIALIZED_CLUSTERS = {
    "AI Engineering",
    "Cyber / Security Engineering",
    "Cloud Platform Engineering",
    "Modern Data Stack",
}


@dataclass(frozen=True)
class ListingSignalRecord:
    id: int
    title: str
    description: str
    city: str
    role_family: str
    experience_level: str
    work_mode: str
    listed_at: datetime | None
    salary_mid_annual: int | None
    skills: tuple[str, ...]


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _record_text(record: ListingSignalRecord) -> str:
    return " ".join([record.title, record.description, record.role_family]).lower()


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = phrase.strip().lower()
    if not phrase:
        return False
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    prefix = r"(?<![a-z0-9])" if phrase[0].isalnum() else ""
    suffix = r"(?![a-z0-9])" if phrase[-1].isalnum() else ""
    return re.search(f"{prefix}{escaped}{suffix}", text) is not None


def _term_aliases(term: str) -> tuple[str, ...]:
    return TERM_ALIASES.get(term, (term,))


def has_signal_term(record: ListingSignalRecord, term: str) -> bool:
    normalized_skills = {_norm(skill) for skill in record.skills}
    if _norm(term) in normalized_skills:
        return True
    text = _record_text(record)
    return any(_contains_phrase(text, alias) for alias in _term_aliases(term))


def _has_any(record: ListingSignalRecord, terms: tuple[str, ...] | list[str] | set[str]) -> bool:
    return any(has_signal_term(record, term) for term in terms)


def _text_has_any(record: ListingSignalRecord, phrases: tuple[str, ...] | list[str] | set[str]) -> bool:
    text = _record_text(record)
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def enriched_skills(record: ListingSignalRecord) -> set[str]:
    signal_terms = {skill for cluster in SKILL_CLUSTERS for skill in cluster.skills}
    for blueprint in PATHWAY_BLUEPRINTS.values():
        for key in ("core", "adjacent", "stretch"):
            signal_terms.update(str(skill) for skill in blueprint[key])
    return set(record.skills) | {term for term in signal_terms if has_signal_term(record, term)}


def skill_clusters_for_record(record: ListingSignalRecord) -> list[str]:
    clusters: list[str] = []
    for cluster in SKILL_CLUSTERS:
        matched = [skill for skill in cluster.skills if has_signal_term(record, skill)]
        if not matched:
            continue
        has_distinctive = any(skill in matched for skill in cluster.distinctive_skills)
        has_title_hint = _text_has_any(record, cluster.title_hints)
        if has_distinctive or len(matched) >= 2 or has_title_hint:
            clusters.append(cluster.name)
    return clusters


def infer_role_archetype(
    title: str,
    description: str = "",
    skills: tuple[str, ...] | list[str] | set[str] | None = None,
    role_family: str | None = None,
) -> str:
    record = ListingSignalRecord(
        id=0,
        title=title,
        description=description,
        city="",
        role_family=role_family or "",
        experience_level="unknown",
        work_mode="unknown",
        listed_at=None,
        salary_mid_annual=None,
        skills=tuple(skills or ()),
    )

    has_ai = _has_any(record, ("AI", "LLMs", "RAG", "OpenAI API", "Vector Databases"))
    has_ml = _has_any(record, ("Machine Learning", "PyTorch", "TensorFlow", "scikit-learn", "MLOps"))
    has_security = _has_any(record, ("Security", "IAM", "SIEM", "SOC", "Cloud Security"))
    has_cloud = _has_any(record, ("AWS", "Azure", "GCP", "Kubernetes", "Terraform", "Docker", "CI/CD"))
    has_frontend = _has_any(record, ("React", "TypeScript", "JavaScript", "Next.js", "CSS"))
    has_backend = _has_any(record, ("Python", "Node.js", "Java", "C#", ".NET", "REST APIs", "Microservices"))
    has_data_platform = _has_any(record, ("Snowflake", "Databricks", "Airflow", "Spark", "Kafka"))
    has_bi = _has_any(record, ("Power BI", "Tableau", "Excel"))

    if has_security and (has_cloud or _text_has_any(record, ("cloud security",))):
        return "Cloud Security Engineer"
    if has_security and _text_has_any(record, ("analyst", "soc", "siem", "cyber")):
        return "Cyber Security Analyst"
    if has_ai and (_text_has_any(record, ("product engineer", "ai engineer", "llm", "rag", "genai")) or has_frontend or has_backend):
        return "AI Product Engineer"
    if has_ml or _text_has_any(record, ("machine learning engineer", "ml engineer")):
        return "Machine Learning Engineer"
    if _text_has_any(record, ("analytics engineer",)) or (has_signal_term(record, "SQL") and has_signal_term(record, "dbt")):
        return "Analytics Engineer"
    if has_data_platform or _text_has_any(record, ("data engineer", "data platform")):
        return "Data Platform Engineer"
    if _text_has_any(record, ("devops", "sre", "site reliability")):
        return "DevOps / SRE Engineer"
    if has_cloud and _text_has_any(record, ("cloud", "platform", "infrastructure")):
        return "Cloud Infrastructure Engineer"
    if _text_has_any(record, ("full-stack", "fullstack", "full stack")) or (has_frontend and has_backend):
        return "Full-stack Product Engineer"
    if has_frontend or _text_has_any(record, ("frontend", "front-end", "front end")):
        return "Frontend Product Engineer"
    if has_backend or _text_has_any(record, ("backend", "back-end", "back end", "api engineer")):
        return "Backend Services Engineer"
    if has_bi or _text_has_any(record, ("bi analyst", "reporting analyst", "business intelligence")):
        return "BI / Reporting Analyst"
    return "Other / Unclear"


def classify_momentum(current_count: int, previous_count: int) -> tuple[float | None, str]:
    if current_count > 0 and previous_count == 0:
        return None, "new"
    if current_count == 0 and previous_count == 0:
        return 0.0, "stable"
    delta_pct = round(((current_count - previous_count) / previous_count) * 100, 1)
    if delta_pct >= 15:
        return delta_pct, "rising"
    if delta_pct <= -15:
        return delta_pct, "falling"
    return delta_pct, "stable"


def build_momentum_signal(name: str, signal_type: str, current_count: int, previous_count: int) -> MomentumSignal:
    delta_pct, momentum = classify_momentum(current_count, previous_count)
    return MomentumSignal(
        name=name,
        signal_type=signal_type,
        current_count=current_count,
        previous_count=previous_count,
        delta_count=current_count - previous_count,
        delta_pct=delta_pct,
        momentum=momentum,
    )


def _pct(part: int, total: int) -> float:
    return round((part / total) * 100, 1) if total else 0.0


def _average(values: list[int]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _difficulty_label(score: int) -> str:
    if score >= 75:
        return "very high"
    if score >= 55:
        return "high"
    if score >= 35:
        return "moderate"
    return "low"


def score_recruiter_difficulty(
    records: list[ListingSignalRecord],
    *,
    total_records: int,
    name: str,
    signal_type: str,
    specialized: bool,
) -> RecruiterDifficultySignal:
    if not records:
        return RecruiterDifficultySignal(
            name=name,
            signal_type=signal_type,
            difficulty_score=0,
            difficulty_label="low",
            reasons=["No matching postings under the selected filters."],
            senior_share_pct=0,
            average_required_skills=0,
            salary_confidence_pct=0,
        )

    senior_count = sum(1 for record in records if record.experience_level == "senior")
    salary_count = sum(1 for record in records if record.salary_mid_annual is not None)
    skill_counts = [len(enriched_skills(record)) for record in records]
    senior_share = _pct(senior_count, len(records))
    salary_share = _pct(salary_count, len(records))
    average_skills = _average(skill_counts)

    score = 18
    score += round(senior_share * 0.32)
    if specialized:
        score += 16
    if average_skills >= 6:
        score += 18
    elif average_skills >= 4:
        score += 10
    elif average_skills >= 2:
        score += 4
    rarity_threshold = max(3, round(total_records * 0.08))
    if len(records) <= rarity_threshold:
        score += 14
    elif len(records) <= max(5, round(total_records * 0.15)):
        score += 7
    if salary_share >= 15:
        score += 5

    reasons = [
        f"{senior_share}% of matching listings are senior-level.",
        f"Matching listings show an average of {average_skills} detected or inferred skills.",
    ]
    if specialized:
        reasons.append("Specialized AI, security, cloud, or data-platform demand raises hiring complexity.")
    if len(records) <= rarity_threshold:
        reasons.append("The segment is relatively rare in the selected market, reducing the visible hiring pool.")
    if salary_share >= 15:
        reasons.append(f"Salary is visible on {salary_share}% of matching listings, improving confidence in this proxy.")

    score = max(0, min(100, score))
    return RecruiterDifficultySignal(
        name=name,
        signal_type=signal_type,
        difficulty_score=score,
        difficulty_label=_difficulty_label(score),
        reasons=reasons,
        senior_share_pct=senior_share,
        average_required_skills=average_skills,
        salary_confidence_pct=salary_share,
    )


def _opportunity_label(score: int, records: list[ListingSignalRecord], senior_share: float, total_records: int) -> str:
    if not records or (len(records) <= 2 and total_records >= 5) or score < 30:
        return "niche"
    entry_mid_share = _pct(
        sum(1 for record in records if record.experience_level in {"grad", "junior", "mid"}),
        len(records),
    )
    if senior_share >= 65 and entry_mid_share < 35:
        return "advanced"
    if score >= 65:
        return "accessible"
    return "competitive"


def score_candidate_opportunity(
    records: list[ListingSignalRecord],
    *,
    total_records: int,
    name: str,
    signal_type: str,
    adjacent_skill_count: int,
    clear_cluster: bool,
) -> CandidateOpportunitySignal:
    if not records:
        return CandidateOpportunitySignal(
            name=name,
            signal_type=signal_type,
            opportunity_score=0,
            opportunity_label="niche",
            reasons=["No matching postings under the selected filters."],
            demand_count=0,
            entry_mid_share_pct=0,
            senior_share_pct=0,
            adjacent_skill_count=0,
        )

    entry_mid_count = sum(1 for record in records if record.experience_level in {"grad", "junior", "mid"})
    senior_count = sum(1 for record in records if record.experience_level == "senior")
    entry_mid_share = _pct(entry_mid_count, len(records))
    senior_share = _pct(senior_count, len(records))
    demand_share = _pct(len(records), total_records)

    demand_component = min(35, round(demand_share * 0.9 + min(len(records), 25) * 0.6))
    entry_component = round(entry_mid_share * 0.25)
    cluster_component = 10 if clear_cluster else 3
    pathway_component = min(15, adjacent_skill_count * 3)
    senior_penalty = round(max(0, senior_share - 45) * 0.35)

    score = max(0, min(100, 25 + demand_component + entry_component + cluster_component + pathway_component - senior_penalty))
    reasons = [
        f"{len(records)} matching postings represent {demand_share}% of the selected market.",
        f"{entry_mid_share}% of matching listings are grad, junior, or mid-level.",
    ]
    if clear_cluster:
        reasons.append("The role has a clear skill cluster, reducing ambiguity for candidates.")
    else:
        reasons.append("The role spans mixed or unclear skill clusters, increasing pathway ambiguity.")
    if senior_share > 45:
        reasons.append(f"{senior_share}% senior concentration lowers accessibility.")
    if adjacent_skill_count:
        reasons.append(f"{adjacent_skill_count} adjacent skills form a visible learning pathway.")

    return CandidateOpportunitySignal(
        name=name,
        signal_type=signal_type,
        opportunity_score=score,
        opportunity_label=_opportunity_label(score, records, senior_share, total_records),
        reasons=reasons,
        demand_count=len(records),
        entry_mid_share_pct=entry_mid_share,
        senior_share_pct=senior_share,
        adjacent_skill_count=adjacent_skill_count,
    )


def _latest_listing_at(session: Session) -> datetime | None:
    return session.scalar(select(func.max(Listing.listed_at)))


def _window_days(days: str | None) -> int:
    if days == "all":
        return 30
    try:
        return max(1, int(days or 30))
    except ValueError:
        return 30


def _load_listing_records(
    session: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    **filters,
) -> list[ListingSignalRecord]:
    query = filtered_listing_query(session, **filters).distinct()
    if start is not None:
        query = query.where(Listing.listed_at >= start)
    if end is not None:
        query = query.where(Listing.listed_at <= end)
    listings = session.scalars(query.order_by(Listing.listed_at.desc(), Listing.id.desc())).all()
    listing_ids = [listing.id for listing in listings]
    skills_by_listing: dict[int, list[str]] = defaultdict(list)
    if listing_ids:
        rows = session.execute(
            select(ListingSkill.listing_id, Skill.name)
            .join(Skill, Skill.id == ListingSkill.skill_id)
            .where(ListingSkill.listing_id.in_(listing_ids))
            .order_by(Skill.name.asc())
        ).all()
        for listing_id, skill_name in rows:
            skills_by_listing[listing_id].append(skill_name)

    return [
        ListingSignalRecord(
            id=listing.id,
            title=listing.title or "",
            description=listing.description_raw or "",
            city=listing.city or "Other",
            role_family=listing.role_family or "Other/Unknown",
            experience_level=listing.experience_level or "unknown",
            work_mode=listing.work_mode or "unknown",
            listed_at=listing.listed_at,
            salary_mid_annual=listing.salary_mid_annual,
            skills=tuple(skills_by_listing.get(listing.id, [])),
        )
        for listing in listings
    ]


def _load_momentum_records(session: Session, **filters) -> tuple[list[ListingSignalRecord], list[ListingSignalRecord]]:
    latest = _latest_listing_at(session)
    if latest is None:
        return [], []
    window = _window_days(filters.get("days"))
    current_start = latest - timedelta(days=window - 1)
    previous_start = current_start - timedelta(days=window)
    previous_end = current_start - timedelta(seconds=1)
    period_filters = dict(filters)
    period_filters["days"] = "all"
    current = _load_listing_records(session, start=current_start, end=latest, **period_filters)
    previous = _load_listing_records(session, start=previous_start, end=previous_end, **period_filters)
    return current, previous


def _records_by_cluster(records: list[ListingSignalRecord]) -> dict[str, list[ListingSignalRecord]]:
    grouped: dict[str, list[ListingSignalRecord]] = {cluster.name: [] for cluster in SKILL_CLUSTERS}
    for record in records:
        for cluster_name in skill_clusters_for_record(record):
            grouped[cluster_name].append(record)
    return grouped


def _records_by_archetype(records: list[ListingSignalRecord]) -> dict[str, list[ListingSignalRecord]]:
    grouped: dict[str, list[ListingSignalRecord]] = {name: [] for name in ROLE_ARCHETYPES}
    for record in records:
        grouped[infer_role_archetype(record.title, record.description, record.skills, record.role_family)].append(record)
    return grouped


def _top_skills(records: list[ListingSignalRecord], limit: int = 6) -> list[str]:
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(enriched_skills(record))
    return [skill for skill, _ in counts.most_common(limit)]


def _top_city(records: list[ListingSignalRecord]) -> tuple[str | None, float]:
    if not records:
        return None, 0.0
    city, count = Counter(record.city for record in records).most_common(1)[0]
    return city, _pct(count, len(records))


def _average_skill_count(records: list[ListingSignalRecord]) -> float:
    return _average([len(enriched_skills(record)) for record in records])


def _senior_share(records: list[ListingSignalRecord]) -> float:
    return _pct(sum(1 for record in records if record.experience_level == "senior"), len(records))


def _common_adjacent_skills(archetype: str, records: list[ListingSignalRecord], limit: int = 5) -> list[str]:
    blueprint = PATHWAY_BLUEPRINTS.get(archetype, PATHWAY_BLUEPRINTS["Other / Unclear"])
    core = set(str(skill) for skill in blueprint["core"])
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(skill for skill in enriched_skills(record) if skill not in core)
    adjacent = [skill for skill, _ in counts.most_common(limit)]
    for skill in blueprint["adjacent"]:
        if str(skill) not in adjacent and str(skill) not in core:
            adjacent.append(str(skill))
        if len(adjacent) >= limit:
            break
    return adjacent[:limit]


def _clear_cluster_for_records(records: list[ListingSignalRecord]) -> bool:
    if not records:
        return False
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(skill_clusters_for_record(record))
    if not counts:
        return False
    return counts.most_common(1)[0][1] >= max(1, round(len(records) * 0.45))


def get_cluster_signals(session: Session, **filters) -> list[SkillClusterSignal]:
    current_records = _load_listing_records(session, **filters)
    total = len(current_records)
    current_momentum, previous_momentum = _load_momentum_records(session, **filters)
    current_by_cluster = _records_by_cluster(current_records)
    momentum_by_cluster = _records_by_cluster(current_momentum)
    previous_by_cluster = _records_by_cluster(previous_momentum)
    signals: list[SkillClusterSignal] = []

    for cluster in SKILL_CLUSTERS:
        records = current_by_cluster[cluster.name]
        current_count = len(momentum_by_cluster[cluster.name])
        previous_count = len(previous_by_cluster[cluster.name])
        top_city, concentration = _top_city(records)
        top_skills = _top_skills(records)
        adjacent_count = len([skill for skill in top_skills if skill not in cluster.skills])
        momentum = build_momentum_signal(cluster.name, "cluster", current_count, previous_count)
        signals.append(
            SkillClusterSignal(
                name=cluster.name,
                skills=list(cluster.skills),
                listing_count=len(records),
                share_of_postings_pct=_pct(len(records), total),
                demand_concentration_pct=concentration,
                top_city=top_city,
                top_skills=top_skills,
                senior_share_pct=_senior_share(records),
                average_skills_per_listing=_average_skill_count(records),
                momentum=momentum,
                recruiter_difficulty=score_recruiter_difficulty(
                    records,
                    total_records=total,
                    name=cluster.name,
                    signal_type="cluster",
                    specialized=cluster.name in SPECIALIZED_CLUSTERS,
                ),
                candidate_opportunity=score_candidate_opportunity(
                    records,
                    total_records=total,
                    name=cluster.name,
                    signal_type="cluster",
                    adjacent_skill_count=adjacent_count,
                    clear_cluster=bool(records),
                ),
            )
        )
    return sorted(signals, key=lambda item: (-item.listing_count, item.name))


def get_archetype_signals(session: Session, **filters) -> list[RoleArchetypeSignal]:
    current_records = _load_listing_records(session, **filters)
    total = len(current_records)
    current_momentum, previous_momentum = _load_momentum_records(session, **filters)
    current_by_archetype = _records_by_archetype(current_records)
    momentum_by_archetype = _records_by_archetype(current_momentum)
    previous_by_archetype = _records_by_archetype(previous_momentum)
    signals: list[RoleArchetypeSignal] = []

    for archetype in ROLE_ARCHETYPES:
        records = current_by_archetype[archetype]
        top_city, _ = _top_city(records)
        cluster_counts: Counter[str] = Counter()
        for record in records:
            cluster_counts.update(skill_clusters_for_record(record))
        adjacent = _common_adjacent_skills(archetype, records)
        momentum = build_momentum_signal(
            archetype,
            "archetype",
            len(momentum_by_archetype[archetype]),
            len(previous_by_archetype[archetype]),
        )
        signals.append(
            RoleArchetypeSignal(
                name=archetype,
                listing_count=len(records),
                share_of_postings_pct=_pct(len(records), total),
                top_skills=_top_skills(records),
                top_clusters=[name for name, _ in cluster_counts.most_common(3)],
                top_city=top_city,
                senior_share_pct=_senior_share(records),
                average_skills_per_listing=_average_skill_count(records),
                momentum=momentum,
                recruiter_difficulty=score_recruiter_difficulty(
                    records,
                    total_records=total,
                    name=archetype,
                    signal_type="archetype",
                    specialized=archetype in SPECIALIZED_ARCHETYPES,
                ),
                candidate_opportunity=score_candidate_opportunity(
                    records,
                    total_records=total,
                    name=archetype,
                    signal_type="archetype",
                    adjacent_skill_count=len(adjacent),
                    clear_cluster=_clear_cluster_for_records(records),
                ),
            )
        )
    return sorted(signals, key=lambda item: (-item.listing_count, item.name))


def get_momentum_signals(session: Session, **filters) -> list[MomentumSignal]:
    current_records, previous_records = _load_momentum_records(session, **filters)
    current_clusters = _records_by_cluster(current_records)
    previous_clusters = _records_by_cluster(previous_records)
    current_archetypes = _records_by_archetype(current_records)
    previous_archetypes = _records_by_archetype(previous_records)
    signals: list[MomentumSignal] = []

    for cluster in SKILL_CLUSTERS:
        current_count = len(current_clusters[cluster.name])
        previous_count = len(previous_clusters[cluster.name])
        if current_count or previous_count:
            signals.append(build_momentum_signal(cluster.name, "cluster", current_count, previous_count))
    for archetype in ROLE_ARCHETYPES:
        current_count = len(current_archetypes[archetype])
        previous_count = len(previous_archetypes[archetype])
        if current_count or previous_count:
            signals.append(build_momentum_signal(archetype, "archetype", current_count, previous_count))

    return sorted(signals, key=lambda item: (-abs(item.delta_count), -item.current_count, item.name))


def get_pathway_signals(session: Session, **filters) -> list[SkillPathwaySignal]:
    records = _load_listing_records(session, **filters)
    total = len(records)
    by_archetype = _records_by_archetype(records)
    pathways: list[SkillPathwaySignal] = []

    for archetype in ROLE_ARCHETYPES:
        blueprint = PATHWAY_BLUEPRINTS[archetype]
        archetype_records = by_archetype[archetype]
        adjacent = _common_adjacent_skills(archetype, archetype_records)
        primary_cluster = str(blueprint["cluster"]) or None
        pathways.append(
            SkillPathwaySignal(
                archetype=archetype,
                primary_cluster=primary_cluster,
                demand_count=len(archetype_records),
                core_skills=[str(skill) for skill in blueprint["core"]],
                common_adjacent_skills=adjacent,
                stretch_skills=[str(skill) for skill in blueprint["stretch"]],
                related_archetypes=[str(role) for role in blueprint["related"]],
                opportunity=score_candidate_opportunity(
                    archetype_records,
                    total_records=total,
                    name=archetype,
                    signal_type="archetype",
                    adjacent_skill_count=len(adjacent),
                    clear_cluster=_clear_cluster_for_records(archetype_records),
                ),
            )
        )
    return sorted(pathways, key=lambda item: (-item.demand_count, item.archetype))


def _top_pair(records: list[ListingSignalRecord], required_terms: set[str] | None = None) -> tuple[str, str, int] | None:
    pairs: Counter[tuple[str, str]] = Counter()
    for record in records:
        skills = sorted(enriched_skills(record))
        if required_terms:
            skills = [skill for skill in skills if skill in required_terms]
        for index, skill_a in enumerate(skills):
            for skill_b in skills[index + 1 :]:
                pairs[(skill_a, skill_b)] += 1
    if not pairs:
        return None
    (skill_a, skill_b), count = pairs.most_common(1)[0]
    return skill_a, skill_b, count


def get_market_notes(session: Session, **filters) -> list[MarketNote]:
    records = _load_listing_records(session, **filters)
    if not records:
        return [
            MarketNote(
                audience="recruiter",
                subject="Market",
                signal_type="coverage",
                note="No postings match the selected filters, so recruiter signals should be treated as unavailable.",
            ),
            MarketNote(
                audience="candidate",
                subject="Market",
                signal_type="coverage",
                note="No postings match the selected filters, so candidate pathways should be treated as unavailable.",
            ),
        ]

    clusters = get_cluster_signals(session, **filters)
    archetypes = get_archetype_signals(session, **filters)
    momentum = get_momentum_signals(session, **filters)
    notes: list[MarketNote] = []

    top_cluster = next((cluster for cluster in clusters if cluster.listing_count), None)
    if top_cluster:
        senior_clause = " and skews senior" if top_cluster.senior_share_pct >= 45 else ""
        city_clause = f" in {top_cluster.top_city}" if top_cluster.top_city else ""
        notes.append(
            MarketNote(
                audience="recruiter",
                subject=top_cluster.name,
                signal_type="cluster",
                note=(
                    f"{top_cluster.name} demand is most visible{city_clause}"
                    f"{senior_clause} across the selected postings."
                ),
            )
        )

    hard_archetype = next(
        (item for item in archetypes if item.listing_count and item.recruiter_difficulty.difficulty_score >= 55),
        None,
    )
    if hard_archetype:
        notes.append(
            MarketNote(
                audience="recruiter",
                subject=hard_archetype.name,
                signal_type="difficulty",
                note=(
                    f"{hard_archetype.name} is a {hard_archetype.recruiter_difficulty.difficulty_label}"
                    " difficulty segment under this proxy."
                ),
            )
        )

    cloud_records = [
        record for record in records if "Cloud Platform Engineering" in skill_clusters_for_record(record)
    ]
    cloud_pair = _top_pair(cloud_records, {"Kubernetes", "Terraform", "Docker", "CI/CD", "AWS", "Azure", "GCP"})
    if cloud_pair:
        notes.append(
            MarketNote(
                audience="recruiter",
                subject="Cloud Platform Engineering",
                signal_type="skill_pair",
                note=f"Cloud Platform roles commonly bundle {cloud_pair[0]} with {cloud_pair[1]}.",
            )
        )

    rising = next((item for item in momentum if item.momentum in {"rising", "new"} and item.current_count), None)
    if rising:
        notes.append(
            MarketNote(
                audience="recruiter",
                subject=rising.name,
                signal_type="momentum",
                note=f"{rising.name} postings are {rising.momentum} versus the previous equivalent period.",
            )
        )

    top_archetype = next((item for item in archetypes if item.listing_count), None)
    if top_archetype and top_archetype.top_skills:
        notes.append(
            MarketNote(
                audience="candidate",
                subject=top_archetype.name,
                signal_type="foundation_skill",
                note=(
                    f"For {top_archetype.name} roles, {top_archetype.top_skills[0]}"
                    " appears as the strongest foundation skill."
                ),
            )
        )

    frontend_records = [
        record for record in records if infer_role_archetype(record.title, record.description, record.skills, record.role_family)
        in {"Frontend Product Engineer", "Full-stack Product Engineer"}
    ]
    if any(has_signal_term(record, "React") and has_signal_term(record, "TypeScript") for record in frontend_records):
        notes.append(
            MarketNote(
                audience="candidate",
                subject="Frontend Product Engineering",
                signal_type="skill_pair",
                note=(
                    "Frontend roles commonly pair React with TypeScript, so learning both is more useful"
                    " than learning React alone."
                ),
            )
        )

    accessible = next(
        (
            item
            for item in archetypes
            if item.listing_count and item.candidate_opportunity.opportunity_label in {"accessible", "competitive"}
        ),
        None,
    )
    if accessible:
        notes.append(
            MarketNote(
                audience="candidate",
                subject=accessible.name,
                signal_type="opportunity",
                note=(
                    f"{accessible.name} has a {accessible.candidate_opportunity.opportunity_label}"
                    " candidate pathway in the selected market data."
                ),
            )
        )

    return notes[:8]


def get_market_signals_summary(session: Session, **filters) -> MarketSignalsSummary:
    records = _load_listing_records(session, **filters)
    clusters = get_cluster_signals(session, **filters)
    archetypes = get_archetype_signals(session, **filters)
    momentum = get_momentum_signals(session, **filters)
    notes = get_market_notes(session, **filters)
    recruiter_difficulty = score_recruiter_difficulty(
        records,
        total_records=len(records),
        name="Selected market",
        signal_type="overall",
        specialized=any(
            archetype.name in SPECIALIZED_ARCHETYPES and archetype.listing_count
            for archetype in archetypes
        ),
    )
    candidate_opportunities = [
        archetype.candidate_opportunity for archetype in archetypes if archetype.listing_count
    ][:8]
    return MarketSignalsSummary(
        total_postings=len(records),
        period_days=str(filters.get("days") or "30"),
        top_clusters=[cluster for cluster in clusters if cluster.listing_count][:8],
        top_archetypes=[archetype for archetype in archetypes if archetype.listing_count][:8],
        momentum=momentum[:12],
        recruiter_difficulty=recruiter_difficulty,
        candidate_opportunities=candidate_opportunities,
        notes=notes,
    )
