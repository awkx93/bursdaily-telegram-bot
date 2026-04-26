import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@sipekhuatchannel")
CHECK_INTERVAL = 600  # seconds between checks (10 min)

SOURCES = [
    {
        "name": "The Edge Malaysia",
        "url": "https://theedgemalaysia.com/categories/corporate",
        "scraper": "edge",
    },
    {
        "name": "KLSE Screener",
        "url": "https://klsescreener.com/v2/news",
        "scraper": "klse",
    },
]
