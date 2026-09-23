# Profesia job monitor

> [!IMPORTANT]
> The project is mainly vibe coded, so it's probably poorly structured.

Watches [Profesia.sk](https://www.profesia.sk) for new job offers. It runs continuously, scrapes your searches once an hour, keeps every offer (unique by ID) in `jobs.json`, and sends new ones to Telegram subscribers.

## Setup

Requires Python 3.10+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy config.example.json config.json   # Linux/macOS: cp
```

Edit `config.json` to set your searches (see [Configuration](#configuration)).

## Running

With the virtual environment active, run from the repo folder:

```powershell
python -m profesia_monitor
```

It scrapes straight away, then every `interval` minutes (60 by default). It keeps running until you press Ctrl+C. Each round prints the offer count per search and a `NEW …` line for every offer it hasn't seen before.

Run it as `python -m profesia_monitor`. `python profesia_monitor` doesn't work because the folder is a package, not a script.

Common options:

| Option | Meaning |
|---|---|
| `--once` | Scrape once and exit |
| `--interval 30` | Minutes between scrapes |
| `-c other.json` | Use a different config file |
| `--days 3` | Only offers posted in the last N days (all searches) |
| `--pages 1` | Max listing pages per search (20 offers per page) |
| `--out file.json` | Where to store jobs |
| `--no-notify` | Don't send Telegram messages |
| `--log monitor.log` | Append output to a file instead of the console |
| `-v` | Verbose logging |

Try a one-off search without touching the config:

```powershell
python -m profesia_monitor "c#" --segment bratislavsky-kraj --remote 2 --min-salary 2000 --once
```

Run `python -m profesia_monitor --help` for everything.

### Keeping it running in the background (Windows)

`pythonw` runs without a console window, and `--log` captures the output:

```powershell
Start-Process .venv\Scripts\pythonw.exe -ArgumentList "-m profesia_monitor --log monitor.log" -WorkingDirectory $PWD
```

To stop it, end the `pythonw.exe` process in Task Manager.

## Configuration

`config.json` is read from the current folder. It is git-ignored because it holds your bot token. Its schema is in `schemas/config.schema.json`, so editors such as VS Code autocomplete and validate it.

```json
{
  "$schema": "./schemas/config.schema.json",
  "out": "jobs.json",
  "pages": 3,
  "delay": 1.5,
  "interval": 60,
  "count_days": 3,
  "searches": [
    { "keyword": "frontend" },
    { "keyword": "c#", "segments": ["bratislavsky-kraj"], "remote_work": 2, "min_salary": 2000 }
  ],
  "telegram": {
    "token": "123456:ABC-your-bot-token",
    "subscribers": "subscribers.json"
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `out` | `jobs.json` | Jobs file. Relative paths resolve against the config's folder |
| `pages` | `3` | Max pages per search |
| `delay` | `1.5` | Seconds between page requests. Be polite to the site |
| `interval` | `60` | Minutes between scrapes |
| `count_days` | none | Only offers from the last N days. 31 or more means no filter. A search can override it |
| `searches[].keyword` | required | Free-text search |
| `searches[].segments` | `[]` | Path filters: region (`bratislavsky-kraj`), work area (`informacne-technologie`), employment type (`plny-uvazok`), language (`anglicky-jazyk`) and so on |
| `searches[].remote_work` | any | `0` on-site, `1` remote, `2` partially remote |
| `searches[].min_salary` | none | Minimum salary in EUR |
| `searches[].salary_period` | `m` | `m` monthly or `h` hourly (used with `min_salary`) |
| `searches[].count_days` | top-level value | Per-search override |
| `telegram.token` | none | Bot token. Falls back to the `TELEGRAM_BOT_TOKEN` env variable. With neither, Telegram is off |
| `telegram.subscribers` | `subscribers.json` | Subscriber list |

All results from all searches are merged into one file. An offer found by several searches is stored once.

`salvage.md` lists all available filters and how the site is parsed.

## Telegram notifications

1. Create a bot with [@BotFather](https://t.me/BotFather) and put its token in `config.json` under `telegram.token`.
2. Start the monitor.
3. Each person who wants notifications opens the bot and sends **`/start`**. **`/stop`** unsubscribes.

While the monitor runs, the bot answers commands within seconds. After each scrape, every subscriber gets the new offers (title linked to the offer, company, location and salary), grouped into as few messages as possible. People who block the bot are removed automatically. Subscribers are saved in `subscribers.json`.

Only one copy of the monitor can use a given bot at a time, because Telegram lets only one process read its messages.

## Output

`jobs.json` (format: `schemas/jobs.schema.json`):

```json
{
  "schema_version": 1,
  "updated_at": "2026-09-23T10:00:00+00:00",
  "jobs": [
    {
      "id": 4812345,
      "title": "Frontend Developer (Vue.js)",
      "url": "https://www.profesia.sk/praca/.../O4812345",
      "company": "ACME s.r.o.",
      "company_id": 12345,
      "location": "Bratislava",
      "salary": { "raw": "Od 2 500 EUR/mesiac", "min": 2500, "max": null, "currency": "EUR", "period": "month" },
      "labels": [],
      "posted_text": "Nová",
      "first_seen": "2026-09-23T10:00:00+00:00",
      "last_seen": "2026-09-23T10:00:00+00:00"
    }
  ]
}
```

`first_seen` stays fixed and `last_seen` is updated on every scrape that finds the offer. Newest offers come first.

## Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Tests run offline against saved HTML pages in `tests/fixtures/`.
