import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_impact_factors as sync


def catalog_row(
    name,
    impact_factor,
    *,
    issn="",
    abbreviation="",
    year=2025,
    source="ordinary_raw",
    status=None,
):
    row = {
        "journal_name": name,
        "journal_name_short": abbreviation,
        "issn": issn,
        "impact_factor": impact_factor,
        "impact_factor_year": year,
        "source": source,
    }
    if status is not None:
        row["impact_factor_status"] = status
    return row


def process_args(path, index, unresolved=None, manual=None, reference=None, crawl=False):
    return {
        "path": path,
        "base_entries": [],
        "letpub_index": index,
        "unresolved": unresolved if unresolved is not None else sync.default_unresolved_registry(),
        "supplement_payload": manual if manual is not None else sync.default_supplement_payload(),
        "reference_payload": reference if reference is not None else sync.default_reference_payload("test"),
        "reference": "test",
        "crawl_online": crawl,
        "timeout": 1,
        "query_cache": {},
    }


class LetPubResolutionTests(unittest.TestCase):
    def assert_result_fields(self, result):
        for field in (
            "impact_factor",
            "impact_factor_year",
            "impact_factor_status",
            "impact_factor_source",
            "impact_factor_match_method",
            "impact_factor_matched_journal",
        ):
            self.assertIn(field, result)

    def test_matching_priority_is_exact_issn_then_canonical_name_then_abbreviation(self):
        index = sync.build_letpub_if_index(
            [
                catalog_row("ISSN Journal", 8.1, issn="1234-5678"),
                catalog_row("Canonical Journal", 7.2),
                catalog_row("Long Journal Name", 6.3, abbreviation="LJN"),
            ]
        )

        by_issn = sync.resolve_article_if(
            {"journal": "Unrelated", "journal_issn": "12345678"}, index
        )
        by_name = sync.resolve_article_if({"journal": "Canonical Journal"}, index)
        by_abbreviation = sync.resolve_article_if({"journal": "L.J.N."}, index)

        self.assertEqual(by_issn["impact_factor_match_method"], "exact_issn")
        self.assertEqual(by_name["impact_factor_match_method"], "canonical_name")
        self.assertEqual(by_abbreviation["impact_factor_match_method"], "abbreviation")
        self.assertEqual([by_issn["impact_factor"], by_name["impact_factor"], by_abbreviation["impact_factor"]], [8.1, 7.2, 6.3])
        self.assert_result_fields(by_issn)

    def test_zero_is_not_available_yet_and_explicit_unresolved_stays_unresolved(self):
        index = sync.build_letpub_if_index(
            [
                catalog_row("Future Journal", 0),
                catalog_row(
                    "Unresolved Journal",
                    None,
                    status="unresolved",
                    year=None,
                ),
            ]
        )

        future = sync.resolve_article_if({"journal": "Future Journal"}, index)
        unresolved = sync.resolve_article_if({"journal": "Unresolved Journal"}, index)

        self.assertIsNone(future["impact_factor"])
        self.assertEqual(future["impact_factor_status"], "not_available_yet")
        self.assertEqual(unresolved["impact_factor_status"], "unresolved")
        self.assertIn("impact_factor_reason", unresolved)

    def test_same_priority_uncomparable_years_are_conflict_not_maximum_if(self):
        index = sync.build_letpub_if_index(
            [
                catalog_row("Conflict Journal", 6.1, year=None),
                catalog_row("Conflict Journal", 99.0, year=2025),
            ]
        )

        result = sync.resolve_article_if({"journal": "Conflict Journal"}, index)

        self.assertEqual(result["impact_factor_status"], "unresolved")
        self.assertEqual(result["impact_factor_reason"], "conflict")
        self.assertIsNone(result["impact_factor"])

    def test_source_priority_beats_larger_or_newer_impact_factor(self):
        index = sync.build_letpub_if_index(
            [
                catalog_row("Priority Journal", 99.0, year=2025, source="ordinary_raw"),
                catalog_row("Priority Journal", 8.0, year=2024, source="unique_base"),
                catalog_row("Priority Journal", 7.0, year=2023, source="legacy_crawler_supplement"),
                catalog_row("Priority Journal", 6.5, year=2022, source="manual_override"),
            ]
        )

        result = sync.resolve_article_if({"journal": "Priority Journal"}, index)

        self.assertEqual(result["impact_factor"], 6.5)
        self.assertEqual(result["impact_factor_source"], "manual_override")

    def test_newer_year_wins_within_same_source_priority(self):
        index = sync.build_letpub_if_index(
            [
                catalog_row("Annual Journal", 12.0, year=2023),
                catalog_row("Annual Journal", 7.0, year=2024),
            ]
        )

        result = sync.resolve_article_if({"journal": "Annual Journal"}, index)

        self.assertEqual(result["impact_factor"], 7.0)
        self.assertEqual(result["impact_factor_year"], 2024)

    def test_no_match_and_lookup_error_are_distinct_machine_states(self):
        empty_index = sync.build_letpub_if_index([])
        no_match = sync.resolve_article_if({"journal": "Missing Journal"}, empty_index)
        self.assertEqual(no_match["impact_factor_status"], "unresolved")
        self.assertEqual(no_match["impact_factor_reason"], "no_match")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-23-brainmri.json"
            path.write_text(
                json.dumps({"date": "2026-07-23", "articles": [{"journal": "Missing Journal"}]}),
                encoding="utf-8",
            )
            with patch.object(sync, "lookup_letpub_for_journal", side_effect=RuntimeError("network failed")):
                changed, _ = sync.process_data_file(**process_args(path, empty_index, crawl=True))
            article = json.loads(path.read_text(encoding="utf-8"))["articles"][0]

        self.assertEqual(changed, 1)
        self.assertEqual(article["impact_factor_status"], "lookup_error")
        self.assertEqual(article["impact_factor_reason"], "network_or_parse_error")

    def test_empty_journal_is_explicitly_unresolved(self):
        result = sync.resolve_article_if({"journal": ""}, sync.build_letpub_if_index([]))
        self.assertEqual(result["impact_factor_status"], "unresolved")
        self.assertEqual(result["impact_factor_reason"], "missing_journal")


class CatalogAndPersistenceTests(unittest.TestCase):
    def run_args(self, project_dir, file_name):
        return type(
            "Args",
            (),
            {
                "project_dir": str(project_dir),
                "files": [f"data/{file_name}"],
                "reference": "audit",
                "no_crawl": True,
                "retries": None,
                "journal": [],
                "journals_file": [],
                "timeout": 1,
                "workers": 1,
            },
        )()

    def make_project(self, root, article, *, raw_payload=None, reference_rows=None, manual_rows=None):
        data_dir = root / "data"
        letpub_dir = data_dir / "letpub"
        reference_dir = letpub_dir / "references"
        reference_dir.mkdir(parents=True)
        file_name = "2026-07-23-brainmri.json"
        (data_dir / file_name).write_text(
            json.dumps({"date": "2026-07-23", "articles": [article]}),
            encoding="utf-8",
        )
        (letpub_dir / "letpub_life_med_unique.json").write_text(
            json.dumps({"journals": []}), encoding="utf-8"
        )
        (letpub_dir / "letpub_life_med_raw.json").write_text(
            json.dumps(raw_payload if raw_payload is not None else {"rows": []}), encoding="utf-8"
        )
        (reference_dir / "audit.json").write_text(
            json.dumps({"journals": reference_rows or []}), encoding="utf-8"
        )
        if manual_rows is not None:
            (letpub_dir / "letpub_manual_overrides.json").write_text(
                json.dumps({"journals": manual_rows}), encoding="utf-8"
            )
        return data_dir / file_name

    def test_catalog_json_and_structure_errors_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            invalid_json = Path(tmp) / "invalid.json"
            invalid_json.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                sync.load_letpub_journal_list(invalid_json)

            invalid_structure = Path(tmp) / "invalid-structure.json"
            invalid_structure.write_text(json.dumps({"journals": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                sync.load_letpub_journal_list(invalid_structure)

        with self.assertRaises(ValueError):
            sync.build_letpub_if_index({})

    def test_run_fails_on_malformed_raw_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.make_project(root, {"journal": "Journal"})
            (root / "data" / "letpub" / "letpub_life_med_raw.json").write_text(
                "{", encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                sync.run(self.run_args(root, path.name))

    def test_run_excludes_reference_files_but_uses_persistent_manual_override(self):
        reference_row = catalog_row(
            "File Boundary Journal",
            12.0,
            source="letpub_unresolved_crawler",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.make_project(
                root,
                {"journal": "File Boundary Journal"},
                reference_rows=[reference_row],
            )
            sync.run(self.run_args(root, path.name))
            reference_only = json.loads(path.read_text(encoding="utf-8"))["articles"][0]
            self.assertEqual(reference_only["impact_factor_status"], "unresolved")
            self.assertEqual(reference_only["impact_factor_reason"], "no_match")

        manual_row = dict(reference_row, source="manual_override")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.make_project(
                root,
                {"journal": "File Boundary Journal"},
                reference_rows=[reference_row],
                manual_rows=[manual_row],
            )
            manual_path = root / "data" / "letpub" / "letpub_manual_overrides.json"
            sync.run(self.run_args(root, path.name))
            manually_enriched = json.loads(path.read_text(encoding="utf-8"))["articles"][0]

            self.assertEqual(manually_enriched["impact_factor"], 12.0)
            self.assertEqual(manually_enriched["impact_factor_source"], "manual_override")
            self.assertTrue(manual_path.exists())

    def test_apply_and_process_write_real_fields_atomically_and_report_true_changes(self):
        index = sync.build_letpub_if_index([catalog_row("Writeback Journal", 6.8)])
        original_article = {"title": "Kept", "journal": "Writeback Journal", "custom": 17}
        expected = sync.apply_if_result(
            original_article,
            sync.resolve_article_if(original_article, index),
        )
        self.assertEqual(original_article, {"title": "Kept", "journal": "Writeback Journal", "custom": 17})
        self.assertEqual(expected["impact_factor_status"], "available")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-23-brainmri.json"
            path.write_text(
                json.dumps({"date": "2026-07-23", "articles": [original_article]}, indent=2) + "\n",
                encoding="utf-8",
            )
            first_changed, _ = sync.process_data_file(**process_args(path, index))
            first_bytes = path.read_bytes()
            payload = json.loads(first_bytes)
            second_changed, _ = sync.process_data_file(**process_args(path, index))

            self.assertEqual(first_changed, 1)
            self.assertEqual(second_changed, 0)
            self.assertEqual(first_bytes, path.read_bytes())
            self.assertEqual(payload["articles"][0], expected)
            self.assertEqual(list(Path(tmp).glob(f".{path.name}.*.tmp")), [])

    def test_unresolved_registry_migrates_last_file_and_is_idempotent_per_file(self):
        unresolved = {
            "schema_version": 1,
            "updated_at": "fixed",
            "journals": {
                "Missing": {
                    "journal_name": "Missing",
                    "first_seen": "2026-07-20",
                    "last_seen": "2026-07-20",
                    "seen_count": 1,
                    "last_file": "2026-07-20-brainmri.json",
                }
            },
        }
        observed = {"Missing": {"journal_issn": "", "hit_count": 1, "manual_full_name": ""}}

        sync.update_unresolved_registry(unresolved, observed, set(), "2026-07-23", "2026-07-23-brainmri.json")
        first = json.dumps(unresolved, sort_keys=True)
        sync.update_unresolved_registry(unresolved, observed, set(), "2026-07-23", "2026-07-23-brainmri.json")

        entry = unresolved["journals"]["Missing"]
        self.assertNotIn("last_file", entry)
        self.assertEqual(entry["files"], ["2026-07-20-brainmri.json", "2026-07-23-brainmri.json"])
        self.assertEqual(entry["seen_count"], 2)
        self.assertEqual(json.dumps(unresolved, sort_keys=True), first)

    def test_manual_unresolved_retry_is_idempotent_and_migrates_files(self):
        unresolved = {
            "schema_version": 1,
            "updated_at": "fixed",
            "journals": {
                "Manual Missing": {
                    "journal_name": "Manual Missing",
                    "first_seen": "2026-07-20",
                    "last_seen": "2026-07-20",
                    "seen_count": 1,
                    "last_file": "2026-07-20-brainmri.json",
                }
            },
        }
        kwargs = {
            "specs": [
                {
                    "journal_name": "Manual Missing",
                    "journal_issn": "",
                    "manual_full_name": "Manual Missing",
                }
            ],
            "letpub_index": sync.build_letpub_if_index([]),
            "unresolved": unresolved,
            "supplement_payload": sync.default_supplement_payload(),
            "reference_payload": sync.default_reference_payload("audit"),
            "reference": "audit",
            "crawl_online": False,
            "timeout": 1,
            "workers": 1,
            "query_cache": {},
        }

        sync.process_manual_journal_specs(**kwargs)
        first = json.dumps(unresolved, sort_keys=True)
        sync.process_manual_journal_specs(**kwargs)

        entry = unresolved["journals"]["Manual Missing"]
        self.assertNotIn("last_file", entry)
        self.assertEqual(entry["files"], ["2026-07-20-brainmri.json"])
        self.assertEqual(entry["seen_count"], 1)
        self.assertEqual(json.dumps(unresolved, sort_keys=True), first)

    def test_default_file_collection_reads_sorted_unique_files_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            first = data_dir / "2026-07-20-brainmri.json"
            second = data_dir / "2026-07-23-brainmri.json"
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")
            unresolved = {
                "journals": {
                    "One": {"files": [second.name, first.name, second.name]},
                    "Two": {"files": [first.name]},
                }
            }

            collected = sync.collect_default_files(data_dir, unresolved)

        self.assertEqual([path.name for path in collected], [first.name, second.name])

    def test_online_confirmation_updates_manual_override_and_reference_audit(self):
        manual = sync.default_supplement_payload()
        reference = sync.default_reference_payload("audit")
        row = catalog_row(
            "Confirmed Journal",
            7.7,
            issn="1111-2222",
            source="letpub_online",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-07-23-brainmri.json"
            path.write_text(
                json.dumps({"date": "2026-07-23", "articles": [{"journal": "Confirmed Journal"}]}),
                encoding="utf-8",
            )
            with patch.object(sync, "lookup_letpub_for_journal", return_value=(row, "name:Confirmed Journal")):
                changed, supplement_changed = sync.process_data_file(
                    **process_args(
                        path,
                        sync.build_letpub_if_index([]),
                        manual=manual,
                        reference=reference,
                        crawl=True,
                    )
                )
            article = json.loads(path.read_text(encoding="utf-8"))["articles"][0]

        self.assertEqual(changed, 1)
        self.assertEqual(supplement_changed, 2)
        self.assertEqual(article["impact_factor"], 7.7)
        self.assertEqual(article["impact_factor_source"], "manual_override")
        self.assertEqual(len(manual["journals"]), 1)
        self.assertEqual(len(reference["journals"]), 1)
        self.assertEqual(reference["journals"][0]["audit_role"], "reference_only")

    def test_manual_override_created_from_local_fact_keeps_year_and_audit_role(self):
        manual = sync.default_supplement_payload()
        reference = sync.default_reference_payload("audit")
        unresolved = sync.default_unresolved_registry()
        found, updated, unresolved_added = sync.process_manual_journal_specs(
            specs=[
                {
                    "journal_name": "Local Journal",
                    "journal_issn": "1234-5678",
                    "manual_full_name": "Local Journal",
                }
            ],
            letpub_index=sync.build_letpub_if_index(
                [
                    catalog_row(
                        "Local Journal",
                        8.2,
                        issn="1234-5678",
                        year=2024,
                        source="unique_base",
                    )
                ]
            ),
            unresolved=unresolved,
            supplement_payload=manual,
            reference_payload=reference,
            reference="audit",
            crawl_online=False,
            timeout=1,
            workers=1,
            query_cache={},
        )

        self.assertEqual((found, updated, unresolved_added), (1, 2, 0))
        self.assertEqual(manual["journals"][0]["impact_factor_year"], 2024)
        self.assertEqual(reference["journals"][0]["audit_role"], "reference_only")

    def test_reference_only_rows_never_enter_fact_index(self):
        reference_row = catalog_row("Audit Journal", 12.0, source="reference_audit")
        index = sync.build_letpub_if_index([reference_row])
        result = sync.resolve_article_if({"journal": "Audit Journal"}, index)
        self.assertEqual(result["impact_factor_status"], "unresolved")
        self.assertEqual(result["impact_factor_reason"], "no_match")

        manual_row = dict(reference_row, source="manual_override")
        result = sync.resolve_article_if(
            {"journal": "Audit Journal"},
            sync.build_letpub_if_index([manual_row]),
        )
        self.assertEqual(result["impact_factor"], 12.0)
        self.assertEqual(result["impact_factor_source"], "manual_override")


if __name__ == "__main__":
    unittest.main()
