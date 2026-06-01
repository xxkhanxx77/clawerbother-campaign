from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from types import SimpleNamespace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


DEFAULT_SEARCH_URL = "https://nitter.net/search?f=tweets&q=%23renaiss&since=&until=&min_faves="
DEFAULT_INSTANCE = "https://nitter.net"
DEFAULT_QUERY = "#renaiss"
DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FIELDNAMES = [
    "id",
    "url",
    "nitter_url",
    "description",
    "author_name",
    "author_username",
    "created_at",
    "replies",
    "reposts",
    "quotes",
    "likes",
    "views",
    "hashtags",
    "raw_stats",
    "pictures",
    "score",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Nitter/X search results by query and date range with real Chrome."
    )
    parser.add_argument(
        "--config",
        help="Optional JSON config file. CLI values override config values.",
    )
    parser.add_argument(
        "--query",
        help='Search wording, such as "#renaiss", "#renaissTH", or "renaiss bnbchain".',
    )
    parser.add_argument(
        "--instance",
        help="Nitter instance base URL. Default: https://nitter.net.",
    )
    parser.add_argument("--url", help="Advanced: full Nitter search URL or cursor URL.")
    parser.add_argument("--number", type=int, help="Maximum new posts to save.")
    parser.add_argument("--output-dir", help="Directory for CSV/JSONL output.")
    parser.add_argument(
        "--output-base",
        help="Output filename without extension. Default is derived from --query.",
    )
    parser.add_argument(
        "--date-from",
        help="Newest search date. Accepts DD-MM-YYYY or YYYY-MM-DD. Example: 28-05-2026.",
    )
    parser.add_argument(
        "--date-to",
        help="Oldest search date. Accepts DD-MM-YYYY or YYYY-MM-DD. Example: 20-05-2026.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Compatibility flag. Appending/deduping is the default unless --fresh is used.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Overwrite the output files instead of loading existing rows.",
    )
    parser.add_argument(
        "--oldest-date",
        help="Oldest created_at date to include. Usually not needed when using --date-from/--date-to.",
    )
    parser.add_argument(
        "--skip-id",
        action="append",
        default=[],
        help="Tweet ID to skip. Can be used more than once.",
    )
    parser.add_argument(
        "--profile-dir",
        help="Persistent browser profile for cookies and Nitter verification state.",
    )
    parser.add_argument(
        "--debug-dir",
        help="Where to save debug screenshots/HTML.",
    )
    parser.add_argument(
        "--chrome-path",
        help="Path to Google Chrome executable.",
    )
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser. This is the default.")
    parser.add_argument("--headed", action="store_true", help="Show the browser window.")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Pause when no tweets are found so you can solve browser checks manually.",
    )
    parser.add_argument(
        "--manual-wait-seconds",
        type=float,
        help="Fallback wait time for --manual when stdin is not interactive.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        help="Seconds to wait after each page load.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum Nitter pages to follow via show-more links per URL/date.",
    )
    parser.add_argument(
        "--between-days-seconds",
        type=float,
        help="Pause between date-bounded searches to reduce Nitter rate limiting.",
    )
    parser.add_argument(
        "--navigation-retries",
        type=int,
        help="Retries for Nitter navigation failures such as HTTP 429.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        help="Pause before retrying a failed Nitter navigation.",
    )
    return parser.parse_args()


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def config_value(args: argparse.Namespace, config: dict[str, Any], name: str, default: Any = None) -> Any:
    value = getattr(args, name)
    if value is not None and value is not False:
        return value
    return config.get(name, default)


def normalize_instance(instance: str) -> str:
    return instance.strip().rstrip("/")


def build_search_url(instance: str, query: str) -> str:
    params = {
        "f": "tweets",
        "q": query,
        "since": "",
        "until": "",
        "min_faves": "",
    }
    return f"{normalize_instance(instance)}/search?{urlencode(params)}"


def extract_query_from_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True).get("q", [""])[0]
    return query or DEFAULT_QUERY


def output_base_from_query(query: str) -> str:
    cleaned = query.strip().lstrip("#@").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return f"{cleaned or 'nitter'}_posts"


def resolve_args(args: argparse.Namespace) -> SimpleNamespace:
    config = load_config(args.config)
    query_was_explicit = args.query is not None or "query" in config
    query = config_value(args, config, "query", DEFAULT_QUERY)
    instance = normalize_instance(config_value(args, config, "instance", DEFAULT_INSTANCE))
    url = config_value(args, config, "url")
    if not url:
        url = build_search_url(instance, query)
    elif not query_was_explicit:
        query = extract_query_from_url(url)

    output_base = config_value(args, config, "output_base") or output_base_from_query(query)

    headless = bool(config.get("headless", True))
    if args.headless:
        headless = True
    if args.headed:
        headless = False

    return SimpleNamespace(
        config=args.config,
        query=query,
        instance=instance,
        url=url,
        number=int(config_value(args, config, "number", 1000)),
        output_dir=config_value(args, config, "output_dir", "data"),
        output_base=output_base,
        date_from=config_value(args, config, "date_from"),
        date_to=config_value(args, config, "date_to"),
        fresh=bool(args.fresh or config.get("fresh", False)),
        append=True,
        oldest_date=config_value(args, config, "oldest_date"),
        skip_id=args.skip_id or config.get("skip_id", []),
        profile_dir=config_value(args, config, "profile_dir", "output/playwright-profile"),
        debug_dir=config_value(args, config, "debug_dir", "output/playwright"),
        chrome_path=config_value(args, config, "chrome_path", DEFAULT_CHROME_PATH),
        headless=headless,
        manual=bool(args.manual or config.get("manual", False)),
        manual_wait_seconds=float(config_value(args, config, "manual_wait_seconds", 60.0)),
        wait_seconds=float(config_value(args, config, "wait_seconds", 3.0)),
        max_pages=int(config_value(args, config, "max_pages", 8)),
        between_days_seconds=float(config_value(args, config, "between_days_seconds", 5.0)),
        navigation_retries=int(config_value(args, config, "navigation_retries", 3)),
        retry_delay_seconds=float(config_value(args, config, "retry_delay_seconds", 60.0)),
    )


def parse_count(value: Any) -> int:
    text = str(value or "").strip().lower().replace(",", "")
    if not text:
        return 0
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def normalize_username(username: str) -> str:
    return username.strip().lstrip("@")


def normalize_tweet(raw: dict[str, Any]) -> dict[str, Any]:
    raw_stats = raw.get("raw_stats") if isinstance(raw.get("raw_stats"), list) else []
    if len(raw_stats) >= 5:
        replies, reposts, quotes, likes, views = (parse_count(raw_stats[index]) for index in range(5))
    elif len(raw_stats) >= 4:
        replies, reposts, likes, views = (parse_count(raw_stats[index]) for index in range(4))
        quotes = 0
    else:
        padded_stats = list(raw_stats) + [""] * (4 - len(raw_stats))
        replies, reposts, likes, views = (parse_count(padded_stats[index]) for index in range(4))
        quotes = 0

    hashtags = raw.get("hashtags") if isinstance(raw.get("hashtags"), list) else []
    pictures = raw.get("pictures") if isinstance(raw.get("pictures"), list) else []

    return {
        "id": raw.get("id", ""),
        "url": raw.get("url", ""),
        "nitter_url": raw.get("nitter_url", ""),
        "description": raw.get("description", ""),
        "author_name": raw.get("author_name", ""),
        "author_username": normalize_username(str(raw.get("author_username", ""))),
        "created_at": raw.get("created_at", ""),
        "replies": replies,
        "reposts": reposts,
        "quotes": quotes,
        "likes": likes,
        "views": views,
        "hashtags": ",".join(tag.lstrip("#") for tag in hashtags),
        "raw_stats": json.dumps(raw_stats, ensure_ascii=False),
        "pictures": ",".join(str(item) for item in pictures),
        "score": raw.get("score", ""),
    }


def parse_created_date(value: Any) -> date | None:
    text = str(value or "").split("·", 1)[0].strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_input_date(value: str) -> date:
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date '{value}'. Use DD-MM-YYYY or YYYY-MM-DD.")


def inclusive_dates(start: date, end: date) -> list[date]:
    step = -1 if start >= end else 1
    days: list[date] = []
    current = start
    while True:
        days.append(current)
        if current == end:
            return days
        current = current + timedelta(days=step)


def parse_created_datetime(value: Any) -> datetime:
    text = str(value or "").replace(" UTC", "").strip()
    for fmt in ("%b %d, %Y · %I:%M %p", "%B %d, %Y · %I:%M %p", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def output_paths(output_dir: Path, output_base: str) -> tuple[Path, Path]:
    return output_dir / f"{output_base}.csv", output_dir / f"{output_base}.jsonl"


def item_key(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("url") or item.get("nitter_url") or item.get("description") or "")


def build_date_search_url(base_url: str, day: date) -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.pop("cursor", None)
    query["f"] = ["tweets"]
    query["q"] = query.get("q") or ["#renaiss"]
    query["since"] = [day.isoformat()]
    query["until"] = [(day + timedelta(days=1)).isoformat()]
    query.setdefault("min_faves", [""])
    return urlunparse(parsed._replace(path="/search", query=urlencode(query, doseq=True)))


def build_range_search_url(base_url: str, since: date, until: date) -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query.pop("cursor", None)
    query["f"] = ["tweets"]
    query["q"] = query.get("q") or ["#renaiss"]
    query["since"] = [since.isoformat()]
    query["until"] = [(until + timedelta(days=1)).isoformat()]
    query.setdefault("min_faves", [""])
    return urlunparse(parsed._replace(path="/search", query=urlencode(query, doseq=True)))


def build_search_targets(args: argparse.Namespace) -> list[tuple[str, str, date | None, date | None]]:
    if bool(args.date_from) != bool(args.date_to):
        raise ValueError("--date-from and --date-to must be used together.")
    if not args.date_from:
        return [("single", args.url, None, None)]

    date_from = parse_input_date(args.date_from)
    date_to = parse_input_date(args.date_to)
    since = min(date_from, date_to)
    until = max(date_from, date_to)
    url = build_range_search_url(args.url, since, until)
    return [(f"{since.isoformat()}..{until.isoformat()}", url, since, until)]


def load_existing_outputs(output_dir: Path, output_base: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    csv_path, jsonl_path = output_paths(output_dir, output_base)
    rows: list[dict[str, Any]] = []
    raw_items: list[dict[str, Any]] = []
    seen: set[str] = set()

    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                row_dict = dict(row)
                row_dict.setdefault("score", "")
                rows.append(row_dict)
                key = str(row.get("id") or row.get("url") or "")
                if key:
                    seen.add(key)

    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                raw_items.append(item)
                key = item_key(item)
                if key:
                    seen.add(key)

    return rows, raw_items, seen


def extract_tweets(page: Page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const text = (root, selector) => {
            const node = root.querySelector(selector);
            return node ? node.innerText.trim().replace(/\\s+/g, " ") : "";
          };
          const absoluteUrl = (href) => {
            try { return new URL(href, window.location.href).toString(); }
            catch { return ""; }
          };
          const xUrlFromNitter = (href) => {
            const absolute = absoluteUrl(href);
            if (!absolute) return "";
            try {
              const parsed = new URL(absolute);
              return `https://x.com${parsed.pathname}`;
            } catch {
              return "";
            }
          };
          const idFromUrl = (url) => {
            const match = String(url).match(/\\/status\\/(\\d+)/);
            return match ? match[1] : "";
          };
          const unique = (items) => Array.from(new Set(items.filter(Boolean)));

          return Array.from(document.querySelectorAll("div.timeline-item"))
            .filter((item) => !item.classList.contains("thread"))
            .map((item) => {
              const dateLink = item.querySelector("span.tweet-date a");
              const nitterUrl = dateLink ? absoluteUrl(dateLink.getAttribute("href")) : "";
              const url = xUrlFromNitter(nitterUrl);
              const description = text(item, ".tweet-content");
              const rawStats = Array.from(item.querySelectorAll(".tweet-stat"))
                .map((stat) => stat.innerText.trim().replace(/\\s+/g, " "));
              const pictures = Array.from(item.querySelectorAll(".attachments img"))
                .map((img) => absoluteUrl(img.getAttribute("src")));
              const hashtags = unique(description.match(/#[\\p{L}\\p{N}_]+/gu) || []);

              return {
                id: idFromUrl(url),
                url,
                nitter_url: nitterUrl,
                description,
                author_name: text(item, ".fullname"),
                author_username: text(item, ".username"),
                created_at: dateLink ? (dateLink.getAttribute("title") || dateLink.innerText.trim()) : "",
                raw_stats: rawStats,
                hashtags,
                pictures,
              };
            })
            .filter((item) => item.id && item.url.includes("/status/"));
        }
        """
    )


def find_next_page_url(page: Page) -> str:
    try:
        href = page.evaluate(
            """
            () => {
              const links = Array.from(document.querySelectorAll("div.show-more a"));
              const link = links.at(-1);
              return link ? link.getAttribute("href") : "";
            }
            """
        )
    except PlaywrightError as exc:
        print(f"Next page warning: {exc}", file=sys.stderr, flush=True)
        return ""
    if not href:
        return ""
    absolute = urljoin(page.url, href)
    if "cursor=" not in absolute:
        parsed = urlparse(absolute)
        if parsed.path != "/search":
            absolute = urlunparse(parsed._replace(path="/search"))
    return absolute


def save_debug(page: Page, debug_dir: Path) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    try:
        (debug_dir / "nitter_debug.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(debug_dir / "nitter_debug.png"), full_page=True)
    except PlaywrightError as exc:
        (debug_dir / "nitter_debug_error.txt").write_text(str(exc), encoding="utf-8")


def save_outputs(output_dir: Path, output_base: str, rows: list[dict[str, Any]], raw_items: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path, jsonl_path = output_paths(output_dir, output_base)
    rows = sorted(rows, key=lambda row: parse_created_datetime(row.get("created_at")), reverse=True)
    raw_items = sorted(raw_items, key=lambda item: parse_created_datetime(item.get("created_at")), reverse=True)

    for row in rows:
        row.setdefault("score", "")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    with jsonl_path.open("w", encoding="utf-8") as file:
        for item in raw_items:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"CSV:   {csv_path}")
    print(f"JSONL: {jsonl_path}")


def save_checkpoint(output_dir: Path, output_base: str, rows: list[dict[str, Any]], raw_items: list[dict[str, Any]]) -> None:
    save_outputs(output_dir, output_base, rows, raw_items)
    print("Checkpoint saved.", flush=True)


def sleep_with_progress(seconds: float, reason: str) -> None:
    remaining = max(0, int(seconds))
    if remaining == 0:
        return
    print(f"{reason}; waiting {remaining}s", flush=True)
    while remaining > 0:
        step = min(15, remaining)
        time.sleep(step)
        remaining -= step
        if remaining:
            print(f"... {remaining}s remaining", flush=True)


def wait_for_page(page: Page, seconds: float) -> bool:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=30_000)
        try:
            page.wait_for_selector(
                ".timeline-item, .error-panel, .timeline-none, .search-result",
                timeout=30_000,
            )
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(int(seconds * 1000))
        return True
    except PlaywrightError as exc:
        print(f"Page wait warning: {exc}", file=sys.stderr, flush=True)
        return False


def click_load_newest(page: Page) -> bool:
    try:
        candidates = page.locator("text=Load newest")
        if candidates.count() == 0:
            return False
        candidates.first.click(timeout=10_000)
        page.wait_for_load_state("domcontentloaded", timeout=30_000)
        page.wait_for_timeout(1_000)
        return True
    except PlaywrightError as exc:
        print(f"Load newest warning: {exc}", file=sys.stderr, flush=True)
        return False


def goto_page(page: Page, url: str, retries: int, retry_delay_seconds: float) -> bool:
    for attempt in range(1, retries + 2):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(800)
            body_html: str = page.evaluate("() => document.body ? document.body.innerHTML : ''")
            if not body_html.strip():
                raise PlaywrightError("blank page (bot detection or server error)")
            return True
        except PlaywrightError as exc:
            print(f"Navigation warning ({attempt}/{retries + 1}): {exc}", file=sys.stderr, flush=True)
            if attempt > retries:
                time.sleep(2)
                return False
            sleep_with_progress(retry_delay_seconds, "Retrying navigation after rate limit/error")
    return False


def print_progress(label: str, page_number: int, url: str, found: int, total: int) -> None:
    parsed = urlparse(url)
    prefix = f"{label} " if label != "single" else ""
    status = f"found {found}" if found else "blank page"
    print(f"{prefix}page {page_number}: {parsed.netloc}{parsed.path} -> {status}, {total} total new saved", flush=True)


def format_day_label(day: date | None) -> str:
    return day.isoformat() if day else "unknown"


def scrape(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, list[tuple[str, int, int]]]:
    chrome_path = Path(args.chrome_path)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome executable not found: {chrome_path}")

    output_dir = Path(args.output_dir)
    existing_rows, existing_raw_items, seen = (
        load_existing_outputs(output_dir, args.output_base) if not args.fresh else ([], [], set())
    )
    seen.update(str(skip_id) for skip_id in args.skip_id)

    raw_items: list[dict[str, Any]] = list(existing_raw_items)
    rows: list[dict[str, Any]] = list(existing_rows)
    new_rows_count = 0
    targets = build_search_targets(args)
    target_dates = [target_date for _, _, target_date, _ in targets if target_date]
    default_oldest_date = min(target_dates) if target_dates else None
    oldest_date = parse_input_date(args.oldest_date) if args.oldest_date else default_oldest_date
    reached_older_than_oldest_date = False
    per_day_summary: dict[str, dict[str, int]] = {}

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=args.profile_dir,
            executable_path=str(chrome_path),
            headless=args.headless,
            viewport={"width": 1440, "height": 1100},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for target_index, (label, url, target_start, target_end) in enumerate(targets, 1):
            if new_rows_count >= args.number or reached_older_than_oldest_date:
                break
            if label != "single":
                print(f"\nSearching {label} ({target_index}/{len(targets)})", flush=True)
            if not goto_page(page, url, args.navigation_retries, args.retry_delay_seconds):
                save_debug(page, Path(args.debug_dir))
                continue

            for page_number in range(1, args.max_pages + 1):
                if not wait_for_page(page, args.wait_seconds):
                    save_debug(page, Path(args.debug_dir))
                    break
                try:
                    page_items = extract_tweets(page)
                except PlaywrightError as exc:
                    print(f"Extract warning: {exc}", file=sys.stderr, flush=True)
                    save_debug(page, Path(args.debug_dir))
                    break

                if not page_items:
                    loaded_newest = click_load_newest(page)
                    if loaded_newest:
                        if not wait_for_page(page, 1):
                            save_debug(page, Path(args.debug_dir))
                            break
                        try:
                            page_items = extract_tweets(page)
                        except PlaywrightError as exc:
                            print(f"Extract warning: {exc}", file=sys.stderr, flush=True)
                            save_debug(page, Path(args.debug_dir))
                            break

                if not page_items and args.manual and not args.headless:
                    print(
                        "No tweets found yet. If Chrome shows a verification page, solve it now. "
                        "Press Enter here when the tweets are visible."
                    )
                    if sys.stdin.isatty():
                        input()
                    else:
                        print(f"stdin is not interactive; waiting {args.manual_wait_seconds:g} seconds.")
                        time.sleep(args.manual_wait_seconds)
                    if not wait_for_page(page, 1):
                        save_debug(page, Path(args.debug_dir))
                        break
                    try:
                        page_items = extract_tweets(page)
                    except PlaywrightError as exc:
                        print(f"Extract warning: {exc}", file=sys.stderr, flush=True)
                        save_debug(page, Path(args.debug_dir))
                        break

                page_new_rows_before = new_rows_count
                for item in page_items:
                    created_date = parse_created_date(item.get("created_at"))
                    if oldest_date and created_date and created_date < oldest_date:
                        reached_older_than_oldest_date = True
                        continue
                    if target_start and target_end and created_date and not (target_start <= created_date <= target_end):
                        continue

                    if created_date:
                        day_key = created_date.isoformat()
                        per_day_summary.setdefault(day_key, {"matched": 0, "saved": 0})["matched"] += 1

                    key = item_key(item)
                    if not key or key in seen:
                        continue
                    seen.add(str(key))
                    raw_items.append(item)
                    rows.append(normalize_tweet(item))
                    new_rows_count += 1
                    if created_date:
                        per_day_summary[created_date.isoformat()]["saved"] += 1
                    if new_rows_count >= args.number:
                        break

                print_progress(label, page_number, page.url, len(page_items), new_rows_count)
                if new_rows_count > page_new_rows_before:
                    save_checkpoint(output_dir, args.output_base, rows, raw_items)
                if new_rows_count >= args.number or reached_older_than_oldest_date:
                    break

                next_url = find_next_page_url(page)
                if not next_url:
                    break
                sleep_with_progress(args.between_days_seconds, "Waiting before next page")
                if not goto_page(page, next_url, args.navigation_retries, args.retry_delay_seconds):
                    save_debug(page, Path(args.debug_dir))
                    break

            if label != "single" and target_index < len(targets):
                sleep_with_progress(args.between_days_seconds, "Waiting before next date")

        if new_rows_count == 0:
            save_debug(page, Path(args.debug_dir))
        try:
            context.close()
        except PlaywrightError:
            pass

    return rows, raw_items, new_rows_count, per_day_summary


def print_summary(per_day_summary: dict[str, dict[str, int]]) -> None:
    if not per_day_summary:
        return
    print("\nPER-DAY SUMMARY")
    for day_label in sorted(per_day_summary.keys(), reverse=True):
        summary = per_day_summary[day_label]
        print(f"  {day_label}: {summary['matched']} matched, {summary['saved']} saved")
    print()


def print_preview(rows: list[dict[str, Any]], new_rows_count: int) -> None:
    preview_rows = rows[-new_rows_count:] if new_rows_count else rows
    print(f"\nRESULTS: {new_rows_count} NEW POSTS, {len(rows)} TOTAL POSTS\n")
    for index, row in enumerate(preview_rows[:5], 1):
        print(f"POST #{index}")
        print(f"  URL: {row['url']}")
        print(f"  Author: @{row['author_username']}")
        print(f"  Created: {row['created_at']}")
        print(f"  Text: {row['description']}")
        print(f"  Likes: {row['likes']}")
        print(f"  Reposts: {row['reposts']}")
        print(f"  Replies: {row['replies']}")
        print()


def main() -> int:
    args = resolve_args(parse_args())
    try:
        rows, raw_items, new_rows_count, per_day_summary = scrape(args)
        if not rows:
            print(
                "No tweets found. Check output/playwright/nitter_debug.png. "
                "If the browser shows a verification page, rerun with --manual.",
                file=sys.stderr,
            )
            return 1
        print_summary(per_day_summary)
        print_preview(rows, new_rows_count)
        save_outputs(Path(args.output_dir), args.output_base, rows, raw_items)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
