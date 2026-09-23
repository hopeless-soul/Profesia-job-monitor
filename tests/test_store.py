import json
from pathlib import Path

import jsonschema

from profesia_monitor.models import Job
from profesia_monitor.parser import parse_listing
from profesia_monitor.store import load_jobs, merge_jobs, save_jobs

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "jobs.schema.json").read_text(encoding="utf-8"))

T1 = "2026-09-23T10:00:00+00:00"
T2 = "2026-09-23T14:00:00+00:00"


def job(id: int, title: str = "Dev") -> Job:
    return Job(id=id, title=title, url=f"https://www.profesia.sk/praca/x/O{id}", company="X")


def test_merge_keeps_unique_ids_and_first_seen():
    existing, _ = merge_jobs([], [job(1, "Old title"), job(2)], seen_at=T1)
    merged, added = merge_jobs(existing, [job(1, "New title"), job(3)], seen_at=T2)

    assert sorted(j.id for j in merged) == [1, 2, 3]
    assert [j.id for j in added] == [3]
    by_id = {j.id: j for j in merged}
    assert by_id[1].title == "New title"
    assert (by_id[1].first_seen, by_id[1].last_seen) == (T1, T2)


def test_saved_file_matches_schema_and_round_trips(tmp_path):
    path = tmp_path / "jobs.json"
    html = (ROOT / "tests" / "fixtures" / "listing_page1.html").read_text(encoding="utf-8")
    jobs, _ = merge_jobs([], parse_listing(html)[0], seen_at=T1)

    save_jobs(path, jobs)

    jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), SCHEMA)
    assert load_jobs(path) == jobs
