"""Actual source-pinned GBrain projector integration, opt-in CI only.

No live GBrain connector, private memory, network or local PC operations.
"""
import importlib.util
import json
import os
from pathlib import Path
import unittest

from scripts.factory_mcp_readonly import ReadOnlyFactoryTools
from scripts.factory_mcp_memory_context import FactoryMemoryContext

ROOT = os.environ.get("GBRAIN_PROJECTION_CHECKOUT")


class Gateway:
    def repository_status(self, repo): return {"repository": repo}
    def pull_request_evidence(self, repo, num, *, expected_head_sha):
        return {"pr_number": num}
    def operation_checkpoint(self, op, *, repository, source_sha):
        return {"operation_id": op}


@unittest.skipUnless(ROOT, "pinned real GBrain projector not provided")
class PinnedGBrainProjectorTests(unittest.TestCase):
    def test_real_projector_filters_credentials_and_weak_facts(self):
        source = Path(ROOT) / "scripts" / "gbrain_memory_adapter.py"
        self.assertTrue(source.is_file())
        spec = importlib.util.spec_from_file_location("gbrain_memory_adapter_pinned", source)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        facts = [
            {"fact": "Reusable donor requires evidence", "source_id": "default",
             "fact_id": "1", "trust_tier": "tool_observed", "visibility": "world",
             "valid_until": None, "expired_at": None, "superseded_by": None},
            {"fact": "another phrase", "source_id": "ghp_" + "a" * 24,
             "fact_id": "2", "trust_tier": "tool_observed", "visibility": "world"},
            {"fact": "agent's unverifiable claim", "source_id": "default",
             "fact_id": "3", "trust_tier": "agent_written", "visibility": "world"},
        ]
        response = {"text": json.dumps({
            "protocol_version": 1, "facts": facts,
            "search_degraded": "keyword_only_embedding_disabled",
        })}
        owner = ReadOnlyFactoryTools(
            gateway=Gateway(), trusted_owner_authorizer=lambda: True)
        tool = FactoryMemoryContext(
            owner_bound_service=owner,
            trusted_gbrain_recall=lambda *, query, budget_tokens: response,
            pinned_projection=module.project_recall)
        result = tool.recall_context("donor")
        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(result["facts"][0]["text"], "Reusable donor requires evidence")
        self.assertEqual(result["search_mode"], "KEYWORD_ONLY_DEGRADED")
        self.assertFalse(result["absence_proven"])
        self.assertFalse(result["job_authorized"])
        self.assertNotIn("ghp_", str(result))


if __name__ == "__main__":
    unittest.main()
