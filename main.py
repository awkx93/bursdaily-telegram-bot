import time
import logging
from config import CHECK_INTERVAL
from db import init_db, is_seen, mark_seen
from scrapers import scrape_edge_malaysia, scrape_klse_screener
from bot import send_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def process(articles: list[dict]):
    for article in articles:
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
        time.sleep(2)  # brief gap between posts


def main():
    init_db()
    logging.info("News bot started — checking every %d seconds", CHECK_INTERVAL)

    while True:
        logging.info("--- Checking sources ---")
        process(scrape_edge_malaysia())
        process(scrape_klse_screener())
        logging.info("Done. Sleeping %d seconds...", CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
