import json
from pathlib import Path

import jsonschema
import pytest

from profesia_monitor.__main__ import build_parser, resolve_config
from profesia_monitor.config import ConfigError, load_config, parse_config
from profesia_monitor.scraper import Query

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "config.example.json"
SCHEMA = json.loads((ROOT / "schemas" / "config.schema.json").read_text(encoding="utf-8"))


def test_example_config_is_valid():
    jsonschema.validate(json.loads(EXAMPLE.read_text(encoding="utf-8")), SCHEMA)
    config = load_config(EXAMPLE)
    assert config.out == ROOT / "jobs.json"
    assert config.searches[0] == Query("c#", ["bratislavsky-kraj"], 2, 2000, "m", 7)


def test_count_days_default_and_override():
    config = parse_config({"count_days": 3, "searches": [{"keyword": "a"}, {"keyword": "b", "count_days": 7}]})
    assert [q.count_days for q in config.searches] == [3, 7]


def test_invalid_config_names_the_field():
    with pytest.raises(ConfigError, match=r"searches\[0\].remote_work"):
        parse_config({"searches": [{"keyword": "c#", "remote_work": 5}]})


def test_cli_flags_override_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"pages": 2, "searches": [{"keyword": "python"}]}), encoding="utf-8")
    parser = build_parser()

    config = resolve_config(parser.parse_args(["c#", "--config", str(path), "--pages", "5", "--days", "1", "--interval", "15"]), parser)

    assert config.searches == [Query("c#", count_days=1)]
    assert config.pages == 5
    assert config.interval == 15
    assert config.out == tmp_path / "jobs.json"
