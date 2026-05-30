from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

from app.models import DailySkillSnapshot, Listing, ListingSkill


def refresh_daily_skill_snapshots(session: Session) -> int:
    session.execute(delete(DailySkillSnapshot))

    total_by_date = dict(
        session.execute(
            select(func.date(Listing.listed_at), func.count(distinct(Listing.id))).group_by(
                func.date(Listing.listed_at)
            )
        ).all()
    )

    rows = session.execute(
        select(
            func.date(Listing.listed_at).label("snapshot_date"),
            ListingSkill.skill_id,
            func.count(distinct(Listing.id)).label("listing_count"),
        )
        .join(ListingSkill, ListingSkill.listing_id == Listing.id)
        .group_by(func.date(Listing.listed_at), ListingSkill.skill_id)
    ).all()

    inserted = 0
    for snapshot_date, skill_id, listing_count in rows:
        total = total_by_date.get(snapshot_date, 0) or 0
        share = round((listing_count / total) * 100, 2) if total else 0
        session.add(
            DailySkillSnapshot(
                snapshot_date=snapshot_date,
                skill_id=skill_id,
                listing_count=listing_count,
                total_postings=total,
                share_of_postings_pct=share,
            )
        )
        inserted += 1

    return inserted

