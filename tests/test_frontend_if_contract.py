import re
import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "web" / "index.html"


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^        const {re.escape(name)} = (.*?)(?=^        const |\Z)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError(f"function not found: {name}")
    return match.group(1)


class FrontendIfContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_HTML.read_text(encoding="utf-8")

    def test_frontend_has_no_letpub_catalog_request_or_index(self):
        self.assertNotIn("/data/letpub/", self.source)
        self.assertNotIn("letpubIndex", self.source)

    def test_letpub_index_building_helpers_are_removed(self):
        for symbol in (
            "normalizeJournalKey",
            "normalizeIssn",
            "extractLetpubRows",
            "buildLetpubIndex",
        ):
            self.assertNotIn(symbol, self.source)

    def test_if_helper_reads_article_fields_without_translating_status(self):
        self.assertIn("const getIfInfoForArticle = (article = {})", self.source)
        body = function_body(self.source, "getIfInfoForArticle")
        self.assertRegex(body, r"article\??\.impact_factor\s*\?\?\s*null")
        self.assertRegex(body, r"article\??\.impact_factor_year\s*\?\?\s*null")
        self.assertRegex(body, r"article\??\.impact_factor_status\s*\?\?\s*null")
        self.assertNotRegex(body, r"已收录影响因子|尚无影响因子|未查到影响因子")

    def test_cards_use_direct_if_helper_without_index_props(self):
        self.assertIn(
            "const ifInfo = getIfInfoForArticle(matchedArticle);",
            self.source,
        )
        self.assertIn(
            "const ifInfo = getIfInfoForArticle(article);",
            self.source,
        )

    def test_ai_articles_hide_impact_factor_badges(self):
        digest_body = function_body(self.source, "DigestPanel")
        self.assertIn("const isAiArticle =", digest_body)
        self.assertIn("const showImpactBadge = !isAiArticle;", digest_body)
        self.assertIn("{showImpactBadge && (", digest_body)

        card_body = function_body(self.source, "NewsCard")
        self.assertIn("const isAiArticle =", card_body)
        self.assertIn("const showImpact = !isAiArticle;", card_body)
        self.assertIn("{showImpact && (", card_body)


if __name__ == "__main__":
    unittest.main()
