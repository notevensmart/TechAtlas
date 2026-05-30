from app.services.normalization import (
    infer_experience_level,
    infer_role_family,
    normalize_city,
    normalize_salary,
    normalize_work_mode,
)


def test_normalize_city_buckets_remote_and_major_cities() -> None:
    assert normalize_city("Sydney NSW") == "Sydney"
    assert normalize_city("Remote - Australia") == "Remote"
    assert normalize_city("Regional NSW") == "Other"


def test_ai_ml_role_family_is_first_class() -> None:
    assert infer_role_family("Machine Learning Engineer", "", None) == "AI/ML Engineering"
    assert infer_role_family("AI Engineer", "", None) == "AI/ML Engineering"
    assert (
        infer_role_family(
            "Senior AI Engineer",
            "Build reliable software systems with Python.",
            "Senior AI Engineer",
        )
        == "AI/ML Engineering"
    )


def test_specific_title_role_family_beats_broad_description() -> None:
    assert (
        infer_role_family("Frontend Software Engineer", "Backend platform services.", None)
        == "Frontend"
    )
    assert (
        infer_role_family("Lead Data Engineer", "Build AI-enabled analytics systems.", None)
        == "Data Analytics"
    )
    assert infer_role_family("Fullstack Engineer", "React frontend work.", None) == "Software Engineering"
    assert infer_role_family("Platform Engineer", "Frontend developer tooling.", None) == "Cloud"
    assert infer_role_family("Principal Product Security Engineer", "Cloud security.", None) == "DevOps"
    assert infer_role_family("Salesforce Engineer", "Sales operations tooling.", None) == "Backend"


def test_unknown_seniority_is_not_defaulted_to_mid() -> None:
    assert infer_experience_level("Software Engineer", "Build APIs") == "unknown"
    assert infer_experience_level("Senior Backend Engineer", "Build APIs") == "senior"


def test_work_mode_inference() -> None:
    assert normalize_work_mode(None, "Backend Engineer", "Hybrid role in Melbourne") == "hybrid"
    assert normalize_work_mode("remote", "Backend Engineer", "") == "remote"
    assert normalize_work_mode(None, "Backend Engineer", "Office-based team") == "onsite"


def test_salary_normalization_to_annual() -> None:
    assert normalize_salary(1000, 1200, "daily") == (260000, 312000, 286000)
    assert normalize_salary(120000, 140000, "annual") == (120000, 140000, 130000)
