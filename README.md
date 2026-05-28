# Renaiss Nitter Scraper

Scrapes public Nitter search results for `#renaiss` with Playwright and saves the data to CSV/JSONL.

The scraper:

- runs Chrome in hidden/headless mode by default
- searches one day at a time across the date range
- follows Nitter "Load more" pages
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

Use this shortcut for the default scrape:

```bash
./scripts/run_renaiss.sh
```

That runs:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
```

## Run Manually

After activating `.venv`, you can also run the Python module directly:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
```

To scrape another tag:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaissTH" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
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

Show the browser window:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --headed
```

Slow down when Nitter returns HTTP 429:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --between-days-seconds 30 \
  --navigation-retries 5 \
  --retry-delay-seconds 120
```

Overwrite existing output for the query:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --fresh
```

Use another Nitter instance:

```bash
python -m src.renaiss_playwright_scraper \
  --instance "https://nitter.net" \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
```

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
