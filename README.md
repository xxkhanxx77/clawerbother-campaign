# Renaiss Nitter Scraper

Scrapes public Nitter search results for `#renaiss` with Playwright and saves the data to CSV/JSONL.

The scraper:

- runs Chrome in hidden/headless mode by default
- uses `https://nitter.privacyredirect.com` as the default Nitter instance
- searches one day at a time across the date range (one navigation per day, gentler on Nitter rate limits)
- follows Nitter "Load more" cursor pages while preserving the active search/date filters
- spoofs the user-agent and hides `navigator.webdriver` to reduce bot detection
- appends to existing output files
- skips duplicate tweet IDs automatically

## Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The script uses your installed Google Chrome:

```text
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

## Run With Script

Use this shortcut for the default headless scrape:

```bash
./scripts/run_renaiss_headless.sh
```

That script runs a rolling 7-day scrape from today back to 7 days ago in headless mode:

```bash
TODAY="$(date +%d-%m-%Y)"
SEVEN_DAYS_AGO="$(date -v-7d +%d-%m-%Y)"
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from "$TODAY" \
  --date-to "$SEVEN_DAYS_AGO" \
  --profile-dir output/playwright-profile-clean
```

## Run Manually

After activating `.venv`, you can also run the Python module directly:

```bash
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026 \
  --profile-dir output/playwright-profile-clean \
  --headed
```

To scrape another tag:

```bash
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaissTH" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026 \
  --profile-dir output/playwright-profile-clean \
  --headed
```

## Output

For `#renaiss`, files are saved here:

```text
data/renaiss_posts.csv
data/renaiss_posts.jsonl
```

For `#renaissTH`, files are saved here:

```text
data/renaissth_posts.csv
data/renaissth_posts.jsonl
```

## Common Options

Show the browser window and use a fresh profile:

```bash
TODAY="$(date +%d-%m-%Y)"
SEVEN_DAYS_AGO="$(date -v-7d +%d-%m-%Y)"
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from "$TODAY" \
  --date-to "$SEVEN_DAYS_AGO" \
  --profile-dir output/playwright-profile-clean \
  --headed
```

Run the same scrape in headless mode:

```bash
TODAY="$(date +%d-%m-%Y)"
SEVEN_DAYS_AGO="$(date -v-7d +%d-%m-%Y)"
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from "$TODAY" \
  --date-to "$SEVEN_DAYS_AGO" \
  --profile-dir output/playwright-profile-clean
```

Slow down when Nitter returns HTTP 429:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026 \
  --between-days-seconds 30 \
  --navigation-retries 5 \
  --retry-delay-seconds 120
```

Overwrite existing output for the query:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026 \
  --fresh
```

Use another Nitter instance:

```bash
python -m src.renaiss_playwright_scraper \
  --instance "https://nitter.net" \
  --query "#renaiss" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026
```

The default instance is `https://nitter.privacyredirect.com`.

## Progress Output

Each page prints both extraction and save counters:

```text
2026-05-17 page 2: nitter.privacyredirect.com/search -> found 8, 8 matched, +0 saved, 8 duplicates, 0 skipped, 8 total new saved
```

- `found`: tweet cards extracted from the current page.
- `matched`: found tweets that match the active date/search filters.
- `+N saved`: new unique tweet IDs written from this page.
- `duplicates`: tweets already present in existing output or earlier pages.
- `skipped`: tweets outside the active date range or older than `--oldest-date`.

## Config File

Copy the example config:

```bash
cp scraper_config.example.json scraper_config.json
```

Run with config:

```bash
python -m src.renaiss_playwright_scraper --config scraper_config.json
```

CLI options override config values:

```bash
python -m src.renaiss_playwright_scraper \
  --config scraper_config.json \
  --query "#renaissTH"
```

## Notes

- Dates can be `DD-MM-YYYY` or `YYYY-MM-DD`.
- `--date-from` and `--date-to` are inclusive.
- Re-running the same command is safe because duplicate IDs are skipped.
- Nitter can rate-limit or fail. If you see HTTP 429, wait or use slower retry options.
