import re
import subprocess
import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "web" / "index.html"


class FrontendTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_HTML.read_text(encoding="utf-8")

    def test_date_picker_is_removed_and_all_dates_are_loaded(self):
        self.assertNotIn('type="date"', self.source)
        self.assertNotIn("currentDate", self.source)
        self.assertIn("safeFetch('/api/dates')", self.source)
        self.assertRegex(self.source, r"`/data/\$\{date\}-\$\{domain\.id\}\.json")

    def test_timeline_is_sorted_newest_first(self):
        block = re.search(
            r"// --- Timeline Helpers Start ---\s*(.*?)\s*// --- Timeline Helpers End ---",
            self.source,
            re.DOTALL,
        ).group(1)
        script = f"""
const normalizeUrl = value => value || '';
{block}
const result = mergeTimelineFiles([
  {{requestDate: '2026-07-21', domainId: 'tms', payload: {{articles: [{{title: 'old'}}]}}}},
  {{requestDate: '2026-07-23', domainId: 'tms', payload: {{articles: [{{title: 'new'}}]}}}}
]).map(article => article.title);
process.stdout.write(JSON.stringify(result));
"""
        completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
        self.assertEqual(completed.stdout, '["new","old"]')

    def test_header_explains_sort_order(self):
        self.assertIn("Newest first", self.source)

    def test_articles_are_paginated_twenty_per_page(self):
        self.assertIn("const PAGE_SIZE = 20;", self.source)
        self.assertIn("const paginatedArticles = filteredArticles.slice(", self.source)
        self.assertIn("paginatedArticles.map", self.source)
        self.assertIn("第 {currentPage} / {totalPages} 页", self.source)


if __name__ == "__main__":
    unittest.main()
