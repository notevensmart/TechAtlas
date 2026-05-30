from app.services.jobdataapi import map_jobdata_job


def test_maps_jobdata_job_to_canonical_row() -> None:
    row = map_jobdata_job(
        {
            "id": 12345,
            "company": {"name": "Example Co"},
            "title": "Senior AI Engineer",
            "location_string": "Sydney, New South Wales, Australia",
            "has_remote": True,
            "work_mode": 1,
            "published": "2026-05-01",
            "description_string": "Build RAG systems with Python, AWS and LangChain.",
            "application_url": "https://example.com/jobs/12345",
            "salary_min": "140000",
            "salary_max": "180000",
            "salary_currency": "AUD",
            "types": [{"name": "Full-time"}],
        },
        role_hint="ai engineer",
    )

    assert row is not None
    assert row["source"] == "jobdataapi"
    assert row["external_id"] == "12345"
    assert row["company"] == "Example Co"
    assert row["work_mode"] == "hybrid"
    assert row["salary_min"] == 140000
    assert row["role_hint"] == "ai engineer"


def test_ignores_non_aud_salary_values() -> None:
    row = map_jobdata_job(
        {
            "id": 12345,
            "company": {"name": "Example Co"},
            "title": "Backend Engineer",
            "location": "Melbourne",
            "published": "2026-05-01",
            "description_string": "Build Python APIs.",
            "salary_min": "100000",
            "salary_max": "120000",
            "salary_currency": "USD",
        },
        role_hint="backend developer",
    )

    assert row is not None
    assert "salary_min" not in row
    assert "salary_max" not in row

