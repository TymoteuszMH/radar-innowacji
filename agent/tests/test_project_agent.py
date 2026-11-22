import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx
from openpyxl import Workbook

from agents.prior_art import PriorArtChecker
from agents.project_agent import ProjectAgent, article_text, assess_project, main
from data.build_project_dataset import build_synthetic_dataset, write_dataset
from models.train_project_agent import split_by_domain, undersample_training
from models.evaluation import best_fbeta_threshold, configured_beta, split_crawler_domains
from crawler.crawler_agent import CrawlerAgent


class ProjectDatasetTests(unittest.TestCase):
    def test_training_undersampling_is_exact_reproducible_and_without_replacement(self):
        for positive_count, negative_count in ((24, 21), (9, 40)):
            records = [{"text": f"Przykład {label} {index}", "label": label}
                       for label, count in ((1, positive_count), (0, negative_count))
                       for index in range(count)]
            sampled = undersample_training(records)
            count = min(positive_count, negative_count)
            self.assertEqual(len(sampled), count * 2)
            self.assertEqual(sum(item["label"] == 1 for item in sampled), count)
            self.assertEqual(sum(item["label"] == 0 for item in sampled), count)
            self.assertEqual(len({item["text"] for item in sampled}), len(sampled))
            self.assertEqual(sampled, undersample_training(records))
            self.assertEqual(len(records), positive_count + negative_count)
        with self.assertRaisesRegex(ValueError, "pozytywnych i negatywnych"):
            undersample_training([{"text": "Przykład", "label": 1}] * 2)

    def test_project_fit_does_not_reweight_classes(self):
        from torch import nn
        records = [{"text": f"Przykład {index}", "label": int(index < 3)} for index in range(10)]
        agent = ProjectAgent(hidden_size=8)
        with patch("agents.project_agent.nn.CrossEntropyLoss", wraps=nn.CrossEntropyLoss) as loss:
            agent.fit(records, epochs=1)
        loss.assert_called_once_with()

    def test_project_dropout_is_configurable_from_environment(self):
        records = [{"text": f"Przykład {index}", "label": int(index < 3)} for index in range(10)]
        with patch.dict(os.environ, {"PROJECT_AGENT_DROPOUT": "0.3"}):
            agent = ProjectAgent(hidden_size=8)
            agent.fit(records, epochs=1)
        self.assertEqual(agent.model.layers[2].p, 0.3)
        with patch.dict(os.environ, {"PROJECT_AGENT_DROPOUT": "1"}):
            with self.assertRaisesRegex(ValueError, "PROJECT_AGENT_DROPOUT"):
                ProjectAgent()

    def test_fbeta_prefers_precision_and_counts_unknown_as_not_detected(self):
        threshold, score = best_fbeta_threshold([0.9, 0.8, 0.7, None], [True, False, True, True])
        self.assertEqual(threshold, 0.9)
        self.assertAlmostEqual(score, 1.25 / 1.75)
        self.assertEqual(best_fbeta_threshold([0.2, 0.8], [False, False]), (1.0, 0.0))

    def test_beta_configuration_changes_threshold(self):
        probabilities = [0.9, 0.8, 0.7]
        labels = [True, False, True]
        with patch.dict(os.environ, {"AGENT_F_BETA": "0.1"}):
            self.assertEqual(best_fbeta_threshold(probabilities, labels, configured_beta())[0], 0.9)
        with patch.dict(os.environ, {"AGENT_F_BETA": "0.9"}):
            self.assertEqual(best_fbeta_threshold(probabilities, labels, configured_beta())[0], 0.7)
        with patch.dict(os.environ, {"AGENT_F_BETA": "1"}):
            self.assertEqual(best_fbeta_threshold(probabilities, labels, configured_beta())[0], 0.7)

    def test_crawler_threshold_is_saved_and_changes_article_decision(self):
        records = [{"url": f"https://{domain}.example/{category}", "category": category}
                   for domain in ("a", "b", "c") for category in ("article", "listing", "sitemap", "other")]
        train, validation = split_crawler_domains(records)
        self.assertTrue({item["url"].split("/")[2] for item in train}.isdisjoint(
            {item["url"].split("/")[2] for item in validation}))
        agent = CrawlerAgent()
        agent.fit([item["url"] for item in train], [item["category"] for item in train], epochs=1)
        agent.article_threshold = 0.8
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "crawler.pt"
            agent.save(path)
            restored = CrawlerAgent.load(path)
        self.assertEqual(restored.article_threshold, 0.8)
        with patch.object(restored, "predict_proba", return_value={
            "article": 0.6, "listing": 0.3, "sitemap": 0.05, "other": 0.05
        }):
            self.assertEqual(restored.classify("https://example.test"), "listing")
            restored.article_threshold = None
            self.assertEqual(restored.classify("https://example.test"), "article")

    def test_training_calibrates_with_project_evidence_gate(self):
        from models.train_project_agent import train_project
        train = [{"domain": "a", "text": f"Dane treningowe {index}", "label": int(index < 3)}
                 for index in range(17)]
        validation = [
            {"domain": "b", "text": "Opracowano aplikację alfa.", "label": 1},
            {"domain": "b", "text": "Opracowano aplikację beta.", "label": 0},
            {"domain": "b", "text": "Opracowano aplikację gamma.", "label": 1},
            {"domain": "b", "text": "Brak rozpoznanego rozwiązania.", "label": 1},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.json"
            model = Path(directory) / "model.pt"
            path.write_text(json.dumps({"records": train + validation}), encoding="utf-8")
            with patch("models.train_project_agent.split_by_domain", return_value=(train, validation)), \
                 patch("models.train_project_agent.ProjectAgent") as agent, \
                 patch.dict(os.environ, {"AGENT_F_BETA": "0.9"}):
                agent.return_value.predict_proba.side_effect = [0.9, 0.8, 0.7]
                train_project(path, model, epochs=3)
            selected = agent.return_value.fit.call_args.args[0]
            self.assertEqual(len(selected), 6)
            self.assertEqual(sum(item["label"] == 1 for item in selected), 3)
            self.assertTrue(all(item in train for item in selected))
            self.assertEqual(agent.return_value.fit.call_args.kwargs, {"epochs": 3})
            agent.return_value.save.assert_called_once_with(model)
            self.assertEqual(agent.return_value.predict_proba.call_count, 3)
            self.assertEqual(agent.return_value.threshold, 0.7)

    def test_crawler_training_uses_configured_beta(self):
        from models import train_models
        train = [{"url": "https://a.example/train", "category": "article"}]
        validation = [
            {"url": "https://b.example/one", "category": "article"},
            {"url": "https://b.example/two", "category": "other"},
            {"url": "https://b.example/three", "category": "article"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.json"
            path.write_text(json.dumps({"records": train + validation}), encoding="utf-8")
            environment = {"AGENT_F_BETA": "0.9", "PROJECT_AGENT_DATASET_PATH": str(path),
                           "CRAWLER_AGENT_DATASET_PATH": str(path)}
            output = io.StringIO()
            with patch.dict(os.environ, environment), \
                 patch.object(train_models, "split_by_domain", return_value=(train, validation)), \
                 patch.object(train_models, "undersample_training"), \
                 patch.object(train_models, "split_crawler_domains", return_value=(train, validation)), \
                 patch.object(train_models, "CrawlerAgent") as agent, \
                 patch.object(train_models, "train_project"), redirect_stdout(output):
                agent.return_value.predict_proba.side_effect = [
                    {"article": 0.9}, {"article": 0.8}, {"article": 0.7},
                ]
                train_models.main()
            self.assertEqual(agent.return_value.article_threshold, 0.7)
            self.assertIn("F0.9=", output.getvalue())

    def test_synthetic_dataset_is_balanced_and_split_by_template(self):
        dataset = build_synthetic_dataset()
        train, validation = split_by_domain(dataset["records"])
        self.assertGreater(len(dataset["records"]), 100)
        self.assertEqual(dataset["counts"]["project"], dataset["counts"]["non_project"])
        self.assertTrue({item["domain"] for item in train}.isdisjoint(
            {item["domain"] for item in validation}))
        self.assertTrue(all(item["label_source"] == "synthetic_template" for item in dataset["records"]))

    def test_record_text_ignores_existing_label_and_project_fields(self):
        self.assertEqual(article_text({"source_title": "Tytuł", "content": "Opis", "relevant": True,
                                       "project_title": "Sztuczna etykieta"}), "Tytuł\nOpis")

    def test_generator_does_not_overwrite_existing_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.json"
            path.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_dataset(path)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing")


class ProjectAgentTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"domain": "a", "text": "projekt szkolny aplikacja", "label": 1},
            {"domain": "a", "text": "wycieczka szkolna muzeum", "label": 0},
            {"domain": "b", "text": "projekt miejski aplikacja", "label": 1},
            {"domain": "b", "text": "wycieczka miejska muzeum", "label": 0},
        ]

    def test_verified_url_returns_radar_uuid_and_assessment(self):
        from agents.project_agent import project_from_article
        url = "https://zu.p.lodz.pl/mechaton-trzy-dni-pomyslow-pasji-i-wielkich-wyzwan-na-wydziale-mechanicznym"
        project = project_from_article({"url": url, "source_title": "MECHATON", "content": "Opis"})
        self.assertEqual(project["title"], "Mechanizm Tilt & Lift do elektrycznego wózka inwalidzkiego")
        self.assertEqual(project["flags"]["pci_compatible"], True)
        self.assertEqual(project["assessment"]["status"], "development")
        self.assertEqual(project["project_title_source"], "curated_reference")
        self.assertEqual(project["entity_type"], "Uczelnia wyższa (Politechnika Łódzka – Wydział Mechaniczny)")
        self.assertIn("mechatronika", project["keywords"])
        self.assertTrue(project["pci_compatibility"]["compatible"])
        self.assertIn("pionowe podnoszenie", project["summary"])
        self.assertEqual(len(project["uuid"]), 36)

    def test_assessment_uses_only_confirmed_criteria(self):
        result = assess_project("Opracowano nowatorską aplikację i zdobyto nagrodę. "
            "Działający prototyp monitoruje wodę. Można zastosować rozwiązanie w innych szkołach.")
        self.assertEqual(result["score"], 72)
        self.assertEqual(result["coverage"], 0.65)
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual([item["grade"] for item in result["dimensions"]], [3, None, 5])
        self.assertEqual(result["missing_questions"], ["Innowacyjność i unikalność"])

    def test_assessment_unknown_and_weighted_status(self):
        unknown = assess_project("Nowatorski projekt zdobył pierwszą nagrodę.")
        self.assertIsNone(unknown["score"])
        self.assertEqual(unknown["coverage"], 0)
        self.assertEqual(unknown["status"], "uncertain")
        result = assess_project("Można zastosować rozwiązanie w innych szkołach. "
            "Adaptacja istniejącej technologii wykorzystuje lokalny surowiec. "
            "Działający prototyp monitoruje wodę.")
        self.assertEqual(result["score"], 68)
        self.assertEqual(result["coverage"], 1)
        self.assertEqual(result["status"], "development")

    def test_assessment_recommendation_matrix(self):
        high = assess_project("Gotowy do powielenia model ma wskazanego partnera. "
            "Adaptacja istniejącej technologii wykorzystuje lokalny surowiec.")
        low = assess_project("Rozwiązanie jest tylko w tej szkole. "
            "Adaptacja istniejącej technologii wykorzystuje lokalny surowiec.")
        self.assertEqual(high["coverage"], 0.8)
        self.assertEqual(high["status"], "high")
        self.assertEqual(low["coverage"], 0.8)
        self.assertEqual(low["status"], "low")

    def test_assessment_is_scoped_to_each_project(self):
        agent = ProjectAgent(hidden_size=8)
        source = {"articles": [{"content": "Projekt „Alfa” opracował aplikację. "
            "Działający prototyp monitoruje wodę.\nProjekt „Beta” zbudował czujnik."}]}
        with patch.object(agent, "predict_proba", return_value=0.9):
            projects = agent.classify_results(source)["projects"]
        self.assertEqual(projects[0]["assessment"]["coverage"], 0.2)
        self.assertEqual(projects[1]["assessment"]["coverage"], 0)

    def test_negated_and_planned_facts_do_not_count(self):
        result = assess_project("Prototyp nie działa. Brak danych: działający prototyp. "
            "Planowany działający prototyp monitoruje wodę.")
        self.assertEqual(result["coverage"], 0)

    def test_only_explicit_contact_is_extracted(self):
        from agents.project_agent import project_from_article
        project = project_from_article({"content": "Autor: Jan Kowalski.\nKontakt: zespol@example.pl"})
        self.assertEqual(project["contact_email"], "zespol@example.pl")
        self.assertEqual(project_from_article({"content": "Wiadomość: redakcja@example.pl"})["contact_email"], "")

    def test_domain_split_and_model_round_trip(self):
        train, validation = split_by_domain(self.records)
        self.assertTrue({item["domain"] for item in train}.isdisjoint(
            {item["domain"] for item in validation}))
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        agent.threshold = 0.73
        before = agent.predict_proba("projekt szkolny aplikacja")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            agent.save(path)
            loaded = ProjectAgent.load(path)
            self.assertAlmostEqual(before, loaded.predict_proba("projekt szkolny aplikacja"))
            self.assertEqual(loaded.threshold, 0.73)
        self.assertIsNone(loaded.predict_proba("nieznanewyrazy"))

    def test_default_threshold_and_topics_are_scoped_to_each_project(self):
        agent = ProjectAgent(hidden_size=8)
        agent.threshold = 0.8
        source = {"articles": [{"content": "Projekt „Alfa” opracował aplikację edukacyjną dla uczniów. "
            "Projekt „Beta” zbudował czujnik do monitorowania wody."}]}
        with patch.object(agent, "predict_proba", return_value=0.7):
            self.assertEqual(agent.classify_results(source)["projects"], [])
            projects = agent.classify_results(source, threshold=0.6)["projects"]
        self.assertIn("Edukacja", projects[0]["domain_tags"])
        self.assertIn("Technologie cyfrowe", projects[0]["domain_tags"])
        self.assertNotIn("Środowisko", projects[0]["domain_tags"])
        self.assertIn("Środowisko", projects[1]["domain_tags"])
        self.assertIn("wody", projects[1]["keywords"])
        self.assertNotIn("wody", projects[0]["keywords"])

    def test_classification_preserves_source_and_marks_unknown(self):
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        source = {"articles": [{"url": "1", "content": "Projekt: szkoła opracowała aplikację dla uczniów."},
                       {"url": "2", "content": "nieznanewyrazy"}]}
        output = agent.classify_results(source, threshold=0)
        self.assertEqual(output["projects"][0]["url"], "1")
        self.assertEqual(output["projects"][0]["summary"], "Projekt: szkoła opracowała aplikację dla uczniów.")
        self.assertEqual(output["records"][0]["analyzed_text"], "Projekt: szkoła opracowała aplikację dla uczniów.")
        self.assertIsNone(output["records"][1]["project_detection"]["is_project"])
        self.assertNotIn("project_detection", source["articles"][0])

    def test_prior_art_is_checked_only_for_detected_projects(self):
        agent = ProjectAgent(hidden_size=8)
        checker = unittest.mock.Mock()
        checker.check.return_value = {"status": "matches_found", "matches": []}
        source = {"articles": [
            {"url": "1", "content": "Uczniowie opracowali aplikację dla uczniów."},
            {"url": "2", "content": "Odbyły się warsztaty."},
        ]}
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results(source, prior_art_checker=checker)
        checker.check.assert_called_once()
        self.assertEqual(output["projects"][0]["prior_art"]["status"], "matches_found")
        self.assertNotIn("prior_art", output["records"][1])

    def test_cli_separates_projects_and_analyzed_data(self):
        agent = ProjectAgent(hidden_size=8)
        agent.fit(self.records, epochs=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps({"articles": [
                {"url": "1", "source_title": "Tytuł", "content": "Projekt: szkoła opracowała aplikację dla uczniów."},
                {"url": "2", "source_title": "Inny", "content": "nieznanewyrazy"},
            ]}), encoding="utf-8")
            output = root / "projects.json"
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(output),
                                    "--model", str(root / "model.pt"), "--threshold", "0", "--no-prior-art"]), \
                 patch.object(ProjectAgent, "load", return_value=agent):
                main()
            projects = json.loads(output.read_text(encoding="utf-8"))
            data = json.loads((root / "data.json").read_text(encoding="utf-8"))
            self.assertEqual(list(projects), ["projects"])
            self.assertEqual([item["url"] for item in projects["projects"]], ["1"])
            self.assertNotIn("content", projects["projects"][0])
            self.assertEqual(projects["projects"][0]["project_title"], "Aplikację dla uczniów")
            self.assertEqual(projects["projects"][0]["summary"], "Projekt: szkoła opracowała aplikację dla uczniów.")
            self.assertEqual(len(data["records"]), 2)
            self.assertEqual(data["records"][0]["analyzed_text"], "Tytuł\nProjekt: szkoła opracowała aplikację dla uczniów.")
            self.assertEqual(data["records"][0]["content"], "Projekt: szkoła opracowała aplikację dla uczniów.")

    def test_cli_rejects_output_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "data.json"
            source.write_text("original", encoding="utf-8")
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(Path(directory) / "projects.json")]):
                with self.assertRaises(ValueError):
                    main()
            self.assertEqual(source.read_text(encoding="utf-8"), "original")

    def test_cli_persists_prior_art_by_default(self):
        agent = ProjectAgent(hidden_size=8)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps({"articles": [{"url": "1", "content":
                "Uczniowie opracowali aplikację monitorującą jakość wody."}]}), encoding="utf-8")
            output = root / "projects.json"
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(output)]), \
                 patch.object(ProjectAgent, "load", return_value=agent), \
                 patch.object(agent, "predict_proba", return_value=0.9), \
                 patch("agents.project_agent.PriorArtChecker") as checker:
                checker.return_value.check.return_value = {"status": "inconclusive", "matches": []}
                main()
            project = json.loads(output.read_text(encoding="utf-8"))["projects"][0]
            self.assertEqual(project["prior_art"]["status"], "inconclusive")
            checker.return_value.close.assert_called_once()

    def test_extracts_named_project_from_article(self):
        from agents.project_agent import project_from_article
        project = project_from_article({"source_title": "Szkoła", "url": "https://example.pl",
            "content": "Projekt „Cyfrowa Szkoła” wspiera naukę.\nUczniowie testują aplikację."})
        self.assertEqual(project["project_title"], "Cyfrowa Szkoła")
        self.assertIn("testują aplikację", project["summary"])
        self.assertEqual(project["project_title_source"], "article_content")
        self.assertIsNone(project["pci_compatibility"]["compatible"])
        self.assertEqual(project["url"], "https://example.pl")

    def test_infers_descriptive_name_from_innovation_evidence(self):
        from agents.project_agent import innovation_evidence, project_from_article
        article = {"source_title": "Program stypendialny", "content":
            "Obecnie opracowuje autorski proces mikroenkapsulacji substancji bioaktywnych, "
            "który chciałby w przyszłości opatentować."}
        project = project_from_article(article)
        self.assertEqual(project["project_title"], "Autorski proces mikroenkapsulacji substancji bioaktywnych")
        self.assertEqual(project["project_title_source"], "article_evidence")
        self.assertEqual(innovation_evidence(
            "Zrealizowano 204 projekty w zakresie rozbudowy bazy edukacyjnej uczelni medycznych."), [])

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

    def test_extracts_multiple_projects_with_separate_evidence_and_creators(self):
        agent = ProjectAgent(hidden_size=8)
        source = {"articles": [{"url": "1", "source_title": "Innowacje", "content":
            "Projekt „Alfa” opracował aplikację do nauki. Autor: Jan Kowalski.\n"
            "Projekt „Beta” zbudował czujnik wody. Autor: Anna Nowak.\n"
            "Projekt „Gamma” organizuje szkolenia."}]}
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results(source)
        self.assertEqual([p["project_title"] for p in output["projects"]], ["Alfa", "Beta"])
        self.assertEqual([p["people"] for p in output["projects"]],
                         [[{"name": "Jan Kowalski"}], [{"name": "Anna Nowak"}]])
        self.assertEqual([p["evidence"] for p in output["projects"]],
                         [["Projekt „Alfa” opracował aplikację do nauki."],
                          ["Projekt „Beta” zbudował czujnik wody."]])
        self.assertEqual([p["url"] for p in output["projects"]], ["1", "1"])

    def test_deduplicates_before_prior_art_without_merging_unknown_or_distinct_creators(self):
        agent = ProjectAgent(hidden_size=8)
        checker = unittest.mock.Mock()
        articles = [
            {"url": "1", "content": "Projekt „Alfa” opracował aplikację. Autor: Jan Kowalski."},
            {"url": "2", "content": "Projekt „ALFA” opracował system. Autor: Jan Kowalski."},
            {"url": "3", "content": "Projekt „Alfa” zbudował czujnik. Autor: Anna Nowak."},
            {"url": "4", "content": "Projekt „Alfa” opracował aplikację."},
            {"url": "5", "content": "Projekt „Alfa” opracował aplikację."},
            {"url": "6", "content": "Projekt „Beta” opracował aplikację.\nBeneficjent: Szkoła"},
            {"url": "7", "content": "Projekt „beta” opracował aplikację.\nBeneficjent: SZKOŁA"},
        ]
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results({"articles": articles}, prior_art_checker=checker)
        self.assertEqual([project["url"] for project in output["projects"]], ["1", "3", "4", "5", "6"])
        self.assertEqual(checker.check.call_count, 5)
        self.assertEqual(len(output["records"]), 7)

    def test_multiple_projects_in_one_sentence_and_repeated_project(self):
        agent = ProjectAgent(hidden_size=8)
        source = {"articles": [{"url": "1", "content":
            "Projekt „Alfa” opracował aplikację, a projekt „Beta” zbudował czujnik. "
            "Twórca: Anna Nowak.\n"
            "Projekt „Beta” opracował urządzenie. Twórca: Anna Nowak."}]}
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results(source)
        self.assertEqual([p["project_title"] for p in output["projects"]], ["Alfa", "Beta"])
        self.assertEqual(output["projects"][1]["people"], [{"name": "Anna Nowak"}])
        self.assertIn("czujnik", output["projects"][1]["summary"])

    def test_cli_writes_deduplicated_projects_and_preserves_articles(self):
        agent = ProjectAgent(hidden_size=8)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text(json.dumps({"articles": [
                {"url": "1", "content": "Projekt „Alfa” opracował aplikację. Twórca: Jan Kowalski.\n"
                 "Projekt „Beta” zbudował czujnik. Twórca: Anna Nowak."},
                {"url": "2", "content": "Projekt „Alfa” opracował aplikację. Twórca: Jan Kowalski."},
            ]}), encoding="utf-8")
            output = root / "projects.json"
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(output),
                                    "--no-prior-art"]), \
                 patch.object(ProjectAgent, "load", return_value=agent), \
                 patch.object(agent, "predict_proba", return_value=0.9):
                main()
            projects = json.loads(output.read_text(encoding="utf-8"))["projects"]
            records = json.loads((root / "data.json").read_text(encoding="utf-8"))["records"]
            self.assertEqual([p["project_title"] for p in projects], ["Alfa", "Beta"])
            self.assertEqual(len(records), 2)

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

    def test_only_concrete_innovations_pass(self):
        agent = ProjectAgent(hidden_size=8)
        articles = [
            {"url": "1", "content": "Nauczyciele uczestniczyli w szkoleniu w ramach projektu Erasmus."},
            {"url": "2", "content": "Program rządowy finansuje warsztaty z używania technologii cyfrowych."},
            {"url": "3", "content": "Uczniowie opracowali nową aplikację ułatwiającą naukę."},
            {"url": "4", "content": "Zespół zbudował prototyp urządzenia monitorującego jakość wody."},
        ]
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results({"articles": articles})
        self.assertEqual([project["url"] for project in output["projects"]], ["3", "4"])
        self.assertEqual([item["project_detection"]["is_project"] for item in output["records"]],
                         [False, False, True, True])

    def test_generic_course_descriptions_do_not_match(self):
        from agents.project_agent import innovation_evidence
        self.assertEqual(innovation_evidence("Operatorzy kontrolują procesy przetwarzania tworzyw sztucznych."), [])
        self.assertEqual(innovation_evidence("Uczniowie nauczą się tworzenia i testowania oprogramowania."), [])
        self.assertEqual(innovation_evidence("Szkoła rozwija kompetencje cyfrowe i dostosowuje metody nauczania."), [])
        self.assertEqual(innovation_evidence("Technik opracowuje dokumentację techniczną urządzeń i systemów."), [])
        self.assertEqual(innovation_evidence("Przykładowe rozwiązania egzaminów zostały opracowane przez komisję."), [])
        self.assertTrue(innovation_evidence("Uczniowie opracowali nową metodę oczyszczania wody."))
        self.assertEqual(innovation_evidence("Uczniowie nie zbudowali prototypu urządzenia."), [])


class PriorArtTests(unittest.TestCase):
    project = {"project_title": "Water quality sensor", "summary": "Water quality sensor measures pollution"}

    def test_matches_sources_and_caches_interreg(self):
        calls = []
        workbook = Workbook()
        workbook.active.append(["Wykaz projektów"])
        workbook.active.append(["Project no.", "Project title", "Project description"])
        workbook.active.append(["PL-1", "Water quality sensor", "Sensor measures water quality"])
        spreadsheet = io.BytesIO()
        workbook.save(spreadsheet)
        workbook.close()

        def respond(request):
            calls.append(request.url.path)
            if request.url.path.endswith("accesstoken"):
                return httpx.Response(200, json={"access_token": "test"})
            if request.url.path.endswith("search/biblio"):
                self.assertEqual(request.headers["x-ops-range"], "1-25")
                return httpx.Response(200, text='<world-patent-data><biblio-search><search-result>'
                    '<exchange-document country="EP" doc-number="123" kind="A1">'
                    '<invention-title>Water quality sensor</invention-title>'
                    '</exchange-document></search-result></biblio-search></world-patent-data>')
            if request.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"items": [
                    {"title": ["Water quality sensor"], "DOI": "10.1/test", "URL": "https://doi.org/10.1/test"},
                    {"title": ["Unrelated subject"]}]}})
            if request.url.path.endswith(".xlsx"):
                return httpx.Response(200, content=spreadsheet.getvalue())
            return httpx.Response(200, text='<a href="/wykaz.xlsx">Lista projektów</a>')

        with patch.dict(os.environ, {"EPO_OPS_KEY": "key", "EPO_OPS_SECRET": "secret",
                                     "PBN_APP_ID": "", "PBN_APP_TOKEN": ""}), \
             httpx.Client(transport=httpx.MockTransport(respond)) as client:
            checker = PriorArtChecker(client)
            result = checker.check(self.project)
            checker.check(self.project)
        self.assertEqual(result["status"], "matches_found")
        self.assertEqual({match["source"] for match in result["matches"]}, {"epo", "crossref", "interreg"})
        self.assertEqual(result["sources"]["epo"]["status"], "ok")
        self.assertEqual(next(match for match in result["matches"] if match["source"] == "epo")["identifier"], "EP123A1")
        self.assertEqual(calls.count("/lista-projektow/"), 1)
        self.assertEqual(calls.count("/wykaz.xlsx"), 1)
        self.assertEqual(calls.count("/3.2/auth/accesstoken"), 1)

    def test_failures_are_not_mistaken_for_no_prior_art(self):
        def respond(request):
            if request.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"items": []}})
            return httpx.Response(503)

        with patch.dict(os.environ, {"EPO_OPS_KEY": "", "EPO_OPS_SECRET": "",
                                     "PBN_APP_ID": "", "PBN_APP_TOKEN": ""}), \
             httpx.Client(transport=httpx.MockTransport(respond)) as client:
            result = PriorArtChecker(client).check(self.project)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["sources"]["epo"]["status"], "unavailable")
        self.assertEqual(result["sources"]["interreg"]["status"], "unavailable")
        self.assertEqual(result["sources"]["crossref"]["status"], "ok")
        self.assertEqual(result["matches"], [])

    def test_pbn_search_uses_institution_credentials(self):
        def respond(request):
            self.assertEqual(request.headers["x-app-id"], "institution")
            self.assertEqual(request.headers["x-app-token"], "token")
            return httpx.Response(200, json={"content": [{"mongoId": "123", "objectJson":
                {"title": "Water quality sensor", "doi": "10.1/test"}}]})

        with patch.dict(os.environ, {"PBN_APP_ID": "institution", "PBN_APP_TOKEN": "token"}), \
             httpx.Client(transport=httpx.MockTransport(respond)) as client:
            records = PriorArtChecker(client)._pbn("water quality sensor")
        self.assertEqual(records[0]["url"], "https://doi.org/10.1/test")
        self.assertEqual(records[0]["source"], "pbn")

    def test_invalid_spreadsheet_is_unavailable(self):
        def respond(request):
            if request.url.host == "api.crossref.org":
                return httpx.Response(200, json={"message": {"items": []}})
            if request.url.path.endswith(".xlsx"):
                return httpx.Response(200, content=b"not a spreadsheet")
            return httpx.Response(200, text='<a href="/wykaz.xlsx">Lista projektów</a>')

        with patch.dict(os.environ, {"EPO_OPS_KEY": "", "EPO_OPS_SECRET": "",
                                     "PBN_APP_ID": "", "PBN_APP_TOKEN": ""}), \
             httpx.Client(transport=httpx.MockTransport(respond)) as client:
            result = PriorArtChecker(client).check(self.project)
        self.assertEqual(result["sources"]["interreg"]["status"], "unavailable")

    def test_short_query_skips_sources(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: self.fail("unexpected request"))) as client:
            result = PriorArtChecker(client).check({"project_title": "System"})
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(all(source["status"] == "skipped" for source in result["sources"].values()))


if __name__ == "__main__":
    unittest.main()