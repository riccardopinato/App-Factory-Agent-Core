"""Quality diagnostics never promote GBrain context or reveal private text."""
import unittest
from scripts.gbrain_recall_quality import RecallQualityError, evaluate_recall_quality


def projection(facts=None, mode="KEYWORD_ONLY_DEGRADED"):
    return {
        "record_type": "GBRAIN_RECALL_PROJECTION",
        "authority": "CONTEXT_ONLY", "read_only": True, "absence_proven": False,
        "search_mode": mode,
        "facts": facts if facts is not None else [
            {"text": "Stato App Factory e repository", "untrusted_context": True,
             "verified_by_factory": False, "source_id": "default", "fact_id": "1"}
        ],
    }


class QualityTests(unittest.TestCase):
    def test_degraded_search_hint_never_certifies(self):
        result = evaluate_recall_quality("app factory", projection())
        self.assertEqual(result["lexical_overlap_count"], 1)
        self.assertEqual(result["recommended_action"], "REVIEW_DEGRADED_SEARCH")
        self.assertFalse(result["semantic_search_verified"])
        self.assertFalse(result["fact_truth_verified"])
        self.assertFalse(result["absence_proven"])
        self.assertNotIn("Stato App Factory", str(result))

    def test_empty_recall_never_proves_absence(self):
        result = evaluate_recall_quality("Notes", projection([]))
        self.assertEqual(result["admitted_fact_count"], 0)
        self.assertFalse(result["memory_complete"])
        self.assertFalse(result["absence_proven"])

    def test_accent_fold_and_cross_language_uncertainty(self):
        result = evaluate_recall_quality("certificazióne", projection([
            {"text": "certificazione non verificata", "untrusted_context": True,
             "verified_by_factory": False}
        ], mode="SOURCE_REPORTED"))
        self.assertEqual(result["lexical_overlap_count"], 1)
        self.assertFalse(result["relevance_verified"])

    def test_untrusted_projection_denied(self):
        with self.assertRaisesRegex(RecallQualityError, "UNTRUSTED_RECALL_PROJECTION"):
            evaluate_recall_quality("foo", {**projection(), "authority": "APPROVE"})
        with self.assertRaisesRegex(RecallQualityError, "UNTRUSTED_FACT"):
            evaluate_recall_quality("foo", projection([
                {"text": "foo", "untrusted_context": False,
                 "verified_by_factory": True}
            ]))
        with self.assertRaisesRegex(RecallQualityError, "UNTRUSTED_SEARCH_MODE"):
            evaluate_recall_quality("foo", projection([], mode="CERTIFIED"))

    def test_query_credentials_never_appear_in_report(self):
        q = "ghp_" + "a" * 32
        result = evaluate_recall_quality(q, projection([]))
        self.assertNotIn(q, str(result))

    def test_query_limits_and_bounded_facts(self):
        for bad in ("", "   ", "a" * 161, "abc\nmore"):
            with self.assertRaisesRegex(RecallQualityError, "INVALID_QUERY"):
                evaluate_recall_quality(bad, projection())
        with self.assertRaisesRegex(RecallQualityError, "INVALID_FACT_SET"):
            evaluate_recall_quality("test", projection([
                {"text": "x", "untrusted_context": True, "verified_by_factory": False}
            ] * 33))


if __name__ == "__main__":
    unittest.main()
