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
    """Return an app-only bearer token.

    Accepts either credential the developer console hands out: a bearer token
    directly, or the API Key / Secret pair, which is exchanged for one. The
    exchange is free, so there is no reason to make the user hunt for the
    bearer token if they already have the pair.
    """
    env = _load_env(REPO_ROOT / ".env")

    token = os.environ.get("X_BEARER_TOKEN") or env.get("X_BEARER_TOKEN")
    if token:
        return token.strip()

    api_key = os.environ.get("X_API_KEY") or env.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET") or env.get("X_API_SECRET")
    if api_key and api_secret:
        from .auth import bearer_from_key_pair

        return bearer_from_key_pair(api_key.strip(), api_secret.strip())

    raise ConfigError(
        "No X credentials found. Put EITHER of these in .env:\n"
        "  X_BEARER_TOKEN=AAAA...        (one long string, starts with AAAA)\n"
        "or the API Key / Secret pair from the same console page:\n"
        "  X_API_KEY=...                 (25 characters)\n"
        "  X_API_SECRET=...              (50 characters)\n"
        "See README.md."
    )


def _load_env(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Blank lines and # comments are skipped."""
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values
