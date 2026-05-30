import re

from app.services.taxonomy import SkillDefinition, load_taxonomy


def _token_pattern(term: str) -> str:
    escaped = re.escape(term)
    return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"


class SkillMatcher:
    def __init__(self, definitions: list[SkillDefinition]):
        self._compiled: list[tuple[SkillDefinition, list[re.Pattern[str]]]] = []
        for definition in definitions:
            terms = [definition.name, *definition.aliases]
            pattern_texts = list(definition.patterns) or [_token_pattern(term) for term in terms]
            flags = 0 if definition.case_sensitive else re.IGNORECASE
            patterns = [re.compile(pattern, flags) for pattern in pattern_texts]
            self._compiled.append((definition, patterns))

    @classmethod
    def from_taxonomy(cls) -> "SkillMatcher":
        return cls(load_taxonomy())

    def extract(self, text: str) -> list[SkillDefinition]:
        found: list[SkillDefinition] = []
        seen: set[str] = set()
        normalized_text = text or ""
        for definition, patterns in self._compiled:
            if definition.name in seen:
                continue
            if any(pattern.search(normalized_text) for pattern in patterns):
                found.append(definition)
                seen.add(definition.name)
        return found
