from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from statistics import median

from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.orm import Session

from app.models import CrawlRun, DailySkillSnapshot, ImportRun, Listing, ListingSkill, RawJobRecord, Skill, Source
from app.schemas.api import (
    BreakdownItem,
    BreakdownsResponse,
    CoOccurrenceItem,
    ImportSummary,
    ListingItem,
    ListingsResponse,
    SkillDemandItem,
    SkillHistoryPoint,
    SourceHealthItem,
    SummaryStats,
)
from app.services.source_registry import load_source_registry


HIGH_DETAIL_ADAPTERS = {"ashby-html", "generic-jsonld", "greenhouse-html", "lever-html"}
PARTIAL_DETAIL_ADAPTERS = {"careerone-search"}
PDF_DETAIL_ADAPTERS = {"apsjobs-pdf"}


@dataclass(frozen=True)
class _ListingStats:
    total: int = 0
    latest: datetime | None = None
    first: datetime | None = None
    average_description_length: float | None = None
    short_description_count: int = 0


@dataclass(frozen=True)
class _RegistrySource:
    adapter: str | None = None
    enabled: bool = True
    compliance_note: str | None = None


def _latest_listing_at(session: Session) -> datetime | None:
    return session.scalar(select(func.max(Listing.listed_at)))


def resolve_bounds(session: Session, days: str | None) -> tuple[datetime | None, datetime | None]:
    latest = _latest_listing_at(session)
    if latest is None:
        return None, None
    if days == "all":
        return None, latest
    try:
        count = int(days or 30)
    except ValueError:
        count = 30
    return latest - timedelta(days=max(count - 1, 0)), latest


def filtered_listing_query(
    session: Session,
    *,
    days: str | None = "30",
    city: str | None = None,
    role_family: str | None = None,
    skill_category: str | None = None,
    experience_level: str | None = None,
    work_mode: str | None = None,
    search: str | None = None,
):
    start, end = resolve_bounds(session, days)
    query = select(Listing)
    if skill_category:
        query = query.join(ListingSkill, ListingSkill.listing_id == Listing.id).join(
            Skill, Skill.id == ListingSkill.skill_id
        )
    conditions = []
    if start is not None:
        conditions.append(Listing.listed_at >= start)
    if end is not None:
        conditions.append(Listing.listed_at <= end)
    if city:
        conditions.append(Listing.city == city)
    if role_family:
        conditions.append(Listing.role_family == role_family)
    if experience_level:
        conditions.append(Listing.experience_level == experience_level)
    if work_mode:
        conditions.append(Listing.work_mode == work_mode)
    if skill_category:
        conditions.append(Skill.category == skill_category)
    if search:
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                Listing.title.ilike(term),
                Listing.company.ilike(term),
                Listing.description_raw.ilike(term),
            )
        )
    if conditions:
        query = query.where(and_(*conditions))
    return query


def _listing_ids_subquery(session: Session, **filters):
    return filtered_listing_query(session, **filters).with_only_columns(Listing.id).distinct().subquery()


def get_import_summary(session: Session) -> ImportSummary:
    latest = session.scalar(select(ImportRun).order_by(ImportRun.started_at.desc()).limit(1))
    totals = session.execute(
        select(
            func.count(ImportRun.id),
            func.coalesce(func.sum(ImportRun.rows_seen), 0),
            func.coalesce(func.sum(ImportRun.rows_imported), 0),
            func.coalesce(func.sum(ImportRun.rows_rejected), 0),
        )
    ).one()
    return ImportSummary(
        latest_import_at=latest.finished_at if latest else None,
        latest_status=latest.status if latest else None,
        total_imports=totals[0],
        rows_seen=totals[1],
        rows_imported=totals[2],
        rows_rejected=totals[3],
    )


def _count_filtered(session: Session, **filters) -> int:
    subq = _listing_ids_subquery(session, **filters)
    return session.scalar(select(func.count()).select_from(subq)) or 0


def _top_city(session: Session, **filters) -> str | None:
    subq = _listing_ids_subquery(session, **filters)
    row = session.execute(
        select(Listing.city, func.count(Listing.id).label("count"))
        .join(subq, subq.c.id == Listing.id)
        .group_by(Listing.city)
        .order_by(func.count(Listing.id).desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def _top_growing_skill(session: Session, **filters) -> str | None:
    days = filters.get("days") or "30"
    if days == "all":
        days = "30"
    try:
        window = int(days)
    except ValueError:
        window = 30

    latest = _latest_listing_at(session)
    if latest is None:
        return None
    current_start = latest - timedelta(days=window - 1)
    previous_start = current_start - timedelta(days=window)
    previous_end = current_start - timedelta(seconds=1)

    def counts_between(start: datetime, end: datetime) -> dict[str, int]:
        local_filters = dict(filters)
        local_filters["days"] = "all"
        subq = (
            filtered_listing_query(session, **local_filters)
            .where(Listing.listed_at >= start, Listing.listed_at <= end)
            .with_only_columns(Listing.id)
            .distinct()
            .subquery()
        )
        return dict(
            session.execute(
                select(Skill.name, func.count(distinct(Listing.id)))
                .select_from(subq)
                .join(ListingSkill, ListingSkill.listing_id == subq.c.id)
                .join(Listing, Listing.id == subq.c.id)
                .join(Skill, Skill.id == ListingSkill.skill_id)
                .group_by(Skill.name)
            ).all()
        )

    current = counts_between(current_start, latest)
    previous = counts_between(previous_start, previous_end)
    best_name = None
    best_delta = None
    for name, count in current.items():
        delta = count - previous.get(name, 0)
        if best_delta is None or delta > best_delta:
            best_name = name
            best_delta = delta
    return best_name


def get_summary(session: Session, **filters) -> SummaryStats:
    total = _count_filtered(session, **filters)
    ids = _listing_ids_subquery(session, **filters)
    latest_import = session.scalar(select(func.max(Listing.imported_at)))
    skills_detected = (
        session.scalar(
            select(func.count(distinct(ListingSkill.skill_id))).join(ids, ids.c.id == ListingSkill.listing_id)
        )
        or 0
    )
    salary_count = (
        session.scalar(
            select(func.count(Listing.id))
            .join(ids, ids.c.id == Listing.id)
            .where(Listing.salary_mid_annual.is_not(None))
        )
        or 0
    )
    return SummaryStats(
        total_postings=total,
        latest_import_at=latest_import,
        skills_detected=skills_detected,
        top_growing_skill=_top_growing_skill(session, **filters),
        top_city=_top_city(session, **filters),
        salary_coverage_pct=round((salary_count / total) * 100, 1) if total else 0,
    )


def get_skill_demand(session: Session, limit: int = 25, **filters) -> list[SkillDemandItem]:
    total = _count_filtered(session, **filters)
    ids = _listing_ids_subquery(session, **filters)
    rows = session.execute(
        select(
            Skill.id,
            Skill.name,
            Skill.category,
            func.count(distinct(ListingSkill.listing_id)).label("listing_count"),
        )
        .join(ListingSkill, ListingSkill.skill_id == Skill.id)
        .join(ids, ids.c.id == ListingSkill.listing_id)
        .group_by(Skill.id, Skill.name, Skill.category)
        .order_by(func.count(distinct(ListingSkill.listing_id)).desc(), Skill.name.asc())
        .limit(limit)
    ).all()

    items = []
    for skill_id, name, category, listing_count in rows:
        salary_values = [
            value
            for (value,) in session.execute(
                select(Listing.salary_mid_annual)
                .join(ListingSkill, ListingSkill.listing_id == Listing.id)
                .join(ids, ids.c.id == Listing.id)
                .where(ListingSkill.skill_id == skill_id, Listing.salary_mid_annual.is_not(None))
            ).all()
            if value is not None
        ]
        avg_salary = round(sum(salary_values) / len(salary_values)) if len(salary_values) >= 10 else None
        median_salary = round(median(salary_values)) if len(salary_values) >= 10 else None
        items.append(
            SkillDemandItem(
                skill=name,
                category=category,
                listing_count=listing_count,
                share_of_postings_pct=round((listing_count / total) * 100, 2) if total else 0,
                salary_listing_count=len(salary_values),
                avg_salary=avg_salary,
                median_salary=median_salary,
            )
        )
    return items


def get_skill_history(session: Session, skill: str, days: str = "30") -> list[SkillHistoryPoint]:
    start, end = resolve_bounds(session, days)
    query = (
        select(
            DailySkillSnapshot.snapshot_date,
            DailySkillSnapshot.listing_count,
            DailySkillSnapshot.share_of_postings_pct,
        )
        .join(Skill, Skill.id == DailySkillSnapshot.skill_id)
        .where(Skill.name == skill)
        .order_by(DailySkillSnapshot.snapshot_date.asc())
    )
    if start is not None:
        query = query.where(DailySkillSnapshot.snapshot_date >= start.date())
    if end is not None:
        query = query.where(DailySkillSnapshot.snapshot_date <= end.date())
    return [
        SkillHistoryPoint(date=row[0], listing_count=row[1], share_of_postings_pct=row[2])
        for row in session.execute(query).all()
    ]


def get_breakdowns(session: Session, **filters) -> BreakdownsResponse:
    total = _count_filtered(session, **filters)
    ids = _listing_ids_subquery(session, **filters)

    def breakdown(column) -> list[BreakdownItem]:
        rows = session.execute(
            select(column, func.count(Listing.id))
            .join(ids, ids.c.id == Listing.id)
            .group_by(column)
            .order_by(func.count(Listing.id).desc())
        ).all()
        return [
            BreakdownItem(name=name or "unknown", count=count, pct=round((count / total) * 100, 1) if total else 0)
            for name, count in rows
        ]

    return BreakdownsResponse(
        cities=breakdown(Listing.city),
        role_families=breakdown(Listing.role_family),
        work_modes=breakdown(Listing.work_mode),
        experience_levels=breakdown(Listing.experience_level),
    )


def _listing_stats_by_source(session: Session, **filters) -> dict[str, _ListingStats]:
    ids = _listing_ids_subquery(session, **filters)
    short_description_count = func.coalesce(
        func.sum(case((func.length(Listing.description_raw) < 120, 1), else_=0)),
        0,
    )
    rows = session.execute(
        select(
            Source.name,
            func.count(Listing.id),
            func.max(Listing.listed_at),
            func.min(Listing.listed_at),
            func.avg(func.length(Listing.description_raw)),
            short_description_count,
        )
        .select_from(Listing)
        .join(ids, ids.c.id == Listing.id)
        .join(Source, Source.id == Listing.source_id)
        .group_by(Source.name)
    ).all()

    return {
        source: _ListingStats(
            total=count or 0,
            latest=latest,
            first=first,
            average_description_length=float(avg_length) if avg_length is not None else None,
            short_description_count=short_count or 0,
        )
        for source, count, latest, first, avg_length, short_count in rows
    }


def _latest_crawl_runs(session: Session) -> dict[str, CrawlRun]:
    latest: dict[str, CrawlRun] = {}
    runs = session.scalars(
        select(CrawlRun).order_by(CrawlRun.source_key.asc(), CrawlRun.started_at.desc(), CrawlRun.id.desc())
    ).all()
    for run in runs:
        latest.setdefault(run.source_key, run)
    return latest


def _latest_raw_adapters(session: Session) -> dict[str, str]:
    adapters: dict[str, str] = {}
    rows = session.execute(
        select(RawJobRecord.source_key, RawJobRecord.adapter).order_by(
            RawJobRecord.source_key.asc(),
            RawJobRecord.observed_at.desc(),
            RawJobRecord.id.desc(),
        )
    ).all()
    for source_key, adapter in rows:
        adapters.setdefault(source_key, adapter)
    return adapters


def _registry_sources() -> dict[str, _RegistrySource]:
    try:
        sources = load_source_registry()
    except Exception:
        return {}
    return {
        source.key: _RegistrySource(
            adapter=source.adapter,
            enabled=source.enabled,
            compliance_note=source.compliance_note,
        )
        for source in sources
    }


def _description_quality_is_weak(
    *,
    total_listings: int,
    average_description_length: float | None,
    short_description_count: int,
) -> bool:
    if total_listings <= 0 or average_description_length is None:
        return False
    if average_description_length < 80:
        return True
    return short_description_count >= max(1, total_listings // 2)


def source_quality_tier(
    *,
    adapter: str | None,
    latest_status: str | None,
    rows_extracted: int,
    total_listings: int,
    average_description_length: float | None,
    short_description_count: int,
) -> str:
    if latest_status in {"failed", "abandoned"}:
        return "low"
    if latest_status is not None and rows_extracted == 0:
        return "low"
    if total_listings <= 0:
        return "low"

    weak_description_quality = _description_quality_is_weak(
        total_listings=total_listings,
        average_description_length=average_description_length,
        short_description_count=short_description_count,
    )
    if adapter in PARTIAL_DETAIL_ADAPTERS:
        return "medium"
    if adapter in PDF_DETAIL_ADAPTERS:
        return "medium" if weak_description_quality else "high"
    if adapter in HIGH_DETAIL_ADAPTERS:
        return "low" if weak_description_quality else "high"
    return "medium" if not weak_description_quality else "low"


def _source_notes(
    *,
    registry: _RegistrySource | None,
    adapter: str | None,
    run: CrawlRun | None,
    stats: _ListingStats,
) -> str | None:
    notes: list[str] = []
    if registry and not registry.enabled:
        notes.append("Disabled in the source registry.")
    if registry and registry.compliance_note:
        notes.append(registry.compliance_note)
    if run and run.status in {"failed", "abandoned"}:
        detail = f": {run.error_message}" if run.error_message else "."
        label = "failed" if run.status == "failed" else "was abandoned"
        notes.append(f"Latest crawl {label}{detail}")
    elif run and run.status == "completed" and run.rows_extracted == 0:
        notes.append("Latest crawl completed but extracted zero rows.")
    elif run and run.status == "completed" and run.rows_imported == 0:
        notes.append("Latest crawl completed but imported zero rows.")
    if adapter in PARTIAL_DETAIL_ADAPTERS and not any("detail pages" in note.lower() for note in notes):
        notes.append("Search-result cards only; detail pages are not followed.")
    if adapter in PDF_DETAIL_ADAPTERS:
        notes.append("Parsed APS detail PDFs; listed_at may be the crawl observation time.")
    if adapter is None and stats.total > 0:
        notes.append("Imported source without crawler adapter metadata.")
    if _description_quality_is_weak(
        total_listings=stats.total,
        average_description_length=stats.average_description_length,
        short_description_count=stats.short_description_count,
    ):
        notes.append("Listing descriptions appear short or incomplete.")

    deduped = list(dict.fromkeys(notes))
    return " ".join(deduped) if deduped else None


def get_sources_health(session: Session, **filters) -> list[SourceHealthItem]:
    total_filters = dict(filters)
    total_filters["days"] = "all"
    total_stats = _listing_stats_by_source(session, **total_filters)
    period_stats = _listing_stats_by_source(session, **filters)
    latest_runs = _latest_crawl_runs(session)
    raw_adapters = _latest_raw_adapters(session)
    registry = _registry_sources()

    db_sources = set(session.scalars(select(Source.name)).all())
    source_keys = sorted(set(registry) | db_sources | set(latest_runs) | set(raw_adapters))

    rows = []
    for source_key in source_keys:
        run = latest_runs.get(source_key)
        registered = registry.get(source_key)
        stats = total_stats.get(source_key, _ListingStats())
        period = period_stats.get(source_key, _ListingStats())
        adapter = (run.adapter if run else None) or raw_adapters.get(source_key) or (registered.adapter if registered else None)
        quality = source_quality_tier(
            adapter=adapter,
            latest_status=run.status if run else None,
            rows_extracted=run.rows_extracted if run else 0,
            total_listings=stats.total,
            average_description_length=stats.average_description_length,
            short_description_count=stats.short_description_count,
        )
        rows.append(
            SourceHealthItem(
                source=source_key,
                adapter=adapter,
                latest_status=run.status if run else None,
                latest_crawl_finished_at=run.finished_at if run else None,
                pages_fetched=run.pages_fetched if run else 0,
                pages_skipped=run.pages_skipped if run else 0,
                rows_extracted=run.rows_extracted if run else 0,
                rows_imported=run.rows_imported if run else 0,
                total_listings=stats.total,
                period_listings=period.total,
                latest_listing_listed_at=stats.latest,
                first_listing_listed_at=stats.first,
                quality_tier=quality,
                notes=_source_notes(registry=registered, adapter=adapter, run=run, stats=stats),
            )
        )

    return sorted(
        rows,
        key=lambda item: (
            item.total_listings == 0,
            -(item.period_listings or 0),
            -(item.total_listings or 0),
            item.source,
        ),
    )


def get_co_occurrence(session: Session, limit: int = 30, **filters) -> list[CoOccurrenceItem]:
    ids = [row[0] for row in session.execute(_listing_ids_subquery(session, **filters).select()).all()]
    if not ids:
        return []
    rows = session.execute(
        select(ListingSkill.listing_id, Skill.name)
        .join(Skill, Skill.id == ListingSkill.skill_id)
        .where(ListingSkill.listing_id.in_(ids))
        .order_by(ListingSkill.listing_id)
    ).all()
    by_listing: dict[int, list[str]] = defaultdict(list)
    for listing_id, skill_name in rows:
        by_listing[listing_id].append(skill_name)

    pairs: Counter[tuple[str, str]] = Counter()
    for skills in by_listing.values():
        unique = sorted(set(skills))
        for index, skill_a in enumerate(unique):
            for skill_b in unique[index + 1 :]:
                pairs[(skill_a, skill_b)] += 1

    total = len(ids)
    return [
        CoOccurrenceItem(
            skill_a=skill_a,
            skill_b=skill_b,
            count=count,
            strength_score=round(count / total, 4) if total else 0,
        )
        for (skill_a, skill_b), count in pairs.most_common(limit)
    ]


def get_listings(
    session: Session,
    page: int = 1,
    page_size: int = 25,
    **filters,
) -> ListingsResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    base = filtered_listing_query(session, **filters).distinct()
    count_subq = base.with_only_columns(Listing.id).subquery()
    total = session.scalar(select(func.count()).select_from(count_subq)) or 0
    listings = session.scalars(
        base.order_by(Listing.listed_at.desc(), Listing.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    listing_ids = [listing.id for listing in listings]
    skills_by_listing: dict[int, list[str]] = defaultdict(list)
    if listing_ids:
        for listing_id, skill_name in session.execute(
            select(ListingSkill.listing_id, Skill.name)
            .join(Skill, Skill.id == ListingSkill.skill_id)
            .where(ListingSkill.listing_id.in_(listing_ids))
            .order_by(Skill.name)
        ):
            skills_by_listing[listing_id].append(skill_name)

    items = [
        ListingItem(
            id=listing.id,
            source=listing.source.name,
            external_id=listing.external_id,
            source_url=listing.source_url,
            title=listing.title,
            company=listing.company,
            raw_location=listing.raw_location,
            city=listing.city,
            listed_at=listing.listed_at,
            salary_min_annual=listing.salary_min_annual,
            salary_max_annual=listing.salary_max_annual,
            salary_mid_annual=listing.salary_mid_annual,
            work_mode=listing.work_mode,
            work_type=listing.work_type,
            experience_level=listing.experience_level,
            role_family=listing.role_family,
            skills=skills_by_listing.get(listing.id, []),
            description_snippet=listing.description_raw[:700],
        )
        for listing in listings
    ]
    return ListingsResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(ceil(total / page_size), 1),
    )
