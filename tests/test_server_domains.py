import tempfile
import unittest
from pathlib import Path

import scripts.server as server


class ServerDomainTests(unittest.TestCase):
    def test_load_domains_hides_disabled_domains_even_when_historical_data_exists(self):
        original_data_dir = server.DATA_DIR
        original_sources_dir = server.ACADEMIC_SOURCES_DIR
        original_skills_dir = server.SKILLS_DIR

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "data"
            sources_dir = tmp_path / "sources"
            skills_dir = tmp_path / "skills"
            data_dir.mkdir()
            sources_dir.mkdir()
            (skills_dir / "daily-ai-news").mkdir(parents=True)

            (data_dir / "2026-05-12-ai.json").write_text("{}", encoding="utf-8")
            (data_dir / "2026-05-12-brainmri.json").write_text("{}", encoding="utf-8")
            (data_dir / "2026-05-12-mefmri.json").write_text("{}", encoding="utf-8")
            (sources_dir / "brainmri.md").write_text(
                "---\n"
                "id: brainmri\n"
                "label: Brain MRI\n"
                "category: Brain MRI\n"
                "color: \"#0ea5e9\"\n"
                "icon: crosshair\n"
                "skill: academic-search\n"
                "order: 8\n"
                "---\n",
                encoding="utf-8",
            )
            (sources_dir / "mefmri.md").write_text(
                "---\n"
                "id: mefmri\n"
                "label: Multi-Echo fMRI\n"
                "category: Multi-Echo fMRI\n"
                "skill: academic-search\n"
                "order: 7\n"
                "---\n",
                encoding="utf-8",
            )
            (skills_dir / "daily-ai-news" / "SKILL.md").write_text(
                "---\n"
                "name: daily-ai-news\n"
                "domain_id: ai\n"
                "domain_label: AI News\n"
                "---\n",
                encoding="utf-8",
            )

            try:
                server.DATA_DIR = str(data_dir)
                server.ACADEMIC_SOURCES_DIR = str(sources_dir)
                server.SKILLS_DIR = str(skills_dir)

                domains = server.load_domains()
            finally:
                server.DATA_DIR = original_data_dir
                server.ACADEMIC_SOURCES_DIR = original_sources_dir
                server.SKILLS_DIR = original_skills_dir

        ids = [domain["id"] for domain in domains]
        self.assertIn("brainmri", ids)
        self.assertNotIn("ai", ids)
        self.assertNotIn("mefmri", ids)


if __name__ == "__main__":
    unittest.main()
