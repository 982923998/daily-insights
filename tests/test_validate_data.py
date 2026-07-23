import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_data import validate_file, validate_payload


def raw_article(**updates):
    article = {
        "title": "A valid article",
        "summary": "A sufficiently useful abstract.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
        "category": "Brain MRI",
        "source": "pubmed",
        "journal": "Example Journal",
        "published_date": "2026-07-22",
        "date": "2026-07-23",
    }
    article.update(updates)
    return article


def enriched_article(value=6.0, status="available", **updates):
    article = raw_article(
        impact_factor=value,
        impact_factor_year=2025,
        impact_factor_status=status,
        impact_factor_source="unique_base",
        impact_factor_match_method="canonical_name",
        impact_factor_matched_journal="Example Journal",
    )
    article.update(updates)
    return article


class ValidatePayloadStageTests(unittest.TestCase):
    def test_raw_is_default_and_does_not_require_if_fields(self):
        payload = {"date": "2026-07-23", "articles": [raw_article()]}

        self.assertEqual(validate_payload(payload, "brainmri"), [])
        self.assertEqual(validate_payload(payload, "brainmri", stage="raw"), [])

    def test_schema_and_domain_are_validated(self):
        payload = {
            "date": "2026-07-23",
            "articles": [raw_article(category="AI")],
        }

        errors = validate_payload(payload, "brainmri")

        self.assertTrue(any("category" in error and "Brain MRI" in error for error in errors))

    def test_enriched_requires_machine_state_and_provenance_fields(self):
        payload = {"date": "2026-07-23", "articles": [raw_article()]}

        errors = validate_payload(payload, "brainmri", stage="enriched")

        self.assertTrue(any("impact_factor_status" in error for error in errors))
        self.assertTrue(any("impact_factor_source" in error for error in errors))
        self.assertTrue(any("impact_factor_match_method" in error for error in errors))

    def test_enriched_accepts_available_and_unresolved_machine_states(self):
        unresolved = enriched_article(
            None,
            status="unresolved",
            title="A second valid article",
            url="https://pubmed.ncbi.nlm.nih.gov/456/",
            impact_factor_year=None,
            impact_factor_source=None,
            impact_factor_match_method="none",
            impact_factor_matched_journal=None,
            impact_factor_reason="no_match",
        )
        payload = {
            "date": "2026-07-23",
            "articles": [enriched_article(), unresolved],
        }

        self.assertEqual(validate_payload(payload, "brainmri", stage="enriched"), [])

    def test_available_null_is_invalid_in_enriched_stage(self):
        payload = {
            "date": "2026-07-23",
            "articles": [enriched_article(None, status="available")],
        }

        errors = validate_payload(payload, "brainmri", stage="enriched")

        self.assertTrue(any("available" in error and "impact_factor" in error for error in errors))

    def test_final_rejects_known_if_below_minimum_but_keeps_boundary_and_unresolved(self):
        unresolved = enriched_article(
            None,
            status="not_available_yet",
            impact_factor_year=None,
            impact_factor_source="ordinary_raw",
        )
        payload = {
            "date": "2026-07-23",
            "articles": [enriched_article(5.999), enriched_article(6.0), unresolved],
        }

        errors = validate_payload(payload, "brainmri", stage="final")

        below = [error for error in errors if "below minimum" in error]
        self.assertEqual(len(below), 1)
        self.assertIn("5.999", below[0])


class ValidateFileTests(unittest.TestCase):
    def test_filename_top_level_and_article_dates_must_agree(self):
        payload = {
            "date": "2026-07-23",
            "articles": [raw_article(date="2026-07-22")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-21-brainmri.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            errors = validate_file(path, "brainmri")

        self.assertTrue(any("filename date" in error and "2026-07-23" in error for error in errors))
        self.assertTrue(any("must equal top-level date" in error for error in errors))

    def test_filename_domain_must_match_requested_domain(self):
        payload = {"date": "2026-07-23", "articles": [raw_article()]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-23-ai.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            errors = validate_file(path, "brainmri")

        self.assertTrue(any("filename domain" in error and "brainmri" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
