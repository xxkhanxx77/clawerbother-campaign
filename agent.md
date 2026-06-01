# Agent Guide: Renaiss Nitter Scraper

This repository scrapes public Nitter search results with Playwright. It is intentionally small and should stay focused on the current flow.

## Current Architecture

Only this flow is active:

```text
CLI/config -> daily Nitter search URLs -> Playwright Chrome -> DOM extraction -> dedupe -> CSV/JSONL
```

Do not treat older BrightData or `ntscraper` examples as active project code.

## Entry Points

Default headless shortcut (rolling 7-day window, clean profile):

```bash
./scripts/run_renaiss_headless.sh
```

Main module (replace dates as needed):

```bash
TODAY="$(date +%d-%m-%Y)"
SEVEN_DAYS_AGO="$(date -v-7d +%d-%m-%Y)"
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from "$TODAY" \
  --date-to "$SEVEN_DAYS_AGO" \
  --profile-dir output/playwright-profile-clean
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
7. `build_date_search_url` adds daily `since` and `until` filters, always enforcing `/search` path. The scraper does one navigation per day (it does NOT build one giant range query — per-day navigation is gentler on Nitter rate limits).
8. `scrape` launches persistent Chrome through Playwright with a spoofed user-agent and `navigator.webdriver` removed.
9. `goto_page` handles navigation retries, HTTP 429 waits, and treats a blank/empty page body as a retryable failure.
10. `wait_for_page` waits for `.timeline-item`, `.error-panel`, `.timeline-none`, or `.search-result` (no bare `body`, which used to match before content loaded).
11. `click_load_newest` clicks the "Load newest" button if the first page loads with no tweets.
12. `extract_tweets` reads tweet data from Nitter DOM nodes.
13. `normalize_tweet` converts raw items into CSV rows (includes `score` field).
14. `load_existing_outputs` loads old CSV/JSONL rows unless `--fresh` is set; backfills missing `score`.
15. `item_key` dedupes by tweet ID, URL, Nitter URL, or description fallback.
16. `save_checkpoint` writes CSV/JSONL after each page with new rows.
17. `find_next_page_url` follows Nitter "Load more" links up to `--max-pages`; enforces `/search` path. The scraper waits `--between-days-seconds` before each "Load more", and reloads a later page once (after `--retry-delay-seconds`) if it comes back empty.
18. `print_summary` prints a per-day table of matched vs saved items, keyed by each tweet's own `created_at` date.

## Browser Behavior

Default is hidden/headless mode.

Use visible Chrome only when needed:

```bash
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026 \
  --profile-dir output/playwright-profile-clean \
  --headed
```

Manual verification mode should be headed:

```bash
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from 31-05-2026 \
  --date-to 27-05-2026 \
  --profile-dir output/playwright-profile-clean \
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
raw_stats, pictures, score
```

`score` is populated from raw item data if present; otherwise it is an empty string.

## Important Defaults

- `instance`: `https://nitter.net`
- `query`: `#renaiss`
- `number`: `1000`
- `output_dir`: `data`
- `profile_dir`: `output/playwright-profile` (default scripts override this to `output/playwright-profile-clean`)
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
TODAY="$(date +%d-%m-%Y)"
SEVEN_DAYS_AGO="$(date -v-7d +%d-%m-%Y)"
./.venv/bin/python -m src.renaiss_playwright_scraper \
  --query "#renaiss" \
  --date-from "$TODAY" \
  --date-to "$SEVEN_DAYS_AGO" \
  --profile-dir output/playwright-profile-clean \
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
- Keep per-day navigation (one search URL per day). Do not collapse the date range into a single `since..until` query — per-day navigation is the intended, rate-limit-friendly behavior.
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
