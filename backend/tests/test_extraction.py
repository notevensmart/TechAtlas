from app.services.extraction import SkillMatcher
from app.services.taxonomy import load_taxonomy


def matcher() -> SkillMatcher:
    return SkillMatcher(load_taxonomy())


def names(text: str) -> set[str]:
    return {skill.name for skill in matcher().extract(text)}


def test_extracts_aliases_and_whole_words() -> None:
    found = names("We build Python services with Amazon Web Services, React.js and CI/CD.")
    assert {"Python", "AWS", "React", "CI/CD"} <= found


def test_go_does_not_match_inside_django() -> None:
    found = names("Django backend role with PostgreSQL.")
    assert "Django" in found
    assert "Go" not in found


def test_case_sensitive_r_reduces_false_positives() -> None:
    assert "R" in names("Experience with R and statistics is useful.")
    assert "R" not in names("You are responsible for reliable reporting.")


def test_ai_ml_terms_are_first_class() -> None:
    found = names("AI Engineer role using LLMs, RAG, embeddings, LangChain, vector databases and PyTorch.")
    assert {"LLMs", "RAG", "Embeddings", "LangChain", "Vector Databases", "PyTorch"} <= found

