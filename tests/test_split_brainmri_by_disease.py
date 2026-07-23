import json
import tempfile
import unittest
from pathlib import Path

from scripts.split_brainmri_by_disease import split_payload, write_split_files


def article(title, summary):
    return {
        "title": title,
        "summary": summary,
        "url": "https://pubmed.ncbi.nlm.nih.gov/" + str(abs(hash(title))) + "/",
        "category": "Brain MRI",
        "source": "pubmed",
        "journal": "Test Journal",
        "published_date": "2026-05-11",
        "date": "2026-05-12",
    }


class SplitBrainMriByDiseaseTests(unittest.TestCase):
    def test_copies_articles_to_every_matching_disease_and_leaves_unmatched_in_mri(self):
        payload = {
            "date": "2026-05-12",
            "articles": [
                article(
                    "Autism and Parkinson's disease network MRI study",
                    "ASD and Parkinson disease patients were examined with rs-fMRI.",
                ),
                article(
                    "Resting-state fMRI in major depressive disorder and ADHD",
                    "MDD and attention deficit symptoms were compared.",
                ),
                article(
                    "Amyloid and tau MRI biomarkers in Alzheimer disease",
                    "Dementia and Alzheimer-related pathology were analyzed.",
                ),
                article(
                    "General connectome mapping in healthy adults",
                    "No target disease is mentioned in this MRI article.",
                ),
            ],
        }

        result = split_payload(payload)

        self.assertEqual(
            [a["title"] for a in result["autism"]["articles"]],
            ["Autism and Parkinson's disease network MRI study"],
        )
        self.assertEqual(
            [a["title"] for a in result["pd"]["articles"]],
            ["Autism and Parkinson's disease network MRI study"],
        )
        self.assertEqual(
            [a["title"] for a in result["depression"]["articles"]],
            ["Resting-state fMRI in major depressive disorder and ADHD"],
        )
        self.assertEqual(
            [a["title"] for a in result["adhd"]["articles"]],
            ["Resting-state fMRI in major depressive disorder and ADHD"],
        )
        self.assertEqual(
            [a["title"] for a in result["ad"]["articles"]],
            ["Amyloid and tau MRI biomarkers in Alzheimer disease"],
        )
        self.assertEqual(
            [a["title"] for a in result["brainmri"]["articles"]],
            ["General connectome mapping in healthy adults"],
        )

    def test_write_split_files_uses_domain_categories(self):
        payload = {
            "date": "2026-05-12",
            "articles": [
                article("ADHD MRI study", "Attention-deficit hyperactivity disorder."),
                article("General brain MRI study", "Healthy adult connectome mapping."),
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "2026-05-12-brainmri.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            counts = write_split_files(input_path, Path(tmp))

            self.assertEqual(counts["adhd"], 1)
            self.assertEqual(counts["brainmri"], 1)
            adhd_payload = json.loads((Path(tmp) / "2026-05-12-adhd.json").read_text(encoding="utf-8"))
            mri_payload = json.loads((Path(tmp) / "2026-05-12-brainmri.json").read_text(encoding="utf-8"))
            self.assertEqual(adhd_payload["articles"][0]["category"], "ADHD")
            self.assertEqual(mri_payload["articles"][0]["category"], "Brain MRI")


if __name__ == "__main__":
    unittest.main()
