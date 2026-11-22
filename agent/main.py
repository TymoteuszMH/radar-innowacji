import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

from crawler import Crawler, RawDataFormatter
from agents.project_agent import ProjectAgent, process_file
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
    model_path = Path(os.getenv("PROJECT_AGENT_MODEL_PATH", "models/project_agent.pt"))
    if not model_path.is_absolute():
        model_path = PROJECT_DIR / model_path
    if not model_path.is_file():
        raise FileNotFoundError(f"Brak modelu ProjectAgent: {model_path}. Najpierw uruchom train.bat.")
    project_agent = ProjectAgent.load(model_path)
    sites_file = Path(os.getenv("SITES_FILE", "data/sites.csv"))
    if not sites_file.is_absolute():
        sites_file = PROJECT_DIR / sites_file
    Crawler(sites_file).run()
    formatter = RawDataFormatter()
    formatter.run()
    output_file = Path(os.getenv("PROJECTS_OUTPUT_FILE", "results/projects.json"))
    if not output_file.is_absolute():
        output_file = PROJECT_DIR / output_file
    data_file = Path(os.getenv("PROJECT_DATA_OUTPUT_FILE", "results/data.json"))
    if not data_file.is_absolute():
        data_file = PROJECT_DIR / data_file
    process_file(formatter.output_file, output_file, data_file, model_path,
                 threshold=float(os.getenv("PROJECT_AGENT_THRESHOLD", "0.5")), agent=project_agent)
    if os.getenv("DELETE_SCRAPPED_AFTER_RUN", "1").strip().lower() in {"1", "true", "yes", "on"}:
        scrapped_dir = Path(os.getenv("SCRAPPED_DIR", "data/scrapped"))
        if not scrapped_dir.is_absolute():
            scrapped_dir = PROJECT_DIR / scrapped_dir
        if _delete_scrapped_data(scrapped_dir, PROJECT_DIR):
            LOGGER.info("Usunięto dane crawlera: %s", scrapped_dir)


if __name__ == "__main__":
    main()