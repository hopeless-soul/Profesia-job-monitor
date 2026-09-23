from pathlib import Path

from profesia_monitor.scraper import Query, scrape

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, name: str):
        self.text = (FIXTURES / name).read_text(encoding="utf-8")

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, pages: list[str]):
        self.pages = pages
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params, timeout):
        self.calls.append((url, params))
        return FakeResponse(self.pages[len(self.calls) - 1])


def test_query_uses_page_num_and_path_segments():
    q = Query("c#", segments=["bratislavsky-kraj"], remote_work=2, min_salary=2000, count_days=3)
    assert q.url() == "https://www.profesia.sk/praca/bratislavsky-kraj/"
    assert q.params(2) == {
        "search_anywhere": "c#",
        "sort_by": "relevance",
        "page_num": 2,
        "remote_work": 2,
        "salary": 2000,
        "salary_period": "m",
        "count_days": 3,
    }


def test_scrape_follows_pages_until_last():
    session = FakeSession(["listing_page1.html", "listing_last_page.html"])
    jobs = scrape(Query("c#"), max_pages=10, delay=0, session=session)

    assert [p["page_num"] for _, p in session.calls] == [1, 2]
    assert len(jobs) == 25


def test_scrape_dedupes_repeated_offers():
    session = FakeSession(["listing_page1.html"] * 2)
    assert len(scrape(Query("c#"), max_pages=2, delay=0, session=session)) == 20
