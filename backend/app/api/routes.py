from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.api import (
    BreakdownsResponse,
    CoOccurrenceItem,
    ImportSummary,
    ListingsResponse,
    MarketNote,
    MarketSignalsSummary,
    MomentumSignal,
    RoleArchetypeSignal,
    SkillClusterSignal,
    SkillPathwaySignal,
    SkillDemandItem,
    SkillHistoryPoint,
    SourceHealthItem,
    SummaryStats,
)
from app.services import analytics, market_signals


router = APIRouter(prefix="/api/v1")


DaysParam = Annotated[str, Query(pattern="^(30|90|180|all)$")]


def _filters(
    days: DaysParam = "30",
    city: str | None = None,
    role_family: str | None = None,
    skill_category: str | None = None,
    experience_level: str | None = None,
    work_mode: str | None = None,
) -> dict[str, str | None]:
    return {
        "days": days,
        "city": city,
        "role_family": role_family,
        "skill_category": skill_category,
        "experience_level": experience_level,
        "work_mode": work_mode,
    }


@router.get("/health")
def health(db: Session = Depends(db_session)):
    db.execute(text("select 1"))
    return {"status": "ok"}


@router.get("/imports/summary", response_model=ImportSummary)
def imports_summary(db: Session = Depends(db_session)):
    return analytics.get_import_summary(db)


@router.get("/stats/summary", response_model=SummaryStats)
def stats_summary(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return analytics.get_summary(db, **filters)


@router.get("/skills/demand", response_model=list[SkillDemandItem])
def skills_demand(
    filters: Annotated[dict, Depends(_filters)],
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(db_session),
):
    return analytics.get_skill_demand(db, limit=limit, **filters)


@router.get("/skills/history", response_model=list[SkillHistoryPoint])
def skills_history(
    skill: str,
    days: DaysParam = "30",
    db: Session = Depends(db_session),
):
    return analytics.get_skill_history(db, skill=skill, days=days)


@router.get("/skills/co-occurrence", response_model=list[CoOccurrenceItem])
def skills_co_occurrence(
    filters: Annotated[dict, Depends(_filters)],
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(db_session),
):
    return analytics.get_co_occurrence(db, limit=limit, **filters)


@router.get("/stats/breakdowns", response_model=BreakdownsResponse)
def stats_breakdowns(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return analytics.get_breakdowns(db, **filters)


@router.get("/sources/health", response_model=list[SourceHealthItem])
def sources_health(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return analytics.get_sources_health(db, **filters)


@router.get("/market/signals/summary", response_model=MarketSignalsSummary)
def market_signals_summary(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return market_signals.get_market_signals_summary(db, **filters)


@router.get("/market/signals/clusters", response_model=list[SkillClusterSignal])
def market_signal_clusters(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return market_signals.get_cluster_signals(db, **filters)


@router.get("/market/signals/archetypes", response_model=list[RoleArchetypeSignal])
def market_signal_archetypes(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return market_signals.get_archetype_signals(db, **filters)


@router.get("/market/signals/momentum", response_model=list[MomentumSignal])
def market_signal_momentum(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return market_signals.get_momentum_signals(db, **filters)


@router.get("/market/signals/pathways", response_model=list[SkillPathwaySignal])
def market_signal_pathways(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return market_signals.get_pathway_signals(db, **filters)


@router.get("/market/signals/notes", response_model=list[MarketNote])
def market_signal_notes(
    filters: Annotated[dict, Depends(_filters)],
    db: Session = Depends(db_session),
):
    return market_signals.get_market_notes(db, **filters)


@router.get("/listings", response_model=ListingsResponse)
def listings(
    filters: Annotated[dict, Depends(_filters)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(db_session),
):
    return analytics.get_listings(db, page=page, page_size=page_size, search=search, **filters)
