from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ImportRun, Listing, ListingQueryMatch, ListingSkill, Skill, Source
from app.services.aggregates import refresh_daily_skill_snapshots
from app.services.extraction import SkillMatcher
from app.services.normalization import (
    infer_experience_level,
    infer_role_family,
    matched_queries,
    normalize_city,
    normalize_salary,
    normalize_work_mode,
    parse_datetime,
    parse_int,
)
from app.services.taxonomy import seed_skills


REQUIRED_FIELDS = {"source", "external_id", "title", "company", "location", "description", "listed_at"}


class MissingColumnsError(ValueError):
    def __init__(self, missing: set[str]):
        super().__init__(f"missing required columns: {', '.join(sorted(missing))}")
        self.missing = missing


@dataclass
class JobRecord:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    description: str
    listed_at: datetime
    source_url: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_period: str | None = None
    work_mode: str | None = None
    work_type: str | None = None
    role_hint: str | None = None
    observed_at: datetime | None = None
    content_hash: str | None = None


@dataclass
class RejectedRow:
    row_number: int
    reason: str
    raw: dict[str, object]


@dataclass
class ImportResult:
    rows_seen: int
    rows_imported: int
    rows_rejected: int
    import_run_id: int
    rejects_path: Path | None = None


def _load_rows(path: Path) -> tuple[list[dict[str, object]], set[str] | None]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            return [dict(row) for row in reader], columns

    if suffix in {".jsonl", ".ndjson"}:
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return rows, None

    raise ValueError("import file must be .csv, .jsonl, or .ndjson")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _validate_row(row: dict[str, object]) -> JobRecord:
    missing = [field for field in REQUIRED_FIELDS if not _clean(row.get(field))]
    if missing:
        raise ValueError(f"missing required values: {', '.join(sorted(missing))}")

    salary_min = parse_int(row.get("salary_min"))
    salary_max = parse_int(row.get("salary_max"))

    return JobRecord(
        source=_clean(row["source"]),
        external_id=_clean(row["external_id"]),
        title=_clean(row["title"]),
        company=_clean(row["company"]),
        location=_clean(row["location"]),
        description=_clean(row["description"]),
        listed_at=parse_datetime(row["listed_at"]),
        source_url=_clean(row.get("source_url")) or None,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=_clean(row.get("salary_period")) or None,
        work_mode=_clean(row.get("work_mode")) or None,
        work_type=_clean(row.get("work_type")) or None,
        role_hint=_clean(row.get("role_hint")) or None,
        observed_at=parse_datetime(row["observed_at"]) if _clean(row.get("observed_at")) else None,
        content_hash=_clean(row.get("content_hash")) or None,
    )


def _write_rejects(path: Path, rejects: list[RejectedRow]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_number", "reason", "raw"])
        writer.writeheader()
        for reject in rejects:
            writer.writerow(
                {
                    "row_number": reject.row_number,
                    "reason": reject.reason,
                    "raw": json.dumps(reject.raw, ensure_ascii=True),
                }
            )
    return path


def import_rows(
    session: Session,
    rows: list[dict[str, object]],
    *,
    file_name: str,
    rejects_path: Path | None = None,
    csv_columns: set[str] | None = None,
) -> ImportResult:
    if csv_columns is not None:
        missing_columns = REQUIRED_FIELDS - csv_columns
        if missing_columns:
            raise MissingColumnsError(missing_columns)

    valid_records: list[JobRecord] = []
    rejects: list[RejectedRow] = []
    for index, row in enumerate(rows, start=2 if csv_columns is not None else 1):
        try:
            valid_records.append(_validate_row(row))
        except Exception as exc:
            rejects.append(RejectedRow(row_number=index, reason=str(exc), raw=row))

    if not valid_records:
        raise ValueError("no valid rows to import")

    source_names = sorted({record.source for record in valid_records})
    run = ImportRun(
        source_name=",".join(source_names),
        file_name=file_name,
        status="running",
        rows_seen=len(rows),
        rows_imported=0,
        rows_rejected=len(rejects),
    )
    session.add(run)
    session.flush()

    try:
        seed_skills(session)
        session.flush()
        matcher = SkillMatcher.from_taxonomy()
        skills_by_name = {skill.name: skill for skill in session.scalars(select(Skill)).all()}

        sources_by_name = {
            source.name: source
            for source in session.scalars(
                select(Source).where(Source.name.in_(source_names))
            ).all()
        }
        for source_name in source_names:
            if source_name not in sources_by_name:
                source = Source(name=source_name)
                session.add(source)
                session.flush()
                sources_by_name[source_name] = source

        imported = 0
        for record in valid_records:
            observed_at = record.observed_at or datetime.now(timezone.utc)
            source = sources_by_name[record.source]
            listing = session.scalar(
                select(Listing).where(
                    Listing.source_id == source.id,
                    Listing.external_id == record.external_id,
                )
            )
            if listing is None:
                listing = Listing(source_id=source.id, external_id=record.external_id)
                session.add(listing)
                listing.first_seen_at = observed_at

            annual_min, annual_max, annual_mid = normalize_salary(
                record.salary_min, record.salary_max, record.salary_period
            )
            text_for_inference = f"{record.title}\n{record.description}"

            listing.source_url = record.source_url
            listing.title = record.title
            listing.company = record.company
            listing.raw_location = record.location
            listing.city = normalize_city(record.location)
            listing.description_raw = record.description
            listing.listed_at = record.listed_at
            listing.imported_at = datetime.now(timezone.utc)
            if listing.first_seen_at is None:
                listing.first_seen_at = observed_at
            listing.last_seen_at = observed_at
            listing.expired_at = None
            listing.content_hash = record.content_hash
            listing.salary_min = record.salary_min
            listing.salary_max = record.salary_max
            listing.salary_period = record.salary_period
            listing.salary_min_annual = annual_min
            listing.salary_max_annual = annual_max
            listing.salary_mid_annual = annual_mid
            listing.work_mode = normalize_work_mode(record.work_mode, record.title, record.description)
            listing.work_type = record.work_type
            listing.experience_level = infer_experience_level(record.title, record.description)
            listing.role_family = infer_role_family(record.title, record.description, record.role_hint)
            session.flush()

            session.execute(delete(ListingQueryMatch).where(ListingQueryMatch.listing_id == listing.id))
            for query in matched_queries(record.title, record.description, record.role_hint):
                session.add(ListingQueryMatch(listing_id=listing.id, query=query))

            session.execute(delete(ListingSkill).where(ListingSkill.listing_id == listing.id))
            for definition in matcher.extract(text_for_inference):
                skill = skills_by_name.get(definition.name)
                if skill is not None:
                    session.add(ListingSkill(listing_id=listing.id, skill_id=skill.id))

            imported += 1

        session.flush()
        refresh_daily_skill_snapshots(session)

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.rows_imported = imported
        run.rows_rejected = len(rejects)

        written_rejects = _write_rejects(rejects_path, rejects) if rejects and rejects_path else None
        session.commit()
        return ImportResult(
            rows_seen=len(rows),
            rows_imported=imported,
            rows_rejected=len(rejects),
            import_run_id=run.id,
            rejects_path=written_rejects,
        )
    except Exception as exc:
        session.rollback()
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = str(exc)
        session.add(run)
        session.commit()
        raise


def import_file(session: Session, path: Path, rejects_path: Path | None = None) -> ImportResult:
    rows, columns = _load_rows(path)
    return import_rows(
        session,
        rows,
        file_name=path.name,
        rejects_path=rejects_path,
        csv_columns=columns,
    )
