# Salvage notes: Profesia.sk scraping

What can be kept from the forked `profesia_scrap.py`, and how Profesia.sk actually
exposes job listings. Site behaviour below was verified against the live site on
**2026-09-23** with plain `curl` requests (browser User-Agent). Profesia changes its
markup occasionally, so re-check selectors before relying on them.

Upstream: <https://github.com/Jarosek88/Profesia-job-monitor>

## TL;DR

- **No browser needed.** Listing pages are server-rendered HTML. A plain HTTP GET with
  a browser User-Agent returns the full list of job cards. Playwright is unnecessary overhead.
- **The original script pages incorrectly.** It sends `?page=N`; the site ignores that
  and uses `page_num=N`. Every "page" it scraped was page 1.
- **The original salary selector is dead.** `.label-info` no longer exists; every salary
  came out as `"Dohodou"`.
- **The original URL is stale.** `/praca/c-sharp/?search_anywhere=c%23` now redirects to
  `/praca/?search_anywhere=c%23&sort_by=relevance`.
- **Use the numeric offer ID for dedup**, not `(title, company)`.

## What the original script does

`profesia_scrap.py` runs one pipeline:

1. Launches headed Chromium via Playwright, visits 3 listing pages for keyword `c#`.
2. Selects `article` (falls back to `li.list-row`), reads `h2`, `.employer`, `.label-info`.
3. Loads previous rows from SQLite (`moje_hladanie_prace.db`, table `ponuky`), keeps
   rows whose `(pozicia, firma)` pair is new, appends them.
4. Emails new rows as a plain-text table through `smtp.seznam.cz:465`.
5. Opens a matplotlib bar chart of the top 10 companies (`plt.show()`, blocking).

### Worth keeping

- The overall idea: scrape → diff against local store → notify on new rows only.
- SQLite as a zero-setup local store.
- Polite delay between page requests.

### Discard or rewrite

| Area | Problem |
|---|---|
| Fetching | Playwright + `headless=False` + 5 s fixed wait. Not needed; blocks scheduled runs. |
| Pagination | `page=` is ignored by the site (see [Pagination](#pagination)). |
| Selectors | `article` never matches; `.label-info` never matches. |
| Title parsing | If a card has no `h2`, `title` is unbound or keeps the previous card's value. |
| Filtering | `zakazane = []` — the "senior" filter is empty and does nothing. |
| Dedup key | `(pozicia, firma)` merges reposts and distinct offers with the same title. |
| Errors | Bare `except:` everywhere; one page error `break`s the whole run. |
| Secrets | SMTP credentials hardcoded as `"MAIL"` / `"HESLO"`. |
| Text | Subject and chart title say "Python" while the search is `c#`. |
| Output | `plt.show()` blocks; no file output. |
| Packaging | No `requirements.txt`, README, or tests. |

## Profesia.sk: how listings are exposed

### URL structure

```
https://www.profesia.sk/praca/[<segment>/[<segment>/...]]?<query params>
```

Filters come in two kinds:

- **Path segments**: region, position, employment type, work area, company type, language.
  Segments can be chained: `/praca/bratislavsky-kraj/informacne-technologie/` returned
  results.
- **Query parameters**: keyword, remote work, salary, recency, sort, page.

Localized mirrors exist (`/en/work/`, `/cz/prace/`, `/de/arbeit-suchen/`, `/hu/allas/`),
but `robots.txt` disallows `/en/*?`, `/cz/`, `/de/`, `/hu/*?`. Stick to the Slovak `/praca/`.

### Query parameters

| Param | Values | Meaning |
|---|---|---|
| `search_anywhere` | free text, URL-encoded (`c%23` = `c#`) | Keyword search across the offer |
| `sort_by` | `relevance` | Only value observed. `date` / `salary` returned identical ordering, so they appear unsupported. |
| `page_num` | `1`, `2`, … | Page number (20 offers per page) |
| `remote_work` | `0` on-site only · `1` remote only · `2` partially remote | Work-from-home filter |
| `salary` + `salary_period` | monthly: `salary_period=m`, `salary` ∈ 600, 800, 1000, 1300, 1500, 1800, 2000, 2500 · hourly: `salary_period=h`, `salary` ∈ 4, 5, 6, 8, 10, 12, 15 | Minimum salary in EUR. Sidebar only offers these presets; other values untested. |
| `count_days` | any positive integer (sidebar presets: `1`, `2`, `7`, `31`) | Offers posted within N days. Values ≥ 31 return everything (offers expire after ~a month). Non-numeric values like `3m` are dropped. **Disallowed in `robots.txt`**. |

### Path-segment filters

Slugs as seen in the sidebar for a `c#` search. The sidebar only lists values that have
hits for the current query; each group has a `zoznam-*` link to the full list.

| Group (sidebar label) | Example slugs | Full list |
|---|---|---|
| Region (*Kraje*) | `bratislavsky-kraj`, `zilinsky-kraj`, `trenciansky-kraj`, `kosicky-kraj`, `nitriansky-kraj`, `trnavsky-kraj`, `zahranicie` (abroad) | `/praca/zoznam-lokalit/` |
| Position (*Pozícia*) | `programator-programatorka`, `dotnet-programator-programatorka`, `csharp-programator-programatorka`, `softverovy-inzinier-softverova-inzinierka` | `/praca/zoznam-pozicii/` |
| Employment type (*Druh pracovného pomeru*) | `plny-uvazok`, `skrateny-uvazok`, `na-dohodu-brigady`, `zivnost`, `internship-staz` | — |
| Work area (*Pracovná oblasť*) | `informacne-technologie`, `elektrotechnika-a-energetika`, `strojarstvo`, `administrativa` | `/praca/zoznam-pracovnych-oblasti/` |
| Company type (*Ponuky spoločnosti*) | `zamestnavatelia` (direct employers), `personalne-agentury` (agencies), `top-klienti` | `/praca/zoznam-spolocnosti/` |
| Language (*Jazykové znalosti*) | `anglicky-jazyk`, `slovensky-jazyk`, `nemecky-jazyk`, `francuzsky-jazyk` | `/praca/zoznam-jazykovych-znalosti/` |

Tip: the sidebar links carry the hit count per filter value, so scraping the sidebar
of page 1 gives cheap aggregate stats without fetching every page.

### Pagination

- 20 offers per page.
- Page parameter is `page_num`. `page` is silently ignored (returns page 1).
- Range shown in `.offer-counter` (e.g. `1 - 20`, `21 - 40`).
- `<link rel="next" href="...">` in `<head>` and `ul.pagination a.next` point to the next page.
- A page past the end returns HTTP 200 with **zero** `li.list-row` elements. Stop on
  that, or when `rel="next"` is absent.

### Listing card markup

Each offer is an `li.list-row` inside `ul.list` in `<main>`:

```html
<li class="list-row">
  <a href="/praca/benu-phoenix/C179822" class="offer-company-logo-link">…logo…</a>
  <h2><a id="offer5357568" href="/praca/benu-phoenix/O5357568?search_id=…">
    <span class="title">Junior C#.NET programátor</span></a></h2>
  <span class="employer">BENU / PHOENIX</span>
  <span class="job-location" title="F. Rákocziho 12, Nové Zámky">F. Rákocziho 12, Nové Zámky</span>
  <span class="label-group">
    <a data-dimension7="Salary label" …><span class="label …"><svg class="icon money green">…</svg> 2 250 EUR/mesiac</span></a>
    <a data-dimension15="Transport label" …><span class="label …"><svg class="icon bus green">…</svg> Zabezpečená doprava</span></a>
  </span>
  <div class="list-footer">
    <span class="info"><strong>Pred 2 týždňami</strong></span>
    <a class="star action" data-offer-id="5357568" …>Uložiť ponuku</a>
  </div>
</li>
```

| Field | Selector | Notes |
|---|---|---|
| Offer ID | `h2 a[id^=offer]` → strip `offer`; or `a.star[data-offer-id]` | Stable numeric ID. **Use as primary key.** |
| Title | `h2 .title` | |
| Detail URL | `h2 a[href]` | Relative; strip the `search_id` query param to get a canonical URL `/praca/<company-slug>/O<id>`. |
| Company | `.employer` | |
| Company page | `a.offer-company-logo-link[href]` | `/praca/<slug>/C<company-id>`, gives a stable company ID. Not every card has a logo link. |
| Location | `.job-location` (full text in `title` attr) | May include remote notes, e.g. "(Job with occasional home office)". |
| Salary | `.label-group a[data-dimension7="Salary label"]`, or the `.label` containing `svg.icon.money` | Free text: `2 250 EUR/mesiac`, `Od 3 900 EUR/mesiac`. Present on all 65 `c#` offers checked (Slovak law requires a base salary in job ads), but still handle a missing label. |
| Other labels | other `.label-group .label` | e.g. transport provided (`svg.icon.bus`). |
| Posted | `.list-footer .info strong` | Relative Slovak text ("Pred 2 týždňami"). Exact date only on the detail page. |

Salary strings use a space as thousands separator and a period suffix
(`/mesiac` monthly, `/hod.` hourly). Parse into `min`, `max`, `currency`, `period`
rather than storing raw text only.

### Detail page

`https://www.profesia.sk/praca/<company-slug>/O<offer-id>`

- `h1` holds the title.
- `.salary-range` has the salary; `.salary-desc` has the salary note (bonuses etc.).
- `[itemprop=datePosted]` has the posted date (hidden span).
- `[data-offer-id]` holds the offer ID.
- Section headings (`h3`/`h4`) include *Informácie o pracovnom mieste*,
  *Náplň práce…*, *Zamestnanecké výhody, benefity*, *Požiadavky na zamestnanca*,
  *Pozícii vyhovujú uchádzači so vzdelaním*, *Osobnostné predpoklady a zručnosti*.
- There's no `application/ld+json` JobPosting block.
- **Layout varies by employer.** Some companies use custom designs
  (e.g. `/customdesigns/BenuSk/...` assets, `upper-info-box-*` classes). Treat detail
  parsing as best-effort; the listing card has everything needed for notifications.

### Etiquette and constraints

- Listing pages send `<meta name="robots" content="noindex, nofollow">`. `robots.txt`
  allows `/praca/` but disallows `count_days=`, `*ajax`, `*print=1`, the localized
  query URLs, and various `*.php` endpoints.
- Keep volume low: a few pages per run, a delay of ≥1 s between requests, and a
  run no more than every few hours. A monitor needs only the first 1–3 pages sorted by
  relevance plus local "seen IDs" state.
- There's no public RSS (`/rss/` returns 404) and no public JSON API.
- **Built-in alternative:** Profesia has its own email job agent ("Ponuky e-mailom",
  `/agent/`), which works for any search. If you just want email alerts, it may make
  this project unnecessary. Scraping is only worth it for custom filtering, storage,
  or stats.

## Minimal reference fetch

Proof that `requests` + BeautifulSoup is enough (not production code):

```python
import re, time, requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BASE = "https://www.profesia.sk"

def fetch(keyword: str, max_pages: int = 3, **filters):
    for page in range(1, max_pages + 1):
        params = {"search_anywhere": keyword, "sort_by": "relevance", "page_num": page, **filters}
        r = requests.get(f"{BASE}/praca/", params=params, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        rows = BeautifulSoup(r.text, "html.parser").select("li.list-row")
        if not rows:
            break
        for row in rows:
            link = row.select_one("h2 a[id^=offer]")
            if not link:
                continue
            salary = row.select_one('a[data-dimension7="Salary label"]')
            yield {
                "id": int(link["id"].removeprefix("offer")),
                "title": link.get_text(strip=True),
                "url": BASE + link["href"].split("?")[0],
                "company": (e := row.select_one(".employer")) and e.get_text(strip=True),
                "location": (l := row.select_one(".job-location")) and l.get_text(strip=True),
                "salary": salary and re.sub(r"\s+", " ", salary.get_text(strip=True)),
            }
        time.sleep(1.5)

# e.g. fetch("c#", remote_work=2, salary=2000, salary_period="m")
```

## Open items to verify when rebuilding

- Whether `salary` accepts values other than the sidebar presets.
- Whether multiple values of the same path group can be combined (e.g. two regions).
- Hourly salary label format on real listings (`/hod.` assumed).
- Whether any other `sort_by` value exists (only `relevance` seen in markup).
