import json
import tempfile
import unittest
from pathlib import Path

from scripts.filter_impact_factor import filter_articles_by_if, filter_file


def available(value, **extra):
    return {
        "title": f"IF {value}",
        "impact_factor": value,
        "impact_factor_status": "available",
        **extra,
    }


class FilterArticlesTests(unittest.TestCase):
    def test_minimum_is_inclusive(self):
        articles = [available(5.999), available(6.0), available(6.001)]

        filtered, stats = filter_articles_by_if(articles)

        self.assertEqual([article["impact_factor"] for article in filtered], [6.0, 6.001])
        self.assertEqual(stats, {"kept": 2, "removed": 1, "unresolved": 0})

    def test_available_with_null_impact_factor_is_invalid(self):
        with self.assertRaisesRegex(ValueError, "available.*impact_factor"):
            filter_articles_by_if([available(None)])

    def test_not_available_yet_and_unresolved_null_values_are_kept(self):
        articles = [
            {
                "title": "Future",
                "impact_factor": None,
                "impact_factor_status": "not_available_yet",
            },
            {
                "title": "No match",
                "impact_factor": None,
                "impact_factor_status": "unresolved",
                "impact_factor_reason": "no_match",
            },
        ]

        filtered, stats = filter_articles_by_if(articles)

        self.assertEqual(filtered, articles)
        self.assertEqual(stats, {"kept": 2, "removed": 0, "unresolved": 2})

    def test_filter_does_not_modify_input_or_unrelated_fields(self):
        article = available(6.0, custom={"nested": True})
        original = json.dumps(article, sort_keys=True)

        filtered, _ = filter_articles_by_if([article])

        self.assertEqual(json.dumps(article, sort_keys=True), original)
        self.assertEqual(filtered[0], article)


class FilterFileTests(unittest.TestCase):
    def test_file_filter_is_atomic_and_idempotent(self):
        payload = {
            "date": "2026-07-23",
            "metadata": {"untouched": True},
            "articles": [
                available(5.9, custom="remove"),
                available(6.0, custom="keep"),
                {
                    "title": "Unresolved",
                    "impact_factor": None,
                    "impact_factor_status": "unresolved",
                    "impact_factor_reason": "no_match",
                    "custom": "also keep",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-23-brainmri.json"
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            first_stats = filter_file(path)
            first_bytes = path.read_bytes()
            second_stats = filter_file(path)
            readback = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(first_stats, {"kept": 2, "removed": 1, "unresolved": 1})
            self.assertEqual(second_stats, {"kept": 2, "removed": 0, "unresolved": 1})
            self.assertEqual(path.read_bytes(), first_bytes)
            self.assertEqual(readback["metadata"], {"untouched": True})
            self.assertEqual([a["custom"] for a in readback["articles"]], ["keep", "also keep"])
            self.assertEqual(list(Path(tmp).glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
