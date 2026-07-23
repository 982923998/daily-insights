import importlib.util
import unittest
from datetime import date
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "backfill_pubmed.py"


class BackfillPubmedTests(unittest.TestCase):
    def load_module(self):
        self.assertTrue(MODULE_PATH.exists(), "backfill_pubmed.py must exist")
        spec = importlib.util.spec_from_file_location("backfill_pubmed", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_parses_pubmed_xml_and_buckets_three_day_window(self):
        module = self.load_module()
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>123</PMID>
      <Article>
        <ArticleTitle>Brain <i>MRI</i> study</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">First section.</AbstractText>
          <AbstractText>Second section.</AbstractText>
        </Abstract>
        <Journal>
          <ISSN>1234-5678</ISSN>
          <ISOAbbreviation>J Brain MRI</ISOAbbreviation>
          <JournalIssue><PubDate><Year>2026</Year><Month>May</Month><Day>23</Day></PubDate></JournalIssue>
        </Journal>
        <ArticleDate><Year>2026</Year><Month>05</Month><Day>23</Day></ArticleDate>
      </Article>
    </MedlineCitation>
    <PubmedData><History><PubMedPubDate PubStatus="entrez"><Year>2026</Year><Month>05</Month><Day>24</Day></PubMedPubDate></History></PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""
        records = module.parse_pubmed_xml(xml)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Brain MRI study")
        self.assertEqual(records[0]["summary"], "BACKGROUND: First section. Second section.")
        self.assertEqual(records[0]["journal"], "J Brain MRI")
        self.assertEqual(records[0]["journal_issn"], "1234-5678")
        self.assertEqual(records[0]["published_date"], "2026-05-23")

        buckets = module.bucket_articles(records, date(2026, 5, 24), date(2026, 5, 26))
        self.assertEqual([item["url"] for item in buckets["2026-05-24"]], ["https://pubmed.ncbi.nlm.nih.gov/123/"])
        self.assertEqual([item["url"] for item in buckets["2026-05-25"]], ["https://pubmed.ncbi.nlm.nih.gov/123/"])
        self.assertEqual(buckets["2026-05-26"], [])
        self.assertNotIn("_created_date", buckets["2026-05-24"][0])
        self.assertEqual(buckets["2026-05-24"][0]["date"], "2026-05-24")


if __name__ == "__main__":
    unittest.main()
