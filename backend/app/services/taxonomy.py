from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Skill


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    category: str
    aliases: tuple[str, ...]
    patterns: tuple[str, ...]
    case_sensitive: bool = False


def load_taxonomy(path: Path | None = None) -> list[SkillDefinition]:
    taxonomy_path = path or get_settings().taxonomy_path
    with taxonomy_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    skills = []
    for item in raw.get("skills", []):
        skills.append(
            SkillDefinition(
                name=item["name"],
                category=item["category"],
                aliases=tuple(item.get("aliases", [])),
                patterns=tuple(item.get("patterns", [])),
                case_sensitive=bool(item.get("case_sensitive", False)),
            )
        )
    return skills


def seed_skills(session: Session, taxonomy_path: Path | None = None) -> int:
    definitions = load_taxonomy(taxonomy_path)
    existing = {skill.name: skill for skill in session.scalars(select(Skill)).all()}
    changed = 0

    for definition in definitions:
        skill = existing.get(definition.name)
        aliases = list(definition.aliases)
        patterns = list(definition.patterns)
        if skill is None:
            session.add(
                Skill(
                    name=definition.name,
                    category=definition.category,
                    aliases=aliases,
                    patterns=patterns,
                    case_sensitive=definition.case_sensitive,
                )
            )
            changed += 1
            continue

        if (
            skill.category != definition.category
            or skill.aliases != aliases
            or skill.patterns != patterns
            or skill.case_sensitive != definition.case_sensitive
        ):
            skill.category = definition.category
            skill.aliases = aliases
            skill.patterns = patterns
            skill.case_sensitive = definition.case_sensitive
            changed += 1

    return changed

