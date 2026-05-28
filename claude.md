# Project Notes: Renaiss Nitter Scraper

This project is a Playwright-only scraper for public Nitter search pages. The old `ntscraper` and BrightData flows are no longer used.

## Main Files

- `src/renaiss_playwright_scraper.py`: main scraper module.
- `scripts/run_renaiss.sh`: shortcut script for the default `#renaiss` scrape.
- `scraper_config.example.json`: editable example config.
- `data/renaiss_posts.csv`: normalized CSV output.
- `data/renaiss_posts.jsonl`: raw scraped item output.
- `output/playwright/`: debug screenshots/HTML when scraping fails.
- `output/playwright-profile/`: persistent Chrome profile used by Playwright.

## Default Run

Use the script:

```bash
./scripts/run_renaiss.sh
```

Equivalent manual command:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
```

The scraper runs headless by default. Use `--headed` only when debugging or when a manual browser check is needed.

## Flow

1. CLI args and optional JSON config are merged in `resolve_args`.
2. The query is converted into a Nitter search URL with `build_search_url`.
3. If `--date-from` and `--date-to` are provided, `build_search_targets` creates one search URL per day.
4. Each daily URL uses Nitter `since=YYYY-MM-DD` and `until=YYYY-MM-DD` filters.
5. Playwright launches Google Chrome with a persistent profile.
6. The scraper opens the first page for the day.
7. `extract_tweets` runs JavaScript in the page to read `.timeline-item` tweet cards.
8. Each item is normalized into CSV fields by `normalize_tweet`.
9. Existing CSV/JSONL outputs are loaded first unless `--fresh` is used.
10. Duplicate posts are skipped by tweet ID, URL, Nitter URL, or description fallback.
11. After each page with new data, the scraper checkpoint-saves CSV and JSONL.
12. `find_next_page_url` follows the Nitter "Load more" link until `--max-pages` is reached or no next page exists.

## Output Naming

The output base name is derived from the query:

- `#renaiss` -> `data/renaiss_posts.csv` and `data/renaiss_posts.jsonl`
- `#renaissTH` -> `data/renaissth_posts.csv` and `data/renaissth_posts.jsonl`

Use `--output-base` to override this.

## Important Options

- `--query "#renaiss"`: hashtag or search wording.
- `--date-from 28-05-2026`: newest date in the inclusive range.
- `--date-to 20-05-2026`: oldest date in the inclusive range.
- `--number 1000`: maximum new posts to save.
- `--max-pages 8`: max "Load more" pages per day.
- `--fresh`: overwrite existing output instead of append/dedupe.
- `--headed`: show Chrome UI.
- `--manual`: pause for manual browser checks; use with `--headed`.
- `--instance "https://nitter.net"`: use a different Nitter instance.
- `--between-days-seconds`: wait between date searches.
- `--navigation-retries`: retry count for navigation failures.
- `--retry-delay-seconds`: wait before retrying after HTTP 429 or another navigation error.

## Rate Limits

Nitter often returns HTTP 429. This is not a code bug. The scraper retries and prints countdown progress.

Safer slow command:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --between-days-seconds 30 \
  --navigation-retries 5 \
  --retry-delay-seconds 120
```

If rate limits continue, wait 10-30 minutes or use a working alternate Nitter instance with `--instance`.

## Validation

Check Python syntax:

```bash
python3 -m py_compile src/renaiss_playwright_scraper.py
```

The project uses only one dependency:

```text
playwright==1.60.0
```

## Agent Rules

- Keep this project Playwright-only unless the user explicitly asks to add another scraping backend.
- Do not reintroduce `ntscraper`, BrightData, Selenium, pandas, or Google discovery code.
- Do not use `--fresh` in examples unless explaining that it overwrites existing data.
- Preserve append-and-dedupe behavior as the default.
- Keep output files in `data/`.
- Keep debug artifacts in `output/`.
- Prefer changing the run script or config for user-friendly defaults.
