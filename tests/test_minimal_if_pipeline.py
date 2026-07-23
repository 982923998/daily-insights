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

    def test_filter_and_stage_aware_validator_helpers_are_blocking(self):
        self.assertIn('FILTER_IF_SCRIPT="$PROJECT_DIR/scripts/filter_impact_factor.py"', self.source)

        filter_body = function_body(self.source, "filter_impact_factors")
        self.assertIn('python3 "$FILTER_IF_SCRIPT" "$file" --minimum 6', filter_body)
        self.assertIn("return 1", filter_body)
        self.assertNotIn("non-blocking", filter_body)

        validator_body = function_body(self.source, "validate_data_file")
        self.assertIn('local stage="${3:-}"', validator_body)
        self.assertIn('--stage "$stage"', validator_body)
        self.assertIn("return 1", validator_body)

    def test_brain_mri_pipeline_runs_local_if_and_filter_once_before_split(self):
        academic_body = function_body(self.source, "run_academic_domain")
        self.assertLess(
            academic_body.index('validate_data_file "$data_file" "$domain_id"'),
            academic_body.index('if [ "$post_process" != "1" ]'),
        )

        pipeline = function_body(self.source, "run_mri_pipeline")
        sync_call = 'python3 "$SYNC_IF_SCRIPT" "$brainmri_file" --no-crawl'
        filter_call = 'filter_impact_factors "$brainmri_file"'
        final_validation = 'validate_data_file "$brainmri_file" "brainmri" "final"'
        split_call = "process_mri_split_outputs"

        self.assertEqual(pipeline.count(sync_call), 1)
        self.assertEqual(pipeline.count(filter_call), 1)
        self.assertIn('if ! sync_output=$(python3 "$SYNC_IF_SCRIPT" "$brainmri_file" --no-crawl', pipeline)
        self.assertIn('log "[ERROR] IF sync failed: $brainmri_file"', pipeline)
        self.assertIn("return 1", pipeline)
        self.assertLess(pipeline.index(sync_call), pipeline.index(filter_call))
        self.assertLess(pipeline.index(filter_call), pipeline.index(final_validation))
        self.assertLess(pipeline.index(final_validation), pipeline.index(split_call))

    def test_six_split_outputs_are_final_validated_and_digested_without_sync(self):
        split_body = function_body(self.source, "process_mri_split_outputs")

        self.assertIn("for domain_id in brainmri autism depression adhd ad pd; do", split_body)
        self.assertIn('validate_data_file "$data_file" "$domain_id" "final"', split_body)
        self.assertIn('generate_digest "$data_file" "$domain_id"', split_body)
        self.assertNotIn("sync_impact_factors", split_body)

    def test_mri_modes_skip_global_sync_and_explicit_if_command_remains(self):
        post_fetch = function_body(self.source, "run_post_fetch_if_sync")
        skip_case = post_fetch.split('if [ "$AUTO_IF_SYNC"', 1)[0]

        for mode in ("brainmri", "mri", "all", "autism", "depression", "adhd", "ad", "pd"):
            self.assertRegex(skip_case, rf"\b{mode}\b")
        self.assertIsNotNone(
            re.search(r"^    if\|journal-if\|impact-factor\)$", self.source, re.MULTILINE)
        )
        self.assertIn('python3 "$SYNC_IF_SCRIPT" "$@"', self.source)

    def test_mixed_domain_route_has_no_global_sync_after_mri_pipeline(self):
        main_case = self.source.split('case "$MODE" in', 1)[1]
        task_tail = main_case.rsplit("esac", 1)[1]

        self.assertIn('run_academic_domain "$domain_id" || exit $?', main_case)
        self.assertIn("needs_mri=1", main_case)
        self.assertIn("run_mri_pipeline || exit $?", main_case)
        self.assertNotIn("run_post_fetch_if_sync", task_tail)


if __name__ == "__main__":
    unittest.main()
