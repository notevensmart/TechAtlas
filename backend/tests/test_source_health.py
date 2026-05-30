from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api import routes
from app.api.routes import db_session
from app.main import app
from app.schemas.api import SourceHealthItem
from app.services.analytics import source_quality_tier


def test_source_health_route_passes_core_filters(monkeypatch) -> None:
    called = {}

    def override_db():
        yield object()

    def fake_source_health(db, **filters):
        called["db"] = db
        called["filters"] = filters
        return [
            SourceHealthItem(
                source="greenhouse:example",
                adapter="greenhouse-html",
                latest_status="completed",
                latest_crawl_finished_at=datetime(2026, 5, 30, 1, 2, tzinfo=timezone.utc),
                pages_fetched=4,
                pages_skipped=1,
                rows_extracted=3,
                rows_imported=3,
                total_listings=3,
                period_listings=2,
                latest_listing_listed_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
                first_listing_listed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                quality_tier="high",
                notes="Public company careers page.",
            )
        ]

    monkeypatch.setattr(routes.analytics, "get_sources_health", fake_source_health)
    app.dependency_overrides[db_session] = override_db
    try:
        response = TestClient(app).get(
            "/api/v1/sources/health",
            params={
                "days": "90",
                "city": "Sydney",
                "role_family": "Software Engineering",
                "skill_category": "backend",
                "experience_level": "senior",
                "work_mode": "hybrid",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert called["filters"] == {
        "days": "90",
        "city": "Sydney",
        "role_family": "Software Engineering",
        "skill_category": "backend",
        "experience_level": "senior",
        "work_mode": "hybrid",
    }
    assert response.json()[0]["source"] == "greenhouse:example"
    assert response.json()[0]["quality_tier"] == "high"


def test_source_quality_tier_defaults() -> None:
    assert (
        source_quality_tier(
            adapter="greenhouse-html",
            latest_status="completed",
            rows_extracted=3,
            total_listings=3,
            average_description_length=450,
            short_description_count=0,
        )
        == "high"
    )
    assert (
        source_quality_tier(
            adapter="careerone-search",
            latest_status="completed",
            rows_extracted=5,
            total_listings=5,
            average_description_length=180,
            short_description_count=0,
        )
        == "medium"
    )
    assert (
        source_quality_tier(
            adapter="apsjobs-pdf",
            latest_status="completed",
            rows_extracted=2,
            total_listings=2,
            average_description_length=500,
            short_description_count=0,
        )
        == "high"
    )
    assert (
        source_quality_tier(
            adapter="lever-html",
            latest_status="completed",
            rows_extracted=2,
            total_listings=2,
            average_description_length=45,
            short_description_count=2,
        )
        == "low"
    )
    assert (
        source_quality_tier(
            adapter="ashby-html",
            latest_status="failed",
            rows_extracted=0,
            total_listings=0,
            average_description_length=None,
            short_description_count=0,
        )
        == "low"
    )
