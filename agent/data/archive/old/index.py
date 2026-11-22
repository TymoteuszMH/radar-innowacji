import argparse
import logging
import os

from analyzer import Analyzer
from crawler import Crawler


def main() -> None:
    parser = argparse.ArgumentParser(description="Uruchom crawler, a następnie analizę artykułów.")
    parser.add_argument(
        "domains_file",
        nargs="?",
        default=os.getenv("DOMAINS_FILE", "sites.csv"),
        help="Plik z domenami (domyślnie: DOMAINS_FILE z .env lub sites.csv)",
    )
    parser.add_argument("--output-dir", default="articles", help="Folder na zapisane artykuły")
    parser.add_argument(
        "--analysis-output-dir",
        default="analysis",
        help="Folder na wyniki analizy",
    )
    parser.add_argument(
        "--max-pages-per-site",
        type=int,
        default=int(os.getenv("CRAWLER_MAX_PAGES_PER_SITE", os.getenv("MAX_PAGES_PER_SITE", "200"))),
        help="Maksymalna liczba stron do odwiedzenia na domenę (0 oznacza bez limitu)",
    )
    parser.add_argument(
        "--max-sites",
        type=int,
        default=int(os.getenv("MAX_SITES_TO_SEARCH", "0")),
        help="Maksymalna liczba domen (0 oznacza bez limitu)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=int(os.getenv("MAX_ARTICLES_TO_PROCESS", "0")),
        help="Maksymalna liczba artykułów do analizy (0 oznacza bez limitu)",
    )
    parser.add_argument(
        "--max-articles-per-site",
        type=int,
        default=int(os.getenv("CRAWLER_MAX_ARTICLES_PER_SITE", "50")),
        help="Maksymalna liczba artykułów pobranych z jednej domeny (0 oznacza bez limitu)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    crawler = Crawler(
        args.domains_file,
        output_dir=args.output_dir,
        max_pages_per_site=args.max_pages_per_site,
        max_sites=args.max_sites,
        max_articles_per_site=args.max_articles_per_site,
    )
    crawler.run()
    Analyzer(
        input_dir=args.output_dir,
        output_dir=args.analysis_output_dir,
        max_articles=args.max_articles,
    ).run()


if __name__ == "__main__":
    main()
