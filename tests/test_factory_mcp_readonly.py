"""MCP owner gate contract tests; optional official SDK in-process integration."""
import unittest

from scripts.factory_mcp_readonly import (
    FactoryMcpAccessError, ReadOnlyFactoryTools, build_mcp_server,
)

REPO = "riccardopinato/AppLab"
SHA = "a" * 40


class Gateway:
    def __init__(self):
        self.calls = []
    def repository_status(self, repo):
        self.calls.append(("repo", repo))
        return {"repository": repo, "head_sha": SHA, "read_only": True,
                "ci_verified": False}
    def pull_request_evidence(self, repo, num, *, expected_head_sha):
        self.calls.append(("pr", repo, num, expected_head_sha))
        return {"repository": repo, "pr_number": num, "head_sha": expected_head_sha,
                "ci_state": "NO_CHECKS_OBSERVED", "review_verified": False}
    def operation_checkpoint(self, op, *, repository, source_sha):
        self.calls.append(("op", repository, op, source_sha))
        return {"operation_id": op, "repository": repository, "source_sha": source_sha,
                "next_action_authorized": False}


class ToolServiceTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Gateway()

    def test_auth_gate_precedes_all_provider_calls(self):
        service = ReadOnlyFactoryTools(
            gateway=self.gateway, trusted_owner_authorizer=lambda: False)
        for fn in [
            lambda: service.repository_status(REPO),
            lambda: service.pr_evidence(REPO, 27, SHA),
            lambda: service.operation_checkpoint(REPO, "op-1", SHA),
        ]:
            with self.assertRaisesRegex(FactoryMcpAccessError, "ACCESS_DENIED"):
                fn()
        self.assertEqual(self.gateway.calls, [])

    def test_host_authorizer_exception_is_sanitized(self):
        def deny():
            raise ValueError("oauth access token private")
        service = ReadOnlyFactoryTools(
            gateway=self.gateway, trusted_owner_authorizer=deny)
        with self.assertRaisesRegex(FactoryMcpAccessError, "ACCESS_DENIED") as cm:
            service.repository_status(REPO)
        self.assertNotIn("oauth access token", str(cm.exception))

    def test_allowed_read_calls_only_existing_backend(self):
        service = ReadOnlyFactoryTools(
            gateway=self.gateway, trusted_owner_authorizer=lambda: True)
        self.assertEqual(service.repository_status(REPO)["ci_verified"], False)
        self.assertFalse(service.pr_evidence(REPO, 27, SHA)["review_verified"])
        self.assertFalse(service.operation_checkpoint(REPO, "op-1", SHA)["next_action_authorized"])
        self.assertEqual(len(self.gateway.calls), 3)
        for prohibited in ("enqueue", "execute", "merge", "shell", "write"):
            self.assertFalse(hasattr(service, prohibited))

    def test_no_unbound_service(self):
        with self.assertRaisesRegex(FactoryMcpAccessError, "READONLY_GATEWAY_NOT_BOUND"):
            ReadOnlyFactoryTools(gateway=object(), trusted_owner_authorizer=lambda: True)
        with self.assertRaisesRegex(FactoryMcpAccessError, "TRUSTED_OWNER_AUTHORIZER_REQUIRED"):
            ReadOnlyFactoryTools(gateway=self.gateway, trusted_owner_authorizer=None)


try:
    from mcp.client import Client
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False


@unittest.skipUnless(HAVE_SDK, "MCP SDK v2 not installed; separate pinned-SDK workflow required")
class McpSdkInProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_and_three_tools_with_official_sdk(self):
        service = ReadOnlyFactoryTools(
            gateway=Gateway(), trusted_owner_authorizer=lambda: True)
        mcp = build_mcp_server(service)
        async with Client(mcp) as client:
            listing = await client.list_tools()
            names = {tool.name for tool in listing.tools}
            self.assertEqual(names, {
                "factory_repository_status",
                "factory_pr_evidence",
                "factory_operation_checkpoint",
            })
            for t in listing.tools:
                schema_text = str(t.input_schema)
                self.assertNotIn("trusted_owner_authorizer", schema_text)
                self.assertNotIn("api_key", schema_text)
            got = await client.call_tool(
                "factory_repository_status", {"repository": REPO})
            self.assertFalse(got.is_error)
            self.assertIn(SHA, str(got))

    async def test_unauthorized_in_process_mcp_tool_is_denied(self):
        service = ReadOnlyFactoryTools(
            gateway=Gateway(), trusted_owner_authorizer=lambda: False)
        mcp = build_mcp_server(service)
        async with Client(mcp) as client:
            got = await client.call_tool(
                "factory_repository_status", {"repository": REPO})
            self.assertTrue(got.is_error)
            self.assertNotIn(SHA, str(got))


if __name__ == "__main__":
    unittest.main()
