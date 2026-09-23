import time
import logging
import schedule
from app.config import settings
from app.crawler.pipeline import run_crawl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("scheduler")


def job():
    logger.info("Bat dau crawl dinh ky")
    result = run_crawl(num_pages=settings.crawl_list_pages)
    logger.info(
        "Ket thuc crawl dinh ky: inserted=%s skipped=%s errors=%s",
        len(result["inserted"]),
        len(result["skipped"]),
        len(result["errors"]),
    )


if __name__ == "__main__":
    schedule.every().day.at("00:00").do(job)
    schedule.every().day.at("12:00").do(job)

    logger.info("Scheduler khoi dong, crawl dinh ky luc 00:00 va 12:00 moi ngay")

    while True:
        schedule.run_pending()
        time.sleep(30)