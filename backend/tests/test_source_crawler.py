from datetime import datetime, timezone
from pathlib import Path

from app.services.source_crawler import (
    ApsJobsPdfAdapter,
    AshbyAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    detect_source_from_url,
    discovered_sources_to_registry,
    row_matches_source_filters,
)
from app.services.source_registry import SourceDefinition, load_source_registry


def test_greenhouse_adapter_extracts_remix_job_post() -> None:
    source = SourceDefinition(
        key="greenhouse:example",
        adapter="greenhouse-html",
        seeds=["https://job-boards.greenhouse.io/example"],
    )
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://job-boards.greenhouse.io/example/jobs/123" />
      </head>
      <body>
        <script>
        window.__remixContext = {
          "state": {
            "loaderData": {
              "routes/$url_token_.jobs_.$job_post_id": {
                "jobPost": {
                  "post_type": "job_post",
                  "title": "Senior Software Engineer",
                  "content": "<p>Build Python services on AWS.</p>",
                  "job_post_location": "Sydney, Australia",
                  "public_url": "https://job-boards.greenhouse.io/example/jobs/123",
                  "company_name": "Example",
                  "published_at": "2026-05-01T00:00:00Z",
                  "employment": "Full-time"
                }
              }
            }
          }
        };
        </script>
      </body>
    </html>
    """

    records = GreenhouseAdapter().extract_records(
        source,
        "https://job-boards.greenhouse.io/example/jobs/123",
        html,
        datetime(2026, 5, 30, tzinfo=timezone.utc),
    )

    assert len(records) == 1
    row = records[0].canonical_row
    assert row["source"] == "greenhouse:example"
    assert row["external_id"] == "123"
    assert row["title"] == "Senior Software Engineer"
    assert row["location"] == "Sydney, Australia"
    assert row["content_hash"]


def test_greenhouse_adapter_discovers_au_tech_jobs_from_board() -> None:
    source = SourceDefinition(
        key="greenhouse:example",
        adapter="greenhouse-html",
        seeds=["https://job-boards.greenhouse.io/example"],
    )
    html = """
    <script>
    window.__remixContext = {
      "state": {
        "loaderData": {
          "routes/$url_token": {
            "jobPosts": {
              "data": [
                {
                  "title": "Backend Engineer",
                  "location": "Melbourne, Australia",
                  "absolute_url": "https://job-boards.greenhouse.io/example/jobs/1"
                },
                {
                  "title": "Legal Counsel",
                  "location": "Melbourne, Australia",
                  "absolute_url": "https://job-boards.greenhouse.io/example/jobs/2"
                },
                {
                  "title": "Software Engineer",
                  "location": "Austin, Texas",
                  "absolute_url": "https://job-boards.greenhouse.io/example/jobs/3"
                }
              ]
            }
          }
        }
      }
    };
    </script>
    """

    links = GreenhouseAdapter().discover_links(source, "https://job-boards.greenhouse.io/example", html)

    assert links == ["https://job-boards.greenhouse.io/example/jobs/1"]


def test_lever_adapter_discovers_direct_job_links() -> None:
    source = SourceDefinition(key="lever:example", adapter="lever-html", seeds=["https://jobs.lever.co/example"])
    html = """
    <a href="https://jobs.lever.co/example/abc-123">Engineer</a>
    <a href="https://jobs.lever.co/example">Board</a>
    <a href="https://other.example/jobs/1">Other</a>
    """

    links = LeverAdapter().discover_links(source, "https://jobs.lever.co/example", html)

    assert links == ["https://jobs.lever.co/example/abc-123"]


def test_ashby_adapter_discovers_board_postings() -> None:
    source = SourceDefinition(key="ashby:example", adapter="ashby-html", seeds=["https://jobs.ashbyhq.com/Example"])
    html = """
    <script>
    window.__appData = {
      "posting": null,
      "jobBoard": {
        "jobPostings": [
          {
            "id": "job-1",
            "title": "Software Engineer",
            "locationName": "Sydney",
            "departmentName": "Engineering",
            "isListed": true
          },
          {
            "id": "job-2",
            "title": "Account Executive",
            "locationName": "Sydney",
            "departmentName": "Sales",
            "isListed": true
          }
        ]
      }
    };
    console.log("later script content");
    </script>
    """

    links = AshbyAdapter().discover_links(source, "https://jobs.ashbyhq.com/Example", html)

    assert links == ["https://jobs.ashbyhq.com/Example/job-1"]


def test_ashby_adapter_extracts_app_data_posting() -> None:
    source = SourceDefinition(key="ashby:example", adapter="ashby-html", seeds=["https://jobs.ashbyhq.com/Example"])
    html = """
    <script>
    window.__appData = {
      "organization": {"name": "Example Co"},
      "posting": {
        "id": "job-1",
        "title": "Software Engineer",
        "descriptionHtml": "<p>Build Python services on AWS.</p>",
        "locationName": "Sydney",
        "publishedDate": "2026-05-01",
        "workplaceType": "Hybrid",
        "employmentType": "FullTime",
        "isRemote": false
      },
      "jobBoard": null
    };
    </script>
    """

    records = AshbyAdapter().extract_records(
        source,
        "https://jobs.ashbyhq.com/Example/job-1",
        html,
        datetime(2026, 5, 30, tzinfo=timezone.utc),
    )

    assert len(records) == 1
    row = records[0].canonical_row
    assert row["source"] == "ashby:example"
    assert row["external_id"] == "job-1"
    assert row["company"] == "Example Co"
    assert row["work_mode"] == "hybrid"


def test_apsjobs_pdf_adapter_maps_vacancy_text() -> None:
    source = SourceDefinition(
        key="apsjobs:example",
        adapter="apsjobs-pdf",
        seeds=["https://www.apsjobs.gov.au/aps_VacancyDetailPage?id=a05EXAMPLE"],
    )
    text = """
    Salary
    $ 94125 to $ 104053
    Opportunity Type
    Full-Time;Part-Time
    Opportunity Status
    Ongoing;Non-Ongoing
    APS Classification
    APS Level 6
    Closing Date
    3/11/2026
    Job Category
    Data
    Office Arrangement
    Flexible
    Australian Institute of Health and Welfare
    Senior Data Analyst
    Canberra ACT
    The key duties of the position include:
    Analyse complex datasets using SQL, R and statistical models.
    Build dashboards and communicate insights to policy stakeholders.
    """

    row = ApsJobsPdfAdapter()._row_from_text(
        source,
        "https://www.apsjobs.gov.au/aps_VacancyDetailPage?id=a05EXAMPLE",
        text,
        datetime(2026, 5, 30, tzinfo=timezone.utc),
    )

    assert row is not None
    assert row["external_id"] == "a05EXAMPLE"
    assert row["title"] == "Senior Data Analyst"
    assert row["company"] == "Australian Institute of Health and Welfare"
    assert row["location"] == "Canberra ACT"
    assert row["salary_min"] == 94125
    assert row["salary_max"] == 104053


def test_detects_supported_source_urls() -> None:
    assert detect_source_from_url("https://jobs.lever.co/upguard/abc").key == "lever:upguard"
    assert detect_source_from_url("https://job-boards.greenhouse.io/roller/jobs/123").key == "greenhouse:roller"
    assert detect_source_from_url("https://jobs.ashbyhq.com/Checkbox%20Technology/abc").key == "ashby:checkbox-technology"
    generic = detect_source_from_url(
        "https://example.com/careers/software-engineer",
        '<script type="application/ld+json">{"@type":"JobPosting","title":"Software Engineer"}</script>',
    )
    assert generic is not None
    assert generic.adapter == "generic-jsonld"


def test_discovered_sources_render_registry() -> None:
    source = detect_source_from_url("https://jobs.ashbyhq.com/Checkbox%20Technology/abc")
    assert source is not None

    registry = discovered_sources_to_registry([source])

    assert registry["sources"][0]["key"] == "ashby:checkbox-technology"
    assert registry["sources"][0]["filters"] == {"country": "AU", "tech_only": True}


def test_source_filters_require_au_tech_signal() -> None:
    source = SourceDefinition(key="test", adapter="generic-jsonld", seeds=["https://example.com"])

    assert row_matches_source_filters(
        source,
        {"title": "Data Engineer", "location": "Sydney NSW", "description": "Python pipelines"},
    )
    assert row_matches_source_filters(
        source,
        {"title": "Principal Product Security Engineer", "location": "Melbourne, Australia", "description": ""},
    )
    assert not row_matches_source_filters(
        source,
        {"title": "Data Engineer", "location": "Austin, Texas", "description": "Python pipelines"},
    )
    assert not row_matches_source_filters(
        source,
        {
            "title": "DevOps Engineer",
            "location": "Christchurch, New Zealand",
            "description": "Build software for Australian customers.",
        },
    )
    assert row_matches_source_filters(
        source,
        {
            "title": "Senior Developer",
            "location": "Auckland, New Zealand, Melbourne, Australia",
            "description": "Build software.",
        },
    )
    assert not row_matches_source_filters(
        source,
        {"title": "Legal Counsel", "location": "Sydney NSW", "description": "Commercial contracts"},
    )
    assert not row_matches_source_filters(
        source,
        {
            "title": "Talent Acquisition Partner",
            "location": "Sydney, Australia",
            "description": "Support an AI-driven technology company.",
        },
    )


def test_load_source_registry(tmp_path: Path) -> None:
    path = tmp_path / "sources.yml"
    path.write_text(
        """
sources:
  - key: lever:example
    adapter: lever-html
    seeds:
      - https://jobs.lever.co/example
    filters:
      country: AU
      tech_only: true
""",
        encoding="utf-8",
    )

    sources = load_source_registry(path)

    assert len(sources) == 1
    assert sources[0].key == "lever:example"
    assert sources[0].filters.country == "AU"
