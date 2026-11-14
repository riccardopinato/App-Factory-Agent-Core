"""Pinned-source MCP integration across GitHub, GBrain, AppLab and owner gate.

All HTTP and memory provider responses are **synthetic**. Uses real pinned
production modules, a temporary AppLab SQLiteShadowStore, and the official
in-process MCP SDK client. No public listener, owner PC, live queue or API.
"""
import importlib.util
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.factory_readonly_gateway import FactoryReadOnlyGateway
from scripts.factory_status_v02 import FactoryEvidenceGateway
from scripts.factory_github_connector_reader import GitHubConnectorHeadReader
from scripts.factory_github_evidence_reader import GitHubEvidenceConnector
from scripts.factory_mcp_readonly import ReadOnlyFactoryTools, build_mcp_server
from scripts.factory_mcp_memory_context import FactoryMemoryContext
from scripts.factory_mcp_runtime_gate import FactoryRuntimeGate

REPO = "riccardopinato/AppLab"
SHA = "b" * 40
BASE = "a" * 40
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
GBRAIN = os.environ.get("GBRAIN_PROJECTION_CHECKOUT")
APPLAB = os.environ.get("APPLAB_CHECKOUT")


def real_projector():
    source = Path(GBRAIN) / "scripts/gbrain_memory_adapter.py"
    spec = importlib.util.spec_from_file_location("gbrain_projector_e2e_pinned", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.project_recall


def real_store():
    root = Path(APPLAB)
    sys.path.insert(0, str(root / "scripts"))
    from durable_store_v54b import SQLiteShadowStore
    from durable_brain_v54a import operation_queue_key, operation_idempotency_key
    return SQLiteShadowStore, operation_queue_key, operation_idempotency_key


class FakeGithubConnector:
    def __init__(self):
        self.requests = []

    def __call__(self, url):
        self.requests.append(url)
        if url.endswith("/branches/main"):
            result = {"name": "main", "commit": {"sha": SHA}}
        elif url.endswith("/pulls/27"):
            result = {"number": 27, "draft": False, "state": "open",
                      "head": {"sha": SHA},
                      "base": {"sha": BASE, "repo": {"full_name": REPO}}}
        elif "/actions/runs?head_sha=" in url:
            result = {"total_count": 1, "workflow_runs": [
                {"id": 9, "name": "Gateway — pinned source suite",
                 "status": "completed", "conclusion": "success", "head_sha": SHA}]}
        else:
            raise AssertionError("unexpected GitHub request: " + url)
        return {"result": {"content": json.dumps(result)}}


try:
    from mcp.client import Client
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False


@unittest.skipUnless(GBRAIN and APPLAB and HAVE_SDK, "Pinned integrations require both upstream checkouts + MCP SDK")
class FullReadOnlyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_four_source_tools_and_denial_with_pinned_real_modules(self):
        Store, queue_key, idempotency_key = real_store()
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp) / "applab-test.sqlite3") as store:
                operation = {
                    "schema_version": 1, "record_type": "APPLAB_OPERATION",
                    "operation_id": "op_pinnedread", "correlation_id": "cor_pinnedread",
                    "operation_class": "VERIFICATION", "analysis_mode": "fast",
                    "repository": REPO, "source_ref": "main",
                    "resolved_sha": SHA, "applab_sha": BASE,
                    "state": "QUEUED", "priority": 100,
                    "authority": "ORCHESTRATION_ONLY",
                    "non_exported_payload": "SENSITIVE_DO_NOT_INCLUDE",
                }
                operation["queue_key"] = queue_key(operation)
                operation["idempotency_key"] = idempotency_key(operation)
                self.assertEqual(store.put_operation(operation)["status"], "INSERTED")
                fake = FakeGithubConnector()
                gh = GitHubConnectorHeadReader(
                    trusted_fetch=fake, branches={REPO: "main"}, now=lambda: NOW)
                evidence = GitHubEvidenceConnector(
                    trusted_fetch=fake, allowed_repositories={REPO}, now=lambda: NOW)
                gateway = FactoryEvidenceGateway(
                    allowed_repositories=[REPO], github_head_reader=gh,
                    applab_store=store,
                    trusted_pr_reader=evidence.read_pr,
                    trusted_ci_reader=evidence.read_ci,
                )

                identity = {
                    "principal_id": "owner:test",
                    "host_verified": True,
                    "scopes": frozenset({"factory:read"}),
                    "expires_at": NOW + timedelta(minutes=5),
                }
                gate = FactoryRuntimeGate(
                    trusted_identity_provider=lambda: identity,
                    max_calls_per_minute=4,
                    utc_now=lambda: NOW,
                    clock=lambda: 10.0,
                )
                owner = ReadOnlyFactoryTools(
                    gateway=gateway, trusted_owner_authorizer=gate.authorize)
                recall = {"text": json.dumps({
                    "protocol_version": 1,
                    "search_degraded": "keyword_only_embedding_disabled",
                    "facts": [
                        {"fact": "App Factory source status", "source_id": "default",
                         "fact_id": "1", "trust_tier": "tool_observed",
                         "visibility": "world", "valid_until": None,
                         "expired_at": None, "superseded_by": None},
                        {"fact": "token github_pat_" + "x" * 40,
                         "source_id": "default", "fact_id": "2",
                         "trust_tier": "tool_observed", "visibility": "world"},
                        {"fact": "unverified", "source_id": "default", "fact_id": "3",
                         "trust_tier": "agent_written", "visibility": "world"},
                    ],
                })}
                memory = FactoryMemoryContext(
                    owner_bound_service=owner,
                    trusted_gbrain_recall=lambda *, query, budget_tokens: recall,
                    pinned_projection=real_projector(),
                )
                mcp = build_mcp_server(owner, memory_context=memory)
                async with Client(mcp) as client:
                    available = await client.list_tools()
                    self.assertEqual(len(available.tools), 4)
                    r = await client.call_tool(
                        "factory_repository_status", {"repository": REPO})
                    self.assertFalse(r.is_error)
                    self.assertIn(SHA, str(r))
                    r = await client.call_tool(
                        "factory_pr_evidence", {
                            "repository": REPO, "pr_number": 27,
                            "expected_head_sha": SHA})
                    self.assertFalse(r.is_error)
                    self.assertIn("ALL_OBSERVED_CHECKS_SUCCESS", str(r))
                    self.assertIn("review_verified", str(r))
                    r = await client.call_tool(
                        "factory_operation_checkpoint", {
                            "repository": REPO, "operation_id": "op_pinnedread",
                            "source_sha": SHA})
                    self.assertFalse(r.is_error)
                    self.assertIn("QUEUED", str(r))
                    self.assertNotIn("SENSITIVE_DO_NOT_INCLUDE", str(r))
                    r = await client.call_tool(
                        "factory_memory_context", {"query": "App Factory"})
                    self.assertFalse(r.is_error)
                    self.assertIn("CONTEXT_ONLY", str(r))
                    self.assertNotIn("github_pat_", str(r))
                    self.assertIn("KEYWORD_ONLY_DEGRADED", str(r))

                    # The fifth authorized read attempt must be denied by
                    # the per-principal host-bound process-local budget.
                    denied = await client.call_tool(
                        "factory_repository_status", {"repository": REPO})
                    self.assertTrue(denied.is_error)

                self.assertEqual(store.get_operation("op_pinnedread")["current_state"], "QUEUED")
                self.assertEqual(len(fake.requests), 3)


if __name__ == "__main__":
    unittest.main()
