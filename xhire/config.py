"""Config loading: config.toml for behaviour, environment for the bearer token."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.toml"
DEFAULT_DB = REPO_ROOT / "posts.db"


class ConfigError(Exception):
    """Raised when config.toml or the environment is missing something required."""


@dataclass(frozen=True)
class Query:
    name: str
    query: str


@dataclass(frozen=True)
class Config:
    monthly_usd: float
    per_run_usd: float
    max_results: int
    max_pages: int
    queries: list[Query] = field(default_factory=list)


def _collapse(query: str) -> str:
    """Flatten a TOML multi-line query into the single line the API expects."""
    return re.sub(r"\s+", " ", query).strip()


def load_config(path: Path | None = None) -> Config:
    path = path or DEFAULT_CONFIG
    if not path.exists():
        raise ConfigError(
            f"No config at {path}. Copy config.example.toml to config.toml and edit it."
        )

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    budget = raw.get("budget", {})
    search = raw.get("search", {})

    queries = [
        Query(name=q["name"], query=_collapse(q["query"]))
        for q in raw.get("queries", [])
    ]
    if not queries:
        raise ConfigError(f"{path} defines no [[queries]] — nothing to search for.")

    max_results = int(search.get("max_results", 100))
    if not 10 <= max_results <= 100:
        raise ConfigError("search.max_results must be between 10 and 100.")

    return Config(
        monthly_usd=float(budget.get("monthly_usd", 25.0)),
        per_run_usd=float(budget.get("per_run_usd", 1.0)),
        max_results=max_results,
        max_pages=int(search.get("max_pages", 2)),
        queries=queries,
    )


def bearer_token() -> str:
    """Read the app-only bearer token, preferring the environment over .env."""
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        token = _read_dotenv_token(REPO_ROOT / ".env")
    if not token:
        raise ConfigError(
            "X_BEARER_TOKEN is not set. Put it in .env as X_BEARER_TOKEN=... "
            "or export it in your shell. See README.md for where to get one."
        )
    return token.strip()


def _read_dotenv_token(env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("X_BEARER_TOKEN="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return None
