import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from summarizer import summarize

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def get(url: str) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp


def scrape_edge_malaysia() -> list[dict]:
    """Parse articles from __NEXT_DATA__ JSON embedded in the page."""
    articles = []
    try:
        soup = BeautifulSoup(get("https://theedgemalaysia.com/categories/corporate").text, "lxml")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            logging.error("Edge Malaysia: __NEXT_DATA__ not found")
            return []

        data = json.loads(script.string)
        raw = data["props"]["pageProps"].get("corporateData", [])

        for item in raw:
            nid = item.get("nid")
            title = item.get("title", "").strip()
            alias = item.get("alias", f"node/{nid}")
            summary_text = item.get("summary", "").strip()

            if not title or not nid:
                continue

            url = f"https://theedgemalaysia.com/{alias}"
            summary = summarize(summary_text) if summary_text else None

            articles.append({
                "title": title,
                "url": url,
                "summary": summary,
                "source": "The Edge Malaysia",
            })

        logging.info(f"Edge Malaysia: {len(articles)} articles")
    except Exception as e:
        logging.error(f"Edge Malaysia scrape failed: {e}")

    return articles[:20]


def scrape_klse_screener() -> list[dict]:
    """Scrape KLSE Screener news, deduplicating by article ID."""
    articles: dict[str, dict] = {}
    try:
        soup = BeautifulSoup(get("https://klsescreener.com/v2/news").text, "lxml")

        for link in soup.find_all("a", href=re.compile(r"/v2/news/view/\d+/")):
            href: str = link["href"]
            match = re.search(r"/v2/news/view/(\d+)/", href)
            if not match:
                continue

            article_id = match.group(1)
            title = link.get_text(strip=True)
            is_slug = bool(re.search(r"/view/\d+/[a-z0-9-]+$", href))

            if is_slug and title and article_id not in articles:
                # First pass: slug-style link has the clean title
                articles[article_id] = {
                    "title": title,
                    "url": f"https://klsescreener.com{href}",
                    "summary": None,
                    "source": "KLSE Screener",
                }
            elif not is_slug and article_id in articles:
                # Second pass: underscore-style link's parent has excerpt after title
                parent = link.find_parent(["div", "li", "article", "td"])
                if parent:
                    stored_title = articles[article_id]["title"]
                    full_text = parent.get_text(separator=" ", strip=True)
                    excerpt = full_text[len(stored_title):].strip()
                    if len(excerpt) > 20:
                        articles[article_id]["summary"] = summarize(excerpt)

        result = list(articles.values())
        logging.info(f"KLSE Screener: {len(result)} articles")
    except Exception as e:
        logging.error(f"KLSE Screener scrape failed: {e}")
        return []

    return result[:20]
