from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]


def _load_env_file() -> dict[str, str]:
    path = ROOT_DIR / ".env"
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    allowed_origins: str
    taxonomy_path: Path
    jobdata_api_key: str | None
    jobdata_base_url: str

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    env_file = _load_env_file()

    def get(name: str, default: str) -> str:
        return os.getenv(name) or env_file.get(name) or default

    return Settings(
        app_name="TechAtlas",
        environment=get("ENVIRONMENT", "development"),
        database_url=get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/techatlas"),
        allowed_origins=get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
        taxonomy_path=Path(get("TAXONOMY_PATH", str(ROOT_DIR / "ingestion" / "skills_taxonomy.yml"))),
        jobdata_api_key=get("JOBDATA_API_KEY", "") or None,
        jobdata_base_url=get("JOBDATA_BASE_URL", "https://jobdataapi.com/api/jobs/"),
    )
