from app.services.crawler import (
    discover_job_links,
    extract_jobposting_nodes,
    map_jobposting_node,
)


def test_extracts_jobposting_from_jsonld_graph() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {"@type": "Organization", "name": "Example Co"},
            {
              "@type": "JobPosting",
              "title": "AI Engineer",
              "description": "Build <b>RAG</b> systems with Python.",
              "datePosted": "2026-05-01",
              "hiringOrganization": {"name": "Example Co"},
              "jobLocation": {
                "@type": "Place",
                "address": {
                  "addressLocality": "Sydney",
                  "addressRegion": "NSW",
                  "addressCountry": "AU"
                }
              }
            }
          ]
        }
        </script>
      </head>
    </html>
    """

    nodes = extract_jobposting_nodes(html)

    assert len(nodes) == 1
    assert nodes[0]["title"] == "AI Engineer"


def test_maps_jobposting_to_canonical_import_row() -> None:
    row = map_jobposting_node(
        {
            "@type": "JobPosting",
            "identifier": {"value": "job-123"},
            "title": "Senior Backend Engineer",
            "description": "Build Python APIs on AWS.",
            "datePosted": "2026-05-01",
            "employmentType": "FULL_TIME",
            "hiringOrganization": {"name": "Example Co"},
            "baseSalary": {
                "currency": "AUD",
                "value": {"minValue": 130000, "maxValue": 160000, "unitText": "YEAR"},
            },
            "jobLocation": {
                "address": {
                    "addressLocality": "Melbourne",
                    "addressRegion": "VIC",
                    "addressCountry": "AU",
                }
            },
        },
        "https://example.com/careers/job-123",
    )

    assert row is not None
    assert row["source"] == "crawler:example.com"
    assert row["external_id"] == "job-123"
    assert row["company"] == "Example Co"
    assert row["location"] == "Melbourne, VIC, AU"
    assert row["salary_min"] == 130000
    assert row["salary_period"] == "annual"


def test_remote_jobposting_maps_work_mode() -> None:
    row = map_jobposting_node(
        {
            "@type": "JobPosting",
            "title": "Cloud Engineer",
            "description": "Kubernetes and Terraform role.",
            "datePosted": "2026-05-01",
            "hiringOrganization": {"name": "Example Co"},
            "jobLocationType": "TELECOMMUTE",
        },
        "https://example.com/jobs/cloud",
    )

    assert row is not None
    assert row["location"] == "Remote"
    assert row["work_mode"] == "remote"


def test_discovers_same_host_job_links_only() -> None:
    html = """
    <a href="/careers/backend-engineer">Backend</a>
    <a href="/about">About</a>
    <a href="https://other.example/jobs/1">Other</a>
    """

    links = discover_job_links("https://example.com/careers", html)

    assert links == ["https://example.com/careers/backend-engineer"]

