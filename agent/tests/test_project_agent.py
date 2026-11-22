import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.project_agent import ProjectAgent, article_text, main
from data.build_project_dataset import build_dataset
from models.train_project_agent import split_by_domain


class ProjectDatasetTests(unittest.TestCase):
    def test_bootstrap_labels_only_unambiguous_articles(self):
        articles = [
            {"url": "1", "summary": "Szkoła realizuje projekt dotyczący dostępności cyfrowej dla uczniów."},
            {"url": "2", "summary": "Uczniowie wybrali się na wycieczkę do muzeum w sąsiednim mieście."},
            {"url": "3", "summary": "Spotkanie dotyczyło projektu tworzonego przez szkołę i jej partnerów."},
            {"url": "4", "summary": "Krótki tekst."},
        ]
        dataset = build_dataset({"articles": articles})
        self.assertEqual(dataset["counts"], {"project": 1, "non_project": 1, "unlabeled": 2})
        self.assertEqual([record["label"] for record in dataset["records"]], [1, 0])
        self.assertEqual(dataset["records"][0]["label_source"], "bootstrap_rules")

    def test_record_text_ignores_existing_label_and_project_fields(self):
        self.assertEqual(article_text({"source_title": "Tytuł", "summary": "Opis", "relevant": True,
                                       "project_title": "Sztuczna etykieta"}), "Tytuł\nOpis")

    def test_missing_articles_is_error(self):
        with self.assertRaises(ValueError):
            build_dataset({})

    def test_duplicates_and_placeholders_are_unlabeled(self):
        text = "Szkoła realizuje projekt dotyczący dostępności cyfrowej dla uczniów."
        dataset = build_dataset({"articles": [
            {"url": "1", "summary": text}, {"url": "2", "summary": text},
            {"url": "3", "source_title": "Wyniki projektu", "summary": "Strona jest w trakcie tworzenia"},
        ]})
        self.assertEqual(dataset["counts"], {"project": 1, "non_project": 0, "unlabeled": 2})


class ProjectAgentTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"domain": "a", "text": "projekt szkolny aplikacja", "label": 1},
            {"domain": "a", "text": "wycieczka szkolna muzeum", "label": 0},
            {"domain": "b", "text": "projekt miejski aplikacja", "label": 1},
            {"domain": "b", "text": "wycieczka miejska muzeum", "label": 0},
        ]

    def test_domain_split_and_model_round_trip(self):
        train, validation = split_by_domain(self.records)
        self.assertTrue({item["domain"] for item in train}.isdisjoint(
            {item["domain"] for item in validation}))
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        before = agent.predict_proba("projekt szkolny aplikacja")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            agent.save(path)
            loaded = ProjectAgent.load(path)
            self.assertAlmostEqual(before, loaded.predict_proba("projekt szkolny aplikacja"))
        self.assertIsNone(loaded.predict_proba("nieznanewyrazy"))

    def test_classification_preserves_source_and_marks_unknown(self):
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        source = {"articles": [{"url": "1", "summary": "projekt szkolny aplikacja"},
                               {"url": "2", "summary": "nieznanewyrazy"}]}
        output = agent.classify_results(source, threshold=0)
        self.assertEqual(output["projects"][0]["url"], "1")
        self.assertEqual(output["projects"][0]["summary"], "projekt szkolny aplikacja")
        self.assertEqual(output["records"][0]["analyzed_text"], "projekt szkolny aplikacja")
        self.assertIsNone(output["records"][1]["project_detection"]["is_project"])
        self.assertNotIn("project_detection", source["articles"][0])

    def test_cli_separates_projects_and_analyzed_data(self):
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps({"articles": [
                {"url": "1", "source_title": "Tytuł", "content": "projekt szkolny aplikacja"},
                {"url": "2", "source_title": "Inny", "content": "nieznanewyrazy"},
            ]}), encoding="utf-8")
            output = root / "projects.json"
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(output),
                                    "--model", str(root / "model.pt"), "--threshold", "0"]), \
                 patch.object(ProjectAgent, "load", return_value=agent):
                main()
            projects = json.loads(output.read_text(encoding="utf-8"))
            data = json.loads((root / "data.json").read_text(encoding="utf-8"))
            self.assertEqual(list(projects), ["projects"])
            self.assertEqual([item["url"] for item in projects["projects"]], ["1"])
            self.assertNotIn("content", projects["projects"][0])
            self.assertEqual(projects["projects"][0]["project_title"], "Tytuł")
            self.assertEqual(projects["projects"][0]["summary"], "projekt szkolny aplikacja")
            self.assertEqual(len(data["records"]), 2)
            self.assertEqual(data["records"][0]["analyzed_text"], "Tytuł\nprojekt szkolny aplikacja")
            self.assertEqual(data["records"][0]["content"], "projekt szkolny aplikacja")

    def test_cli_rejects_output_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "data.json"
            source.write_text("original", encoding="utf-8")
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(Path(directory) / "projects.json")]):
                with self.assertRaises(ValueError):
                    main()
            self.assertEqual(source.read_text(encoding="utf-8"), "original")

    def test_extracts_named_project_from_article(self):
        from agents.project_agent import project_from_article
        project = project_from_article({"source_title": "Szkoła", "url": "https://example.pl",
            "content": "Projekt „Cyfrowa Szkoła” wspiera naukę.\nUczniowie testują aplikację."})
        self.assertEqual(project["project_title"], "Cyfrowa Szkoła")
        self.assertIn("Projekt „Cyfrowa Szkoła”", project["summary"])
        self.assertEqual(project["url"], "https://example.pl")

    def test_extracts_name_with_adjectives(self):
        from agents.project_agent import project_from_article
        project = project_from_article({"source_title": "Zespół Szkół nr 2", "content":
            "Szkoła realizuje mobilny projekt edukacyjny „EKONOMICZNA AKADEMIA MALUCHA”."})
        self.assertEqual(project["project_title"], "EKONOMICZNA AKADEMIA MALUCHA")

    def test_extracts_unquoted_project_name(self):
        from agents.project_agent import project_from_article
        project = project_from_article({"source_title": "Zajęcia pozalekcyjne", "content":
            "Szkolne Koło ECDL (w ramach projektu Klasa z ECDL)"})
        self.assertEqual(project["project_title"], "Klasa z ECDL")

    def test_does_not_save_general_mentions_as_projects(self):
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        source = {"articles": [
            {"url": "1", "source_title": "Warsztaty", "content": "Poznawali projekty edukacyjne."},
            {"url": "2", "source_title": "Projekt", "content": "Już wkrótce"},
        ]}
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results(source)
        self.assertEqual(output["projects"], [])
        self.assertEqual(len(output["records"]), 2)


if __name__ == "__main__":
    unittest.main()