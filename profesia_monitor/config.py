"""Load config.json. See config.example.json for the format."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .scraper import Query

_QUERY_KEYS = {"keyword", "segments", "remote_work", "min_salary", "salary_period", "count_days"}
_TOP_KEYS = {"$schema", "out", "pages", "delay", "count_days", "searches", "telegram", "interval"}
_TELEGRAM_KEYS = {"token", "subscribers"}


class ConfigError(ValueError):
    pass


@dataclass
class TelegramConfig:
    token: str | None = None  # falls back to the TELEGRAM_BOT_TOKEN env var
    subscribers: Path = Path("subscribers.json")


@dataclass
class Config:
    searches: list[Query] = field(default_factory=list)
    out: Path = Path("jobs.json")
    pages: int = 3
    delay: float = 1.5
    interval: float = 60  # minutes between scrapes
    telegram: TelegramConfig = field(default_factory=TelegramConfig)


def _count_days(value: object, where: str) -> int | None:
    if value is not None and (not isinstance(value, int) or value < 1):
        raise ConfigError(f"{where}: expected a positive integer (days) or null")
    return value


def _query(raw: object, where: str, default_days: int | None) -> Query:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected an object")
    if unknown := raw.keys() - _QUERY_KEYS:
        raise ConfigError(f"{where}: unknown keys {sorted(unknown)}")
    keyword = raw.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ConfigError(f"{where}.keyword: required non-empty string")
    segments = raw.get("segments", [])
    if not isinstance(segments, list) or not all(isinstance(s, str) for s in segments):
        raise ConfigError(f"{where}.segments: expected a list of strings")
    remote = raw.get("remote_work")
    if remote not in (None, 0, 1, 2):
        raise ConfigError(f"{where}.remote_work: expected 0, 1, 2 or null")
    min_salary = raw.get("min_salary")
    if min_salary is not None and (not isinstance(min_salary, int) or min_salary <= 0):
        raise ConfigError(f"{where}.min_salary: expected a positive integer or null")
    period = raw.get("salary_period", "m")
    if period not in ("m", "h"):
        raise ConfigError(f"{where}.salary_period: expected 'm' or 'h'")
    days = _count_days(raw.get("count_days", default_days), f"{where}.count_days")

    query = Query(keyword, segments, remote, min_salary, period, days)
    try:
        query.url()
    except ValueError as e:
        raise ConfigError(f"{where}.segments: {e}") from None
    return query


def _telegram(raw: object) -> TelegramConfig:
    if raw is None:
        return TelegramConfig()
    if not isinstance(raw, dict):
        raise ConfigError("telegram: expected an object")
    if unknown := raw.keys() - _TELEGRAM_KEYS:
        raise ConfigError(f"telegram: unknown keys {sorted(unknown)}")
    token = raw.get("token")
    if token is not None and not isinstance(token, str):
        raise ConfigError("telegram.token: expected a string or null")
    subscribers = raw.get("subscribers", "subscribers.json")
    if not isinstance(subscribers, str) or not subscribers:
        raise ConfigError("telegram.subscribers: expected a file path")
    return TelegramConfig(token or None, Path(subscribers))


def parse_config(data: object) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("config: expected an object")
    if unknown := data.keys() - _TOP_KEYS:
        raise ConfigError(f"config: unknown keys {sorted(unknown)}")

    searches = data.get("searches", [])
    if not isinstance(searches, list) or not searches:
        raise ConfigError("searches: expected a non-empty list")
    pages = data.get("pages", 3)
    if not isinstance(pages, int) or pages < 1:
        raise ConfigError("pages: expected a positive integer")
    delay = data.get("delay", 1.5)
    if not isinstance(delay, (int, float)) or delay < 0:
        raise ConfigError("delay: expected a non-negative number")
    interval = data.get("interval", 60)
    if not isinstance(interval, (int, float)) or isinstance(interval, bool) or interval <= 0:
        raise ConfigError("interval: expected a positive number of minutes")
    out = data.get("out", "jobs.json")
    if not isinstance(out, str) or not out:
        raise ConfigError("out: expected a file path")
    days = _count_days(data.get("count_days"), "count_days")

    return Config(
        searches=[_query(s, f"searches[{i}]", days) for i, s in enumerate(searches)],
        out=Path(out),
        pages=pages,
        delay=float(delay),
        interval=float(interval),
        telegram=_telegram(data.get("telegram")),
    )


def load_config(path: Path) -> Config:
    """Load and validate a config file. Relative paths resolve against the config's folder."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON ({e})") from None
    config = parse_config(data)
    if not config.out.is_absolute():
        config.out = path.parent / config.out
    if not config.telegram.subscribers.is_absolute():
        config.telegram.subscribers = path.parent / config.telegram.subscribers
    return config
