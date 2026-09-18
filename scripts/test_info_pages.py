import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CITIES = (
    "Paris",
    "London",
    "Chicago",
    "Washington",
    "Boston",
    "Berlin",
    "Madrid",
    "New York City",
)


def page(name: str) -> str:
    return (ROOT / "public" / name).read_text(encoding="utf-8")


def section(html: str, heading: str) -> str:
    match = re.search(
        rf'<section class="info-card"><h2>{re.escape(heading)}</h2>(.*?)</section>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError(f"Missing section: {heading}")
    return match.group(1)


class InfoPageContentTests(unittest.TestCase):
    def test_about_keeps_all_city_data_together(self):
        html = page("legal.html")
        data = section(html, "Data")
        for city in CITIES:
            self.assertIn(f"<strong>{city}:</strong>", data)
        self.assertNotIn("<h2>New York City data</h2>", html)

    def test_endpoint_boundary_explanation_lives_only_in_faq(self):
        about = page("legal.html")
        faq = page("faq.html")
        self.assertNotIn("<h2>Puzzle endpoint boundaries</h2>", about)
        endpoints = section(faq, "Which lines are included?")
        self.assertIn("administrative geography API", endpoints)
        self.assertIn("Greater London Authority boundary", endpoints)
        self.assertIn("ALKIS state boundary", endpoints)

    def test_city_specific_connections_cover_every_city(self):
        connections = section(page("rules.html"), "City-specific connections")
        for city in CITIES:
            self.assertIn(f"<strong>{city}:</strong>", connections)

    def test_city_specific_faq_topics_cover_every_city(self):
        html = page("faq.html")
        for heading in (
            "Which lines are included?",
            "When is walking an option?",
            "How are waiting times estimated?",
        ):
            content = section(html, heading)
            for city in CITIES:
                self.assertIn(f"<strong>{city}:</strong>", content, heading)


if __name__ == "__main__":
    unittest.main()
