import time
import logging
from db import init_db, is_seen, mark_seen
from scrapers import scrape_edge_malaysia, scrape_klse_screener
from bot import send_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

MAX_PER_RUN = 5  # cap posts per check to prevent burst


def process(articles: list[dict], budget: int) -> int:
    sent = 0
    for article in articles:
        if sent >= budget:
            break
        url = article["url"]
        if is_seen(url):
            continue
        mark_seen(url)
        send_article(
            title=article["title"],
            summary=article.get("summary"),
            url=url,
            source=article["source"],
        )
        time.sleep(2)
        sent += 1
    return sent


init_db()
logging.info("Checking sources...")
budget = MAX_PER_RUN
budget -= process(scrape_edge_malaysia(), budget)
process(scrape_klse_screener(), budget)
logging.info("Done.")
