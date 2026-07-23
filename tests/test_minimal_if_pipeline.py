import re
import unittest
from pathlib import Path


FETCH_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch.sh"


def function_body(source: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}\(\) \{{\n(.*?)^\}}$", source, re.MULTILINE | re.DOTALL)
    if not match:
        raise AssertionError(f"function not found: {name}")
    return match.group(1)


class MinimalIfPipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FETCH_SCRIPT.read_text(encoding="utf-8")

    def test_only_three_active_domains_are_declared(self):
        self.assertIn('ACTIVE_DOMAINS=(autism depression tms)', self.source)
        self.assertIn('MODE="${1:-all}"', self.source)

    def test_domain_fetch_is_raw_and_batch_syncs_once_before_finalization(self):
        academic_body = function_body(self.source, "run_academic_domain")
        self.assertIn('validate_data_file "$data_file" "$domain_id"', academic_body)
        self.assertNotIn("sync_impact", academic_body)
        self.assertNotIn("generate_digest", academic_body)

        batch_body = function_body(self.source, "run_domain_batch")
        sync_call = 'python3 "$SYNC_IF_SCRIPT" "${successful_files[@]}" --reference auto-unresolved'
        self.assertEqual(batch_body.count(sync_call), 1)
        self.assertLess(batch_body.index(sync_call), batch_body.index('filter_impact_factors "$data_file"'))
        self.assertLess(
            batch_body.index('filter_impact_factors "$data_file"'),
            batch_body.index('generate_digest "$data_file" "$domain_id"'),
        )
        self.assertLess(
            batch_body.index('generate_digest "$data_file" "$domain_id"'),
            batch_body.index('validate_data_file "$data_file" "$domain_id" "final"'),
        )
        self.assertIn("failed_stages", batch_body)

    def test_filter_and_final_validator_use_if_8(self):
        filter_body = function_body(self.source, "filter_impact_factors")
        self.assertIn('python3 "$FILTER_IF_SCRIPT" "$file" --minimum 8', filter_body)
        validator_body = function_body(self.source, "validate_data_file")
        self.assertIn('--minimum-impact-factor 8', validator_body)

    def test_retired_modes_are_rejected_and_explicit_if_command_remains(self):
        main_case = self.source.split('case "$MODE" in', 1)[1]
        self.assertIn("brainmri|mri|adhd|ad|pd|mefmri|ai)", main_case)
        self.assertIn('run_domain_batch "${ACTIVE_DOMAINS[@]}"', main_case)
        self.assertIn('autism|depression|tms)', main_case)
        self.assertIn('run_domain_batch "$MODE"', main_case)
        self.assertIn('python3 "$SYNC_IF_SCRIPT" "$@"', main_case)
        self.assertNotIn("journal-if|impact-factor", main_case)

    def test_test_mode_is_offline_and_writes_all_three_domains(self):
        body = function_body(self.source, "run_test_mode")
        self.assertIn('for domain_id in "${ACTIVE_DOMAINS[@]}"', body)
        self.assertIn('"impact_factor": 8.0', body)
        self.assertIn("mktemp -d", body)
        self.assertNotIn('$PROJECT_DIR/data/', body)
        self.assertNotIn("run_codex", body)
        self.assertNotIn("sync_impact", body)
        test_case = self.source.split('    test)', 1)[1].split('        ;;', 1)[0]
        self.assertIn('AUTO_GIT_SYNC=0', test_case)


if __name__ == "__main__":
    unittest.main()
