from pathlib import Path

import pytest

from profesia_monitor.models import Salary
from profesia_monitor.parser import parse_listing, parse_salary

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2 250 EUR/mesiac", (2250, 2250, "EUR", "month")),
        ("Od 3 900 EUR/mesiac", (3900, None, "EUR", "month")),
        ("1 500 - 2 000 EUR/mesiac", (1500, 2000, "EUR", "month")),
        ("Od 5,50 EUR/hod.", (5.5, None, "EUR", "hour")),
        ("Dohodou", (None, None, None, None)),
    ],
)
def test_parse_salary(text, expected):
    s = parse_salary(text)
    assert (s.min, s.max, s.currency, s.period) == expected


def test_parse_listing_first_page():
    jobs, has_next = parse_listing(load("listing_page1.html"))

    assert has_next
    assert len({j.id for j in jobs}) == 20
    first = jobs[0]
    assert first.id == 5357568
    assert first.title == "Junior C#.NET programátor"
    assert first.url == "https://www.profesia.sk/praca/benu-phoenix/O5357568"
    assert first.company == "BENU / PHOENIX"
    assert first.company_id == 179822
    assert first.location == "F. Rákocziho 12, Nové Zámky"
    assert first.salary == Salary(raw="2 250 EUR/mesiac", min=2250, max=2250, currency="EUR", period="month")
    assert first.labels == ["Zabezpečená doprava"]
    assert first.posted_text == "Pred 2 týždňami"
