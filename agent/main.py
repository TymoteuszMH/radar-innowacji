import csv
import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

from crawler import Crawler, RawDataFormatter
from agents.project_agent import ProjectAgent, process_file
from config import env_float
from logging_utils import get_logger

LOGGER = get_logger("pipeline", console=False)


def _source_project_urls(project_dir: Path) -> set[str]:
    source_file = project_dir / "data" / "sites_and_projects.csv"
    if not source_file.is_file():
        return set()
    with source_file.open(encoding="utf-8-sig", newline="") as file:
        return {ProjectAgent.normalize_url(row["Bezpośredni link do wpisu"])
                for row in csv.DictReader(file) if row.get("Bezpośredni link do wpisu", "").strip()}


def _output_project_urls(output_file: Path) -> set[str]:
    if not output_file.is_file():
        return set()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    projects = data.get("projects", [])
    return {ProjectAgent.normalize_url(project["url"]) for project in projects
            if isinstance(project, dict) and isinstance(project.get("url"), str) and project["url"].strip()} if isinstance(projects, list) else set()


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
    threshold = (env_float("PROJECT_AGENT_THRESHOLD", 0.5, 0, 1)
                 if os.getenv("PROJECT_AGENT_THRESHOLD") is not None else None)
    model_path = Path(os.getenv("PROJECT_AGENT_MODEL_PATH", "models/bert_innovation_classifier"))
    if not model_path.is_absolute():
        model_path = PROJECT_DIR / model_path
    if not model_path.is_dir():
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
                 threshold=threshold, agent=project_agent,
                 prior_art_enabled=os.getenv("PRIOR_ART_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"})

    source_urls = _source_project_urls(PROJECT_DIR)
    output_urls = _output_project_urls(output_file)
    matched_urls = source_urls & output_urls
    LOGGER.info(
        "Porównanie adresów: wzorzec=%d, dopasowane=%d, spoza wzorca=%d, pokrycie=%.1f%%",
        len(source_urls), len(matched_urls), len(output_urls - source_urls),
        (len(matched_urls) / len(source_urls) * 100) if source_urls else 0.0,
    )
    print(
        f"Porównanie adresów: wzorzec={len(source_urls)}, dopasowane={len(matched_urls)}, "
        f"spoza wzorca={len(output_urls - source_urls)}, "
        f"pokrycie={(len(matched_urls) / len(source_urls) * 100) if source_urls else 0:.1f}%"
    )

    if os.getenv("DELETE_SCRAPPED_AFTER_RUN", "1").strip().lower() in {"1", "true", "yes", "on"}:
        scrapped_dir = Path(os.getenv("SCRAPPED_DIR", "data/scrapped"))
        if not scrapped_dir.is_absolute():
            scrapped_dir = PROJECT_DIR / scrapped_dir
        if _delete_scrapped_data(scrapped_dir, PROJECT_DIR):
            LOGGER.info("Usunięto dane crawlera: %s", scrapped_dir)


if __name__ == "__main__":
    main()