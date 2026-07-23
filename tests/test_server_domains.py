import tempfile
import unittest
from pathlib import Path

import scripts.server as server


class FakeProcess:
    def __init__(self, return_code):
        self.return_code = return_code

    def poll(self):
        return self.return_code


class ServerDomainTests(unittest.TestCase):
    def test_fetch_modes_match_active_domains(self):
        self.assertEqual(server.ALLOWED_FETCH_MODES, {"all", "autism", "depression", "tms"})

    def test_all_fetch_modes_share_one_process_gate(self):
        original = server.active_processes
        try:
            server.active_processes = {"fetch_autism": FakeProcess(None)}
            self.assertTrue(server.has_active_fetch())
            server.active_processes = {"fetch_autism": FakeProcess(0)}
            self.assertFalse(server.has_active_fetch())
        finally:
            server.active_processes = original

    def test_load_domains_returns_only_ordered_active_domains(self):
        original_data_dir = server.DATA_DIR
        original_sources_dir = server.ACADEMIC_SOURCES_DIR

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            sources_dir = tmp_path / "sources"
            data_dir.mkdir()
            sources_dir.mkdir()

            (data_dir / "2026-05-12-brainmri.json").write_text("{}", encoding="utf-8")
            (data_dir / "2026-05-12-adhd.json").write_text("{}", encoding="utf-8")
            for order, domain_id in enumerate(("autism", "depression", "tms"), start=1):
                (sources_dir / f"{domain_id}.md").write_text(
                    "---\n"
                    f"id: {domain_id}\n"
                    f"label: {domain_id.title()}\n"
                    f"category: {domain_id.title()}\n"
                    "color: \"#0ea5e9\"\n"
                    "icon: activity\n"
                    "skill: academic-search\n"
                    f"order: {order}\n"
                    "---\n",
                    encoding="utf-8",
                )
            try:
                server.DATA_DIR = str(data_dir)
                server.ACADEMIC_SOURCES_DIR = str(sources_dir)

                domains = server.load_domains()
            finally:
                server.DATA_DIR = original_data_dir
                server.ACADEMIC_SOURCES_DIR = original_sources_dir

        self.assertEqual([domain["id"] for domain in domains], ["autism", "depression", "tms"])
        for domain in domains:
            self.assertTrue({"id", "label", "category", "color", "icon", "skill", "order"} <= set(domain))


if __name__ == "__main__":
    unittest.main()
