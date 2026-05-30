from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


ROLE_FAMILY_SIGNALS = [
    ("machine learning", "AI/ML Engineering"),
    ("ml engineer", "AI/ML Engineering"),
    ("ai engineer", "AI/ML Engineering"),
    ("ai security", "AI/ML Engineering"),
    ("ai platform", "AI/ML Engineering"),
    ("artificial intelligence", "AI/ML Engineering"),
    ("security engineer", "DevOps"),
    ("product security", "DevOps"),
    ("cyber", "DevOps"),
    ("salesforce", "Backend"),
    ("platform engineer", "Cloud"),
    ("cloud transformation", "Cloud"),
    ("solutions architect", "Cloud"),
    ("solution engineer", "Cloud"),
    ("fullstack", "Software Engineering"),
    ("full-stack", "Software Engineering"),
    ("full stack", "Software Engineering"),
    ("frontend", "Frontend"),
    ("front-end", "Frontend"),
    ("backend", "Backend"),
    ("back-end", "Backend"),
    ("data engineer", "Data Analytics"),
    ("data scientist", "Data Science"),
    ("data analyst", "Data Analytics"),
    ("analytics", "Data Analytics"),
    ("devops", "DevOps"),
    ("site reliability", "DevOps"),
    ("sre", "DevOps"),
    ("cloud", "Cloud"),
    ("software engineer", "Software Engineering"),
    ("software developer", "Software Engineering"),
]

CANONICAL_QUERIES = [
    "software engineer",
    "software developer",
    "frontend developer",
    "backend developer",
    "data analyst",
    "data scientist",
    "devops engineer",
    "cloud engineer",
    "machine learning engineer",
    "ai engineer",
]


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("listed_at is required")
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_city(location: str) -> str:
    value = (location or "").lower()
    if any(token in value for token in ["remote", "work from home", "wfh"]):
        return "Remote"
    for city in [
        "Sydney",
        "Melbourne",
        "Brisbane",
        "Perth",
        "Adelaide",
        "Canberra",
        "Hobart",
        "Darwin",
    ]:
        if city.lower() in value:
            return city
    return "Other"


def infer_experience_level(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    signals = [
        ("grad", ["graduate", " grad ", "entry level", "entry-level", "no experience"]),
        ("junior", ["junior", " jr ", "jr.", "0-2 years", "1-2 years"]),
        ("senior", ["senior", " sr ", "sr.", "lead", "principal", "staff", "5+ years", "7+ years"]),
        ("mid", ["mid ", "mid-level", "2-4 years", "3-5 years", "intermediate"]),
    ]
    padded = f" {text} "
    for level, patterns in signals:
        if any(pattern in padded for pattern in patterns):
            return level
    return "unknown"


def normalize_work_mode(raw_work_mode: str | None, title: str, description: str) -> str:
    value = (raw_work_mode or "").strip().lower()
    text = f"{title} {description}".lower()
    if value in {"remote", "hybrid", "onsite"}:
        return value
    if any(token in value for token in ["remote", "work from home", "wfh"]):
        return "remote"
    if "hybrid" in value:
        return "hybrid"
    if any(token in text for token in ["fully remote", "remote-first", "remote role", " remote ", "work from home", " wfh "]):
        return "remote"
    if "hybrid" in text:
        return "hybrid"
    if any(token in text for token in ["onsite", "on-site", "office-based"]):
        return "onsite"
    return "unknown"


def infer_role_family(title: str, description: str, role_hint: str | None = None) -> str:
    primary_text = f"{role_hint or ''} {title}".lower()
    full_text = f"{role_hint or ''} {title} {description}".lower()
    for text in [primary_text, full_text]:
        for signal, family in ROLE_FAMILY_SIGNALS:
            if signal in text:
                return family
    return "Other/Unknown"


def matched_queries(title: str, description: str, role_hint: str | None = None) -> list[str]:
    text = f"{role_hint or ''} {title} {description}".lower()
    matches = [query for query in CANONICAL_QUERIES if query in text]
    if role_hint:
        hint = role_hint.strip().lower()
        if hint and hint not in matches:
            matches.append(hint)
    return sorted(set(matches))


def parse_int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(Decimal(str(value).replace(",", "").strip()))
    except (InvalidOperation, ValueError):
        raise ValueError(f"expected integer-like value, got {value!r}") from None


def normalize_salary(
    salary_min: int | None,
    salary_max: int | None,
    salary_period: str | None,
) -> tuple[int | None, int | None, int | None]:
    if salary_min is None and salary_max is None:
        return None, None, None

    period = (salary_period or "annual").strip().lower()
    multiplier = {
        "annual": 1,
        "year": 1,
        "yearly": 1,
        "month": 12,
        "monthly": 12,
        "week": 52,
        "weekly": 52,
        "day": 260,
        "daily": 260,
        "hour": 1976,
        "hourly": 1976,
    }.get(period, 1)

    annual_min = salary_min * multiplier if salary_min is not None else None
    annual_max = salary_max * multiplier if salary_max is not None else None
    values = [value for value in [annual_min, annual_max] if value is not None]
    annual_mid = round(sum(values) / len(values)) if values else None
    return annual_min, annual_max, annual_mid
