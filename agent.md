# Agent Guide: Renaiss Nitter Scraper

This repository scrapes public Nitter search results with Playwright. It is intentionally small and should stay focused on the current flow.

## Current Architecture

Only this flow is active:

```text
CLI/config -> daily Nitter search URLs -> Playwright Chrome -> DOM extraction -> dedupe -> CSV/JSONL
```

Do not treat older BrightData or `ntscraper` examples as active project code.

## Entry Points

Default shortcut:

```bash
./scripts/run_renaiss.sh
```

Main module:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026
```

Config run:

```bash
python -m src.renaiss_playwright_scraper --config scraper_config.json
```

## How The Scraper Works

1. `parse_args` defines the CLI.
2. `load_config` reads optional JSON config.
3. `resolve_args` combines CLI and config values. CLI values win.
4. `build_search_url` builds a base Nitter search URL from `--instance` and `--query`.
5. `parse_input_date` accepts `DD-MM-YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`, or `YYYY/MM/DD`.
6. `inclusive_dates` creates all dates between `--date-from` and `--date-to`.
7. `build_date_search_url` adds daily `since` and `until` filters.
8. `scrape` launches persistent Chrome through Playwright.
9. `goto_page` handles navigation retries and HTTP 429 waits.
10. `wait_for_page` waits for tweet cards, error panel, or body.
11. `extract_tweets` reads tweet data from Nitter DOM nodes.
12. `normalize_tweet` converts raw items into CSV rows.
13. `load_existing_outputs` loads old CSV/JSONL rows unless `--fresh` is set.
14. `item_key` dedupes by tweet ID, URL, Nitter URL, or description fallback.
15. `save_checkpoint` writes CSV/JSONL after each page with new rows.
16. `find_next_page_url` follows Nitter "Load more" links up to `--max-pages`.

## Browser Behavior

Default is hidden/headless mode.

Use visible Chrome only when needed:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --headed
```

Manual verification mode should be headed:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --headed \
  --manual
```

## Data Files

For `#renaiss`:

```text
data/renaiss_posts.csv
data/renaiss_posts.jsonl
```

For `#renaissTH`:

```text
data/renaissth_posts.csv
data/renaissth_posts.jsonl
```

CSV fields are defined in `FIELDNAMES`:

```text
id, url, nitter_url, description, author_name, author_username,
created_at, replies, reposts, quotes, likes, views, hashtags,
raw_stats, pictures
```

## Important Defaults

- `instance`: `https://nitter.net`
- `query`: `#renaiss`
- `number`: `1000`
- `output_dir`: `data`
- `profile_dir`: `output/playwright-profile`
- `debug_dir`: `output/playwright`
- `headless`: `true`
- `max_pages`: `8`
- `wait_seconds`: `3`
- `between_days_seconds`: `5`
- `navigation_retries`: `3`
- `retry_delay_seconds`: `60`

## Handling HTTP 429

HTTP 429 means the Nitter instance is rate-limiting requests. It is expected behavior for public instances.

Use slower retries:

```bash
python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 28-05-2026 \
  --date-to 20-05-2026 \
  --between-days-seconds 30 \
  --navigation-retries 5 \
  --retry-delay-seconds 120
```

If that still fails, wait or change `--instance`.

## Safe Change Guidelines

- Keep the existing append-and-dedupe default.
- Avoid destructive changes to `data/*.csv` and `data/*.jsonl`.
- Use `--fresh` only when the user clearly wants to overwrite output.
- Keep external dependencies minimal; currently only Playwright is required.
- If changing extraction selectors, test against a live Nitter page or saved debug HTML.
- If changing date behavior, preserve inclusive date ranges.
- If adding run shortcuts, prefer scripts in `scripts/`.

## Quick Checks

Syntax check:

```bash
python3 -m py_compile src/renaiss_playwright_scraper.py
```

Confirm the default run script:

```bash
sed -n '1,80p' scripts/run_renaiss.sh
```
