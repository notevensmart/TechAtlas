from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api import routes
from app.api.routes import db_session
from app.main import app
from app.schemas.api import MarketNote
from app.services import market_signals
from app.services.market_signals import (
    ListingSignalRecord,
    build_momentum_signal,
    get_market_notes,
    get_pathway_signals,
    infer_role_archetype,
    score_candidate_opportunity,
    score_recruiter_difficulty,
    skill_clusters_for_record,
)


def record(
    title: str,
    *,
    description: str = "",
    city: str = "Sydney",
    experience_level: str = "mid",
    salary_mid_annual: int | None = None,
    skills: tuple[str, ...] = (),
) -> ListingSignalRecord:
    return ListingSignalRecord(
        id=1,
        title=title,
        description=description,
        city=city,
        role_family="Software Engineering",
        experience_level=experience_level,
        work_mode="hybrid",
        listed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        salary_mid_annual=salary_mid_annual,
        skills=skills,
    )


def test_skill_cluster_matching_uses_detected_skills_and_text() -> None:
    analytics = record(
        "Analytics Engineer",
        description="Build SQL models with dbt and Snowflake.",
        skills=("SQL", "dbt", "Snowflake"),
    )
    security = record(
        "Cloud Security Engineer",
        description="Own IAM, SIEM detections and AWS cloud security controls.",
        skills=("AWS",),
    )

    assert "Modern Data Stack" in skill_clusters_for_record(analytics)
    assert "Analytics / BI" in skill_clusters_for_record(analytics)
    assert "Cyber / Security Engineering" in skill_clusters_for_record(security)


def test_archetype_inference_prefers_practical_role_patterns() -> None:
    assert (
        infer_role_archetype(
            "Senior AI Engineer",
            "Build RAG workflows with OpenAI API, Python and React.",
            ("Python", "RAG", "OpenAI API", "React"),
        )
        == "AI Product Engineer"
    )
    assert (
        infer_role_archetype(
            "Cloud Security Engineer",
            "AWS IAM and cloud security automation.",
            ("AWS", "IAM"),
        )
        == "Cloud Security Engineer"
    )
    assert infer_role_archetype("Analytics Engineer", "SQL and dbt", ("SQL", "dbt")) == "Analytics Engineer"


def test_momentum_calculation_labels_new_rising_stable_and_falling() -> None:
    assert build_momentum_signal("AI Engineering", "cluster", 4, 0).momentum == "new"
    assert build_momentum_signal("AI Engineering", "cluster", 12, 8).momentum == "rising"
    assert build_momentum_signal("AI Engineering", "cluster", 9, 10).momentum == "stable"
    assert build_momentum_signal("AI Engineering", "cluster", 6, 10).momentum == "falling"


def test_recruiter_difficulty_scoring_is_explainable() -> None:
    records = [
        record(
            "Senior Cloud Security Engineer",
            description="AWS IAM Kubernetes Terraform SIEM Python",
            experience_level="senior",
            salary_mid_annual=180000,
            skills=("AWS", "IAM", "Kubernetes", "Terraform", "Python", "SIEM"),
        ),
        record(
            "Principal Cloud Security Engineer",
            description="Cloud security, Terraform, Kubernetes and detection engineering",
            experience_level="senior",
            salary_mid_annual=190000,
            skills=("AWS", "Cloud Security", "Terraform", "Kubernetes"),
        ),
    ]

    score = score_recruiter_difficulty(
        records,
        total_records=20,
        name="Cloud Security Engineer",
        signal_type="archetype",
        specialized=True,
    )

    assert score.difficulty_score >= 75
    assert score.difficulty_label == "very high"
    assert score.reasons


def test_candidate_opportunity_scoring_rewards_accessible_pathways() -> None:
    records = [
        record("Junior Analytics Engineer", skills=("SQL", "dbt", "Python"), experience_level="junior"),
        record("Analytics Engineer", skills=("SQL", "dbt", "Snowflake"), experience_level="mid"),
        record("BI Analyst", skills=("SQL", "Power BI", "Excel"), experience_level="mid"),
    ]

    score = score_candidate_opportunity(
        records,
        total_records=6,
        name="Analytics Engineer",
        signal_type="archetype",
        adjacent_skill_count=4,
        clear_cluster=True,
    )

    assert score.opportunity_score >= 65
    assert score.opportunity_label == "accessible"
    assert any("entry" in reason or "junior" in reason or "mid" in reason for reason in score.reasons)


def test_pathway_generation_uses_blueprint_and_market_adjacencies(monkeypatch) -> None:
    records = [
        record("Analytics Engineer", skills=("SQL", "dbt", "Python", "Snowflake")),
        record("Analytics Engineer", skills=("SQL", "dbt", "Power BI", "Airflow")),
    ]

    monkeypatch.setattr(market_signals, "_load_listing_records", lambda *args, **kwargs: records)

    pathways = get_pathway_signals(object())
    analytics = next(item for item in pathways if item.archetype == "Analytics Engineer")

    assert analytics.core_skills == ["SQL", "dbt", "Python"]
    assert "Snowflake" in analytics.common_adjacent_skills
    assert "Data Platform Engineer" in analytics.related_archetypes


def test_notes_generation_is_deterministic_and_audience_specific(monkeypatch) -> None:
    records = [
        record("Frontend Engineer", skills=("React", "TypeScript", "CSS"), city="Sydney"),
        record("Frontend Engineer", skills=("React", "TypeScript", "Next.js"), city="Sydney"),
    ]

    monkeypatch.setattr(market_signals, "_load_listing_records", lambda *args, **kwargs: records)
    monkeypatch.setattr(market_signals, "_load_momentum_records", lambda *args, **kwargs: (records, []))

    notes = get_market_notes(object())

    assert any(note.audience == "recruiter" for note in notes)
    assert any(note.audience == "candidate" for note in notes)
    assert any("React with TypeScript" in note.note for note in notes)


def test_market_signal_route_passes_global_filters(monkeypatch) -> None:
    called = {}

    def override_db():
        yield object()

    def fake_notes(db, **filters):
        called["db"] = db
        called["filters"] = filters
        return [
            MarketNote(
                audience="candidate",
                subject="Analytics Engineer",
                signal_type="foundation_skill",
                note="For Analytics Engineer roles, SQL appears as the strongest foundation skill.",
            )
        ]

    monkeypatch.setattr(routes.market_signals, "get_market_notes", fake_notes)
    app.dependency_overrides[db_session] = override_db
    try:
        response = TestClient(app).get(
            "/api/v1/market/signals/notes",
            params={
                "days": "90",
                "city": "Sydney",
                "role_family": "Data Analytics",
                "skill_category": "data",
                "experience_level": "mid",
                "work_mode": "hybrid",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert called["filters"] == {
        "days": "90",
        "city": "Sydney",
        "role_family": "Data Analytics",
        "skill_category": "data",
        "experience_level": "mid",
        "work_mode": "hybrid",
    }
    assert response.json()[0]["audience"] == "candidate"
