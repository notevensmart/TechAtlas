import os
from pathlib import Path

import pytest
from sqlalchemy import select

if not os.getenv("TEST_DATABASE_URL"):
    pytest.skip(
        "requires TEST_DATABASE_URL pointing at a disposable PostgreSQL database",
        allow_module_level=True,
    )

os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import Listing, ListingSkill, Source  # noqa: E402
from app.services.importer import import_file  # noqa: E402


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        yield session


def test_import_file_partial_import_and_deduplication(tmp_path: Path, db_session) -> None:
    path = tmp_path / "jobs.csv"
    path.write_text(
        "\n".join(
            [
                "source,external_id,title,company,location,description,listed_at,salary_min,salary_max,salary_period,role_hint",
                "permitted,job-1,AI Engineer,Example,Sydney NSW,Python RAG AWS,2026-05-01T00:00:00Z,120000,150000,annual,ai engineer",
                "permitted,,Broken,Example,Sydney NSW,Missing external id,2026-05-01T00:00:00Z,,,,",
            ]
        ),
        encoding="utf-8",
    )
    rejects = tmp_path / "rejects.csv"

    result = import_file(db_session, path, rejects)

    assert result.rows_seen == 2
    assert result.rows_imported == 1
    assert result.rows_rejected == 1
    assert rejects.exists()
    source = db_session.scalar(select(Source).where(Source.name == "permitted"))
    assert source is not None
    listing = db_session.scalar(select(Listing).where(Listing.external_id == "job-1"))
    assert listing is not None
    assert listing.role_family == "AI/ML Engineering"
    assert db_session.scalars(select(ListingSkill).where(ListingSkill.listing_id == listing.id)).all()
