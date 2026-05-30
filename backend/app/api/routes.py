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
    SkillDemandItem,
    SkillHistoryPoint,
    SummaryStats,
)
from app.services import analytics


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


@router.get("/listings", response_model=ListingsResponse)
def listings(
    filters: Annotated[dict, Depends(_filters)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(db_session),
):
    return analytics.get_listings(db, page=page, page_size=page_size, search=search, **filters)

