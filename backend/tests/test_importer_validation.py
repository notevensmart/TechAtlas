from pathlib import Path

import pytest

from app.services.importer import REQUIRED_FIELDS, MissingColumnsError, _load_rows, _validate_row


def test_csv_missing_required_columns_fails_fast(tmp_path: Path) -> None:
    path = tmp_path / "jobs.csv"
    path.write_text("source,title\nexample,Engineer\n", encoding="utf-8")

    rows, columns = _load_rows(path)

    assert rows
    with pytest.raises(MissingColumnsError):
        raise MissingColumnsError(REQUIRED_FIELDS - (columns or set()))
    assert columns == {"source", "title"}


def test_validate_row_parses_required_fields() -> None:
    record = _validate_row(
        {
            "source": "permitted-export",
            "external_id": "abc-1",
            "title": "AI Engineer",
            "company": "Example Co",
            "location": "Sydney NSW",
            "description": "Build RAG systems with Python.",
            "listed_at": "2026-05-01T00:00:00Z",
            "salary_min": "120000",
            "salary_max": "150000",
            "salary_period": "annual",
        }
    )

    assert record.source == "permitted-export"
    assert record.salary_min == 120000
    assert record.listed_at.tzinfo is not None
