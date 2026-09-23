import argparse
import logging
from app.crawler.pipeline import run_crawl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=None, help="So trang can crawl, bo trong hoac 0 de crawl toan bo")
    parser.add_argument("--full", action="store_true", help="Crawl toan bo du lieu tu truoc den nay")
    args = parser.parse_args()

    pages = 0 if args.full else args.pages
    result = run_crawl(pages)
    print(result)