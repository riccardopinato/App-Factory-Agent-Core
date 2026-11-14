"""Optional MCP GBrain context tool contract and refusal tests."""
import unittest
from scripts.factory_mcp_memory_context import FactoryMemoryContext, MemoryBridgeError
from scripts.factory_mcp_readonly import ReadOnlyFactoryTools, FactoryMcpAccessError, build_mcp_server

REPO = "riccardopinato/AppLab"


class Gateway:
    def repository_status(self, repo): return {"repository": repo}
    def pull_request_evidence(self, repo, number, *, expected_head_sha):
        return {"pr": number}
    def operation_checkpoint(self, op, *, repository, source_sha):
        return {"operation_id": op}


def projection(_resp, *, max_facts):
    return {
        "schema_version": 1, "record_type": "GBRAIN_RECALL_PROJECTION",
        "authority": "CONTEXT_ONLY", "read_only": True,
        "search_mode": "KEYWORD_ONLY_DEGRADED", "absence_proven": False,
        "facts": [{
            "text": "Test fact, never instructions", "source_id": "default",
            "fact_id": "1", "visibility": "world",
            "untrusted_context": True, "verified_by_factory": False,
        }],
    }


class MemoryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.allowed = True
        self.owner = ReadOnlyFactoryTools(
            gateway=Gateway(),
            trusted_owner_authorizer=lambda: self.allowed,
        )
        def read(*, query, budget_tokens):
            self.calls.append((query, budget_tokens))
            return {"text": "opaque"}
        self.reader = read
        self.memory = FactoryMemoryContext(
            owner_bound_service=self.owner, trusted_gbrain_recall=self.reader,
            pinned_projection=projection)

    def test_context_is_read_only_and_never_grants_job(self):
        out = self.memory.recall_context("App Factory")
        self.assertEqual(out["record_type"], "FACTORY_MEMORY_CONTEXT")
        self.assertEqual(out["authority"], "CONTEXT_ONLY")
        self.assertEqual(out["facts"][0]["source_id"], "default")
        self.assertTrue(out["facts"][0]["untrusted_context"])
        self.assertFalse(out["certification_granted"])
        self.assertFalse(out["job_authorized"])
        self.assertEqual(self.calls, [("App Factory", 1000)])

    def test_owner_denied_before_any_gbrain_access(self):
        self.allowed = False
        with self.assertRaisesRegex(FactoryMcpAccessError, "ACCESS_DENIED"):
            self.memory.recall_context("App Factory")
        self.assertEqual(self.calls, [])

    def test_reject_unbounded_query_and_control_characters(self):
        for q in ("", " " * 3, "x" * 161, "abc\nwork"):
            with self.subTest(q=q[:20]):
                with self.assertRaisesRegex(MemoryBridgeError, "INVALID_MEMORY_QUERY"):
                    self.memory.recall_context(q)
        self.assertEqual(self.calls, [])

    def test_false_projection_authority_cannot_pass(self):
        def unsafe(_resp, *, max_facts):
            return {**projection(_resp, max_facts=max_facts), "authority": "JOB_ALLOWED"}
        bad = FactoryMemoryContext(
            owner_bound_service=self.owner, trusted_gbrain_recall=self.reader,
            pinned_projection=unsafe)
        with self.assertRaisesRegex(MemoryBridgeError, "PROJECTION_UNTRUSTED"):
            bad.recall_context("App Factory")

    def test_hidden_private_records_never_leave_bridge(self):
        def unsafe(_resp, *, max_facts):
            result = projection(_resp, max_facts=max_facts)
            result["facts"][0]["visibility"] = "private"
            return result
        bad = FactoryMemoryContext(
            owner_bound_service=self.owner, trusted_gbrain_recall=self.reader,
            pinned_projection=unsafe)
        with self.assertRaisesRegex(MemoryBridgeError, "PROJECTION_UNTRUSTED"):
            bad.recall_context("App Factory")

    def test_provider_error_is_sanitized(self):
        def leak(**_kwargs):
            raise ValueError("SECRET_USER_DATA")
        bad = FactoryMemoryContext(
            owner_bound_service=self.owner, trusted_gbrain_recall=leak,
            pinned_projection=projection)
        with self.assertRaisesRegex(MemoryBridgeError, "GBRAIN_READ_UNAVAILABLE") as cm:
            bad.recall_context("App Factory")
        self.assertNotIn("SECRET_USER_DATA", str(cm.exception))


try:
    from mcp.client import Client
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False


@unittest.skipUnless(HAVE_SDK, "official MCP SDK not installed in normal CI")
class MemoryMcpInProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_tool_only_appears_when_trusted_host_binds_it(self):
        owner = ReadOnlyFactoryTools(
            gateway=Gateway(), trusted_owner_authorizer=lambda: True)
        memory = FactoryMemoryContext(
            owner_bound_service=owner,
            trusted_gbrain_recall=lambda *, query, budget_tokens: {"text": "opaque"},
            pinned_projection=projection)
        mcp = build_mcp_server(owner, memory_context=memory)
        async with Client(mcp) as client:
            listing = await client.list_tools()
            self.assertIn("factory_memory_context", [t.name for t in listing.tools])
            out = await client.call_tool(
                "factory_memory_context", {"query": "App Factory"})
            self.assertFalse(out.is_error)
            self.assertIn("CONTEXT_ONLY", str(out))
            self.assertIn("untrusted_context", str(out))
            self.assertNotIn("JOB_ALLOWED", str(out))


if __name__ == "__main__":
    unittest.main()
