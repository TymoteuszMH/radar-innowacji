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
from agents.project_agent import ProjectAgent, article_text, assess_project, main, prepare_text, tokenize_text
from data.build_project_dataset import build_training_dataset, write_dataset
from models.train_project_agent import split_records
from models.evaluation import best_fbeta_threshold, split_crawler_domains
from crawler.crawler_agent import CrawlerAgent


class BertClassifierTests(unittest.TestCase):
    @staticmethod
    def tokenizer():
        from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, processors
        from transformers import BertTokenizerFast
        vocab = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3,
                 "head": 4, "tail": 5, "middle": 6, "projekt": 7, "szum": 8}
        backend = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
        backend.normalizer = normalizers.BertNormalizer()
        backend.pre_tokenizer = pre_tokenizers.Whitespace()
        backend.post_processor = processors.TemplateProcessing(
            single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 2), ("[SEP]", 3)]
        )
        return BertTokenizerFast(tokenizer_object=backend, unk_token="[UNK]",
                                 pad_token="[PAD]", cls_token="[CLS]", sep_token="[SEP]")

    def test_head_tail_word_and_token_limits(self):
        words = ["head"] * 200 + ["middle"] * 51 + ["tail"] * 150
        prepared = prepare_text(" ".join(words))
        self.assertEqual(prepared, " ".join(words[:200]) + " ... " + " ".join(words[-150:]))
        self.assertEqual(prepare_text("head " * 350).split(), ["head"] * 350)
        encoded = tokenize_text(self.tokenizer(), "head-tail " * 600)
        self.assertEqual(len(encoded["input_ids"]), 512)
        self.assertEqual(encoded["input_ids"][1], 4)
        self.assertEqual(encoded["input_ids"][-2], 5)

    def test_weighted_loss(self):
        import torch
        from types import SimpleNamespace
        from models.train_project_agent import WeightedTrainer
        trainer = object.__new__(WeightedTrainer)
        trainer.class_weights = torch.tensor([0.6, 2.4])
        logits = torch.tensor([[2.0, 0.0], [1.0, 0.0]])
        labels = torch.tensor([0, 1])
        model = lambda **kwargs: SimpleNamespace(logits=logits)
        inputs = {"labels": labels}
        loss, outputs = trainer.compute_loss(model, inputs, return_outputs=True)
        expected = torch.nn.CrossEntropyLoss(weight=trainer.class_weights)(logits, labels)
        self.assertTrue(torch.allclose(loss, expected))
        self.assertIs(outputs.logits, logits)
        self.assertIn("labels", inputs)

    def test_real_training_save_load_and_prediction(self):
        from transformers import BertConfig, BertForSequenceClassification
        from models import train_project_agent
        tokenizer = self.tokenizer()
        config = BertConfig(vocab_size=9, hidden_size=16, num_hidden_layers=1,
                            num_attention_heads=2, intermediate_size=24, num_labels=2)
        records = [{"text": f"{word} projekt", "label": label}
                   for word, label, count in (("szum", 0, 12), ("projekt", 1, 4))
                   for _ in range(count)]
        agent = ProjectAgent()
        settings = {"PROJECT_AGENT_TRAIN_BATCH_SIZE": "4", "PROJECT_AGENT_EVAL_BATCH_SIZE": "2",
                    "PROJECT_AGENT_LEARNING_RATE": "0.0002", "PROJECT_AGENT_WARMUP_RATIO": "0.25",
                    "PROJECT_AGENT_WEIGHT_DECAY": "0.02", "PROJECT_AGENT_VALIDATION_FRACTION": "0.2",
                    "PROJECT_AGENT_SEED": "19", "PROJECT_AGENT_TRAIN_EPOCHS": "1"}
        with patch.dict(os.environ, settings), \
             patch.object(train_project_agent.AutoTokenizer, "from_pretrained", return_value=tokenizer), \
             patch.object(train_project_agent.AutoModelForSequenceClassification, "from_pretrained",
                          return_value=BertForSequenceClassification(config)), \
             patch.object(train_project_agent, "compute_class_weight",
                          wraps=train_project_agent.compute_class_weight) as weight_fn, \
             patch.object(train_project_agent, "TrainingArguments",
                          wraps=train_project_agent.TrainingArguments) as arguments:
            agent.fit(records)
        self.assertEqual(len(weight_fn.call_args.kwargs["y"]), 12)
        self.assertEqual(sum(weight_fn.call_args.kwargs["y"]), 3)
        self.assertEqual(arguments.call_args.kwargs["metric_for_best_model"], "f1")
        self.assertTrue(arguments.call_args.kwargs["load_best_model_at_end"])
        self.assertEqual(arguments.call_args.kwargs["per_device_train_batch_size"], 4)
        self.assertEqual(arguments.call_args.kwargs["per_device_eval_batch_size"], 2)
        self.assertEqual(arguments.call_args.kwargs["learning_rate"], 0.0002)
        self.assertEqual(arguments.call_args.kwargs["warmup_ratio"], 0.25)
        self.assertEqual(arguments.call_args.kwargs["weight_decay"], 0.02)
        self.assertEqual(arguments.call_args.kwargs["seed"], 19)
        self.assertEqual(arguments.call_args.kwargs["num_train_epochs"], 1)
        before = agent.predict("projekt")
        self.assertTrue(0 <= before["probability"] <= 1)
        self.assertEqual(agent.predict("projekt", threshold=0)["label"], 1)
        self.assertEqual(agent.predict("projekt", threshold=1)["label"], 0)
        with self.assertRaises(ValueError):
            agent.predict("projekt", threshold=1.1)
        self.assertIsNone(agent.predict_proba(" "))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            agent.threshold = 0.73
            agent.save(path)
            restored = ProjectAgent.load(path)
            self.assertEqual(restored.threshold, 0.73)
            self.assertAlmostEqual(before["probability"], restored.predict_proba("projekt"), places=6)


class ProjectDatasetTests(unittest.TestCase):
    def test_validation_fraction_and_invalid_configuration(self):
        records = [{"text": f"Przykład {index}", "label": index % 2} for index in range(40)]
        with patch.dict(os.environ, {"PROJECT_AGENT_VALIDATION_FRACTION": "0.25",
                                     "PROJECT_AGENT_SEED": "13"}):
            train, validation = split_records(records)
            self.assertEqual((len(train), len(validation)), (30, 10))
            self.assertEqual(sum(item["label"] for item in validation), 5)
            self.assertEqual((train, validation), split_records(records))
        with patch.dict(os.environ, {"PROJECT_AGENT_VALIDATION_FRACTION": "1"}):
            with self.assertRaisesRegex(ValueError, "PROJECT_AGENT_VALIDATION_FRACTION"):
                split_records(records)
        with patch.dict(os.environ, {"PROJECT_AGENT_LEARNING_RATE": "nan"}):
            with self.assertRaisesRegex(ValueError, "PROJECT_AGENT_LEARNING_RATE"):
                ProjectAgent().fit(records, epochs=1)

    def test_training_cli_uses_configured_paths_and_explicit_epochs(self):
        from models import train_project_agent
        environment = {"PROJECT_AGENT_DATASET_PATH": "data/custom.json",
                       "PROJECT_AGENT_MODEL_PATH": "models/custom-model"}
        with patch.dict(os.environ, environment), \
             patch("sys.argv", ["train_project_agent", "--epochs", "2"]), \
             patch.object(train_project_agent, "train_project") as train:
            train_project_agent.main()
        train.assert_called_once_with(train_project_agent.PROJECT_DIR / "data" / "custom.json",
                                      train_project_agent.PROJECT_DIR / "models" / "custom-model", 2)

    def test_training_split_is_stratified_and_preserves_every_record(self):
        records = [{"text": f"Przykład {label} {index}", "label": label}
                   for label, count in ((1, 33), (0, 120)) for index in range(count)]
        train, validation = split_records(records)
        self.assertEqual((len(train), len(validation)), (122, 31))
        self.assertEqual(sum(item["label"] for item in validation), 7)
        self.assertEqual(len({item["text"] for item in train + validation}), 153)
        self.assertEqual((train, validation), split_records(records))
        with self.assertRaises(ValueError):
            split_records([{"text": "Przykład", "label": 1}] * 2)

    def test_fbeta_prefers_precision_and_counts_unknown_as_not_detected(self):
        threshold, score = best_fbeta_threshold([0.9, 0.8, 0.7, None], [True, False, True, True])
        self.assertEqual(threshold, 0.9)
        self.assertAlmostEqual(score, 1.25 / 1.75)
        self.assertEqual(best_fbeta_threshold([0.2, 0.8], [False, False]), (1.0, 0.0))

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

    def test_crawler_training_uses_f05(self):
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
            environment = {"PROJECT_AGENT_DATASET_PATH": str(path),
                           "CRAWLER_AGENT_DATASET_PATH": str(path)}
            output = io.StringIO()
            with patch.dict(os.environ, environment), \
                 patch.object(train_models, "split_records", return_value=(train, validation)), \
                 patch.object(train_models, "split_crawler_domains", return_value=(train, validation)), \
                 patch.object(train_models, "CrawlerAgent") as agent, \
                 patch.object(train_models, "train_project"), redirect_stdout(output):
                agent.return_value.predict_proba.side_effect = [
                    {"article": 0.9}, {"article": 0.8}, {"article": 0.7},
                ]
                train_models.main()
            self.assertEqual(agent.return_value.article_threshold, 0.9)
            self.assertIn("F0.5=", output.getvalue())

    def test_curated_dataset_has_requested_counts_and_auditable_sources(self):
        dataset = build_training_dataset()
        train, validation = split_records(dataset["records"])
        self.assertEqual(dataset["counts"], {"project": 20, "non_project": 35})
        self.assertEqual(dataset["source_counts"], {
            "generated_junk_page": 7,
            "generated_positive_article": 8,
            "generated_unrelated_article": 8,
            "hard_negative_message": 20,
            "generated_reference_article": 12,
        })
        self.assertEqual(sum(record["label"] == 1 for record in dataset["records"]), 20)
        self.assertEqual(sum(record["label"] == 0 for record in dataset["records"]), 35)
        self.assertEqual(len(train) + len(validation), 55)
        from agents.project_agent import innovation_evidence
        self.assertTrue(all(innovation_evidence(record["text"])
                            for record in dataset["records"] if record["label"] == 1))
        self.assertTrue(all(not innovation_evidence(record["text"])
                            for record in dataset["records"] if record["label"] == 0))

    def test_reference_positives_are_pci_compatible_and_deduplicated(self):
        from data.build_project_dataset import _reference_project_records
        records = _reference_project_records()
        self.assertEqual(len(records), 12)
        self.assertTrue(all(record["label"] == 1 for record in records))
        self.assertTrue(all(record["text_origin"] == "synthetic_paraphrase_from_projects_example"
                    for record in records))
        self.assertEqual(len({record["title"].casefold() for record in records}), len(records))
        self.assertNotIn("droniada-future-forum", " ".join(record["url"] for record in records))

    def test_hard_negative_sample_is_balanced_across_institution_types(self):
        from collections import Counter
        from data.build_project_dataset import _hard_negative_records
        records = _hard_negative_records()
        self.assertEqual(len(records), 20)
        self.assertTrue(all(record["label"] == 0 for record in records))
        self.assertEqual(Counter(record["entity_category"] for record in records), {
            "instytucja_publiczna": 5, "jst": 5, "szkola": 5, "uczelnia": 5,
        })
        self.assertEqual(records, _hard_negative_records())

    def test_record_text_ignores_existing_label_and_project_fields(self):
        self.assertEqual(article_text({"source_title": "Tytuł", "content": "Opis", "relevant": True,
                                       "project_title": "Sztuczna etykieta"}), "Tytuł\nOpis")

    def test_configured_project_output_limits(self):
        from agents.project_agent import project_from_article
        article = {"content": "Uczniowie opracowali aplikację edukacyjną. "
                   "Zespół zbudował czujnik wody. Naukowcy stworzyli prototyp robota."}
        with patch.dict(os.environ, {"PROJECT_AGENT_EVIDENCE_MAX_SENTENCES": "2",
                                     "PROJECT_AGENT_KEYWORDS_MAX": "2",
                                     "PROJECT_AGENT_KEYWORD_PHRASES_MAX": "1"}):
            project = project_from_article(article)
        self.assertEqual(len(project["evidence"]), 2)
        self.assertEqual(len(project["keywords"]), 2)

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

    def test_query_parameters_distinguish_reference_articles(self):
        from agents.project_agent import project_from_article
        known_url = "https://slokwidzyn.edupage.org/news/?gtnid=1082"
        self.assertEqual(ProjectAgent.normalize_url(known_url), "https://slokwidzyn.edupage.org/news?gtnid=1082")
        self.assertNotEqual(ProjectAgent.normalize_url(known_url),
                            ProjectAgent.normalize_url("https://slokwidzyn.edupage.org/news/?gtnid=999"))
        self.assertEqual(project_from_article({"url": known_url})["project_title_source"], "curated_reference")
        self.assertEqual(project_from_article({"url": "https://slokwidzyn.edupage.org/news/?gtnid=999"})["project_title_source"], "source_title")

    def test_verified_article_with_multiple_mentions_is_not_lost(self):
        agent = ProjectAgent()
        source = {"articles": [{"url": "https://slokwidzyn.edupage.org/news/?gtnid=1082",
                                "content": "Projekt „Alfa” w finale. Projekt „Beta” zdobył nagrodę."}]}
        with patch.object(agent, "predict_proba", return_value=None):
            result = agent.classify_results(source)
        self.assertEqual(len(result["projects"]), 1)
        self.assertIn("IDLEK", result["projects"][0]["project_title"])

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
        agent = ProjectAgent()
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

    def test_default_threshold_and_topics_are_scoped_to_each_project(self):
        agent = ProjectAgent()
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
        agent = ProjectAgent()
        source = {"articles": [{"url": "1", "content": "Projekt: szkoła opracowała aplikację dla uczniów."},
                       {"url": "2", "content": "nieznanewyrazy"}]}
        with patch.object(agent, "predict_proba", side_effect=[0.8, None]):
            output = agent.classify_results(source, threshold=0)
        self.assertEqual(output["projects"][0]["url"], "1")
        self.assertEqual(output["projects"][0]["summary"], "Projekt: szkoła opracowała aplikację dla uczniów.")
        self.assertEqual(output["records"][0]["analyzed_text"], "Projekt: szkoła opracowała aplikację dla uczniów.")
        self.assertIsNone(output["records"][1]["project_detection"]["is_project"])
        self.assertNotIn("project_detection", source["articles"][0])

    def test_prior_art_is_checked_only_for_detected_projects(self):
        agent = ProjectAgent()
        checker = unittest.mock.Mock()
        checker.check.return_value = {"status": "matches_found", "matches": []}
        source = {"articles": [
            {"url": "1", "content": "Uczniowie opracowali aplikację dla uczniów."},
            {"url": "2", "content": "Odbyły się warsztaty."},
        ]}
        with patch.object(agent, "predict_proba", side_effect=[0.9, 0.1]):
            output = agent.classify_results(source, prior_art_checker=checker)
        checker.check.assert_called_once()
        self.assertEqual(output["projects"][0]["prior_art"]["status"], "matches_found")
        self.assertNotIn("prior_art", output["records"][1])

    def test_cli_separates_projects_and_analyzed_data(self):
        agent = ProjectAgent()
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
                 patch.object(ProjectAgent, "load", return_value=agent), \
                 patch.object(agent, "predict_proba", side_effect=[0.8, None]):
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

    def test_cli_uses_configured_threshold_and_honors_explicit_override(self):
        from agents import project_agent
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text('{"articles": []}', encoding="utf-8")
            output = root / "projects.json"
            environment = {"PROJECT_AGENT_THRESHOLD": "0.73", "PRIOR_ART_ENABLED": "0",
                           "PROJECT_DATA_OUTPUT_FILE": str(root / "configured-data.json")}
            argv = ["project_agent", "--input", str(source), "--output", str(output)]
            with patch.dict(os.environ, environment), patch("sys.argv", argv), \
                 patch.object(project_agent, "process_file") as process:
                main()
            self.assertEqual(process.call_args.args[2], root / "data.json")
            self.assertEqual(process.call_args.args[4], 0.73)
            self.assertFalse(process.call_args.kwargs["prior_art_enabled"])
            with patch.dict(os.environ, environment), patch("sys.argv", argv + ["--threshold", "0.2"]), \
                 patch.object(project_agent, "process_file") as process:
                main()
            self.assertEqual(process.call_args.args[4], 0.2)

    def test_cli_uses_configured_paths_without_explicit_output(self):
        from agents import project_agent
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            source.write_text('{"articles": []}', encoding="utf-8")
            environment = {"ANALYSIS_OUTPUT_FILE": str(source), "PROJECTS_OUTPUT_FILE": str(root / "out.json"),
                           "PROJECT_DATA_OUTPUT_FILE": str(root / "all.json"),
                           "PROJECT_AGENT_MODEL_PATH": str(root / "model")}
            with patch.dict(os.environ, environment), patch("sys.argv", ["project_agent"]), \
                 patch.object(project_agent, "process_file") as process:
                main()
            self.assertEqual(process.call_args.args[:4],
                             (source, root / "out.json", root / "all.json", root / "model"))

    def test_cli_rejects_output_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "data.json"
            source.write_text("original", encoding="utf-8")
            with patch("sys.argv", ["project_agent", "--input", str(source), "--output", str(Path(directory) / "projects.json")]):
                with self.assertRaises(ValueError):
                    main()
            self.assertEqual(source.read_text(encoding="utf-8"), "original")

    def test_cli_persists_prior_art_by_default(self):
        agent = ProjectAgent()
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

    def test_generic_competition_and_funding_descriptions_are_not_innovation_evidence(self):
        from agents.project_agent import innovation_evidence
        for text in (
            "Konkurs organizowany przez PARP pokazuje technologie powstające w nauce i rozwiązania rozwijane przez przedsiębiorców.",
            "Konkurs jest skierowany do twórców produktów już wdrożonych.",
            "Przygotowanie produktów opracowanych w ramach projektu do wejścia na rynki.",
            "Nowo powstałe firmy pracują nad rozwojem pomysłu aż do powstania produktu.",
        ):
            with self.subTest(text=text):
                self.assertEqual(innovation_evidence(text), [])
        self.assertTrue(innovation_evidence("Studenci opracowali aplikację do monitorowania wody."))

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
        agent = ProjectAgent()
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
        agent = ProjectAgent()
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
        agent = ProjectAgent()
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
        agent = ProjectAgent()
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

    def test_model_candidates_without_evidence_are_rejected(self):
        agent = ProjectAgent()
        source = {"articles": [
            {"url": "1", "source_title": "Warsztaty", "content": "Poznawali projekty edukacyjne."},
            {"url": "2", "source_title": "Projekt", "content": "Już wkrótce"},
        ]}
        with patch.object(agent, "predict_proba", side_effect=[0.9, 0.1]):
            output = agent.classify_results(source)
        self.assertEqual(output["projects"], [])
        self.assertEqual([item["project_detection"]["is_project"] for item in output["records"]],
                         [False, False])
        self.assertEqual(output["records"][0]["project_detection"]["probability"], 0.9)
        self.assertEqual(len(output["records"]), 2)

    def test_probability_threshold_and_evidence_review_flags(self):
        agent = ProjectAgent()
        articles = [
            {"url": "1", "content": "Nauczyciele uczestniczyli w szkoleniu w ramach projektu Erasmus."},
            {"url": "2", "content": "Program rządowy finansuje warsztaty z używania technologii cyfrowych."},
            {"url": "3", "content": "Uczniowie opracowali nową aplikację ułatwiającą naukę."},
            {"url": "4", "content": "Zespół zbudował prototyp urządzenia monitorującego jakość wody."},
        ]
        with patch.object(agent, "predict_proba", side_effect=[0.9, 0.1, 0.9, 0.9]):
            output = agent.classify_results({"articles": articles})
        self.assertEqual([project["url"] for project in output["projects"]], ["3", "4"])
        self.assertEqual([project["flags"]["requires_review"] for project in output["projects"]],
                         [False, False])
        self.assertEqual([item["project_detection"]["is_project"] for item in output["records"]],
                         [False, False, True, True])

    def test_multiple_names_without_evidence_are_not_project_candidates(self):
        agent = ProjectAgent()
        article = {"url": "1", "source_title": "Nowe inicjatywy", "content":
                   "Projekt „Alfa” planuje aplikację. Projekt „Beta” planuje warsztaty."}
        with patch.object(agent, "predict_proba", return_value=0.9):
            output = agent.classify_results({"articles": [article]})
        self.assertEqual(output["projects"], [])
        self.assertFalse(output["records"][0]["project_detection"]["is_project"])

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

    def test_configurable_similarity_and_match_limits(self):
        records = [
            {"source": "crossref", "title": "Water quality sensor", "description": ""},
            {"source": "crossref", "title": "Water quality sensor measures pollution", "description": ""},
            {"source": "crossref", "title": "Water quality", "description": ""},
        ]
        settings = {"PRIOR_ART_MAX_MATCHES": "1", "PRIOR_ART_MIN_SHARED_WORDS": "3",
                    "PRIOR_ART_MIN_SIMILARITY": "0.7", "PRIOR_ART_QUERY_MAX_WORDS": "3"}
        with patch.dict(os.environ, settings), \
             httpx.Client(transport=httpx.MockTransport(lambda request: self.fail("unexpected request"))) as client:
            checker = PriorArtChecker(client)
            with patch.object(checker, "_epo", return_value=[]), patch.object(checker, "_pbn", return_value=[]), \
                 patch.object(checker, "_crossref", return_value=records), patch.object(checker, "_load_interreg", return_value=[]):
                result = checker.check(self.project)
        self.assertEqual(result["query"], "water quality sensor")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["title"], "Water quality sensor measures pollution")
        with patch.dict(os.environ, {"PRIOR_ART_MAX_MATCHES": "0"}):
            with self.assertRaisesRegex(ValueError, "PRIOR_ART_MAX_MATCHES"):
                PriorArtChecker()

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