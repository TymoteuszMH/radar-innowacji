import unittest

from agents.content_utils import extract_main_text
from agents.local_agent import LocalAgent, _DATE_PATTERN
from crawler.crawler import Crawler


class UrlQualityTests(unittest.TestCase):
    def test_removes_ui_query_values_and_keeps_pagination(self) -> None:
        url = (
            "https://example.test/events?mini=2026-10&qt-news=0&blindFriendly=1"
            "&page=2&p=452#top"
        )
        self.assertEqual(
            Crawler._normalize_url(url),
            "https://example.test/events?page=2&p=452",
        )

    def test_ignores_calendar_view_paths(self) -> None:
        url = "https://example.test/calendar-node-field-data-wydarzenia/123-event"
        self.assertTrue(Crawler._is_ignored_url(url))
        self.assertFalse(Crawler._is_ignored_url("https://example.test/aktualnosci/123"))


class MainContentTests(unittest.TestCase):
    def test_main_text_excludes_navigation_and_footer(self) -> None:
        html = """
        <html><body>
          <nav><a>Projekt badawczy grant inwestycja</a></nav>
          <main id="main-content"><p>Plan lekcji i godziny zajęć.</p></main>
          <footer>Projekt wdrożeniowy kontakt</footer>
        </body></html>
        """
        text = extract_main_text(html)
        self.assertIn("Plan lekcji", text)
        self.assertNotIn("grant", text)
        self.assertNotIn("wdrożeniowy", text)

    def test_nav_keywords_do_not_make_page_relevant(self) -> None:
        record = {
            "domain": "example.test",
            "url": "https://example.test/plan",
            "title": "Plan zajęć",
            "content": "<nav>Projekty badawcze, granty i inwestycje</nav><main>Plan lekcji dla klas.</main>",
            "crawler_category": "article",
        }
        result = LocalAgent._format_record(
            record,
            {"junk": 0.1, "article": 0.9},
            0.5,
        )
        self.assertFalse(result["relevant"])


class LocalRuleQualityTests(unittest.TestCase):
    def test_date_regex_only_accepts_full_dates(self) -> None:
        valid = "2025-11-14, 14.11.2025, 14-11-2025"
        matches = _DATE_PATTERN.findall(valid)
        self.assertEqual(len(matches), 3)
        for invalid in ("9.45-10", "14.00-22", "2.1.19", "52-33-33"):
            self.assertIsNone(_DATE_PATTERN.search(invalid), invalid)

    def test_institution_names_are_not_people(self) -> None:
        record = {
            "domain": "example.test",
            "url": "https://example.test/project",
            "title": "Projekt badawczy",
            "content": (
                "Koordynator Urząd Miasta Bydgoszczy realizuje projekt badawczy. "
                "Koordynatorka Anna Nowak prowadzi testy rozwiązania."
            ),
            "crawler_category": "article",
        }
        result = LocalAgent._format_record(
            record,
            {"junk": 0.1, "article": 0.9},
            0.5,
        )
        self.assertEqual([person["name"] for person in result["people"]], ["Anna Nowak"])

    def test_confident_junk_forces_relevant_false(self) -> None:
        record = {
            "domain": "example.test",
            "url": "https://example.test/project",
            "title": "Projekt badawczy",
            "content": "Artykuł opisuje projekt badawczy i inwestycję.",
            "crawler_category": "article",
        }
        result = LocalAgent._format_record(
            record,
            {"junk": 0.9, "article": 0.1},
            0.5,
        )
        self.assertTrue(result["is_article"])
        self.assertFalse(result["relevant"])


if __name__ == "__main__":
    unittest.main()