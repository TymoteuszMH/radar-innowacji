import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

from agents.local_agent import LocalAgent
from crawler import Crawler
from logging_utils import get_logger

LOGGER = get_logger("pipeline", console=False)


def _delete_scrapped_data(scrapped_dir: Path, project_dir: Path) -> bool:
    scrapped_path = scrapped_dir.resolve()
    project_path = project_dir.resolve()
    if not scrapped_path.is_dir():
        return False
    if scrapped_path == project_path or project_path not in scrapped_path.parents:
        raise ValueError(f"Odmowa usunięcia katalogu spoza projektu: {scrapped_path}")
    shutil.rmtree(scrapped_path)
    return True


def main() -> None:
    sites_file = Path(os.getenv("SITES_FILE", "data/sites.csv"))
    if not sites_file.is_absolute():
        sites_file = PROJECT_DIR / sites_file
    Crawler(sites_file).run()
    LocalAgent().run()
    if os.getenv("DELETE_SCRAPPED_AFTER_RUN", "1").strip().lower() in {"1", "true", "yes", "on"}:
        scrapped_dir = Path(os.getenv("SCRAPPED_DIR", "data/scrapped"))
        if not scrapped_dir.is_absolute():
            scrapped_dir = PROJECT_DIR / scrapped_dir
        if _delete_scrapped_data(scrapped_dir, PROJECT_DIR):
            LOGGER.info("Usunięto dane crawlera: %s", scrapped_dir)


if __name__ == "__main__":
    main()