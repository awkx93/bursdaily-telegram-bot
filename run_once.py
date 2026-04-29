import logging
from db import init_db, is_seen, mark_seen
from scrapers import scrape_edge_malaysia, scrape_klse_screener
from bot import send_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

MAX_PER_RUN = 10  # max new articles to post per check


def collect_new(articles: list[dict], budget: int) -> tuple[list[dict], int]:
    new = []
    for article in articles:
        if len(new) >= budget:
            break
        url = article["url"]
        if is_seen(url):
            continue
        mark_seen(url)
        new.append(article)
    return new, budget - len(new)


init_db()
logging.info("Checking sources...")

budget = MAX_PER_RUN
edge_new, budget = collect_new(scrape_edge_malaysia(), budget)
klse_new, _ = collect_new(scrape_klse_screener(), budget)

all_new = edge_new + klse_new
if all_new:
    logging.info(f"Sending {len(all_new)} new article(s) as one message")
    send_batch(all_new)
else:
    logging.info("No new articles")

logging.info("Done.")
