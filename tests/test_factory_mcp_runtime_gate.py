"""Runtime guard / remote-exposure safety, no sockets and no OAuth secrets."""
from datetime import datetime, timedelta, timezone
import unittest

from scripts.factory_mcp_runtime_gate import (
    FactoryRuntimeGate, RuntimeGateError, runtime_exposure_preflight
)
from scripts.factory_mcp_readonly import ReadOnlyFactoryTools, FactoryMcpAccessError

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class FakeGateway:
    def __init__(self): self.calls = 0
    def repository_status(self, repository):
        self.calls += 1
        return {"repository": repository, "read_only": True}
    def pull_request_evidence(self, *args, **kwargs):
        self.calls += 1
        return {"read_only": True}
    def operation_checkpoint(self, *args, **kwargs):
        self.calls += 1
        return {"read_only": True}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.current = NOW
        self.tick = 10.0
        self.identity = {
            "principal_id": "owner:factory", "host_verified": True,
            "scopes": frozenset({"factory:read"}),
            "expires_at": NOW + timedelta(minutes=10),
        }
        self.gate = FactoryRuntimeGate(
            trusted_identity_provider=lambda: self.identity,
            max_calls_per_minute=2,
            clock=lambda: self.tick,
            utc_now=lambda: self.current,
        )

    def test_scoped_identity_and_per_process_limit(self):
        self.assertTrue(self.gate.authorize())
        self.assertTrue(self.gate.authorize())
        self.assertFalse(self.gate.authorize())
        self.tick += 60
        self.assertTrue(self.gate.authorize())
        self.gate.revoke("owner:factory")
        self.assertFalse(self.gate.authorize())

    def test_unverified_expired_or_missing_scopes_denied(self):
        for update in [
            {"host_verified": "true"}, {"host_verified": False},
            {"scopes": frozenset({"factory:write"})},
            {"scopes": frozenset({"factory:read", "factory:write"})},
            {"expires_at": NOW - timedelta(seconds=1)},
            {"expires_at": NOW + timedelta(days=7)},
            {"principal_id": "../secrets\\.."},
        ]:
            with self.subTest(update=update):
                gate = FactoryRuntimeGate(
                    trusted_identity_provider=lambda v=update: {**self.identity, **v},
                    utc_now=lambda: NOW,
                )
                self.assertFalse(gate.authorize())

    def test_host_exception_never_exposes_secrets(self):
        def broken():
            raise ValueError("OAUTH_BEARER_SECRET")
        gate = FactoryRuntimeGate(trusted_identity_provider=broken)
        self.assertFalse(gate.authorize())

    def test_shared_tool_gate_denial_occurs_before_gateway(self):
        app = FakeGateway()
        service = ReadOnlyFactoryTools(gateway=app, trusted_owner_authorizer=self.gate.authorize)
        self.assertTrue(service.repository_status("riccardopinato/AppLab")["read_only"])
        self.assertTrue(service.repository_status("riccardopinato/AppLab")["read_only"])
        with self.assertRaisesRegex(FactoryMcpAccessError, "ACCESS_DENIED"):
            service.repository_status("riccardopinato/AppLab")
        self.assertEqual(app.calls, 2)

    def test_bad_limit_and_identity_source_denied(self):
        with self.assertRaisesRegex(RuntimeGateError, "INVALID_CALL_BUDGET"):
            FactoryRuntimeGate(trusted_identity_provider=lambda: self.identity,
                               max_calls_per_minute=0)
        with self.assertRaisesRegex(RuntimeGateError, "HOST_AUTHENTICATION_REQUIRED"):
            FactoryRuntimeGate(trusted_identity_provider=None)

    def test_public_wildcard_and_unverified_remote_rejected(self):
        r = runtime_exposure_preflight(
            transport="streamable-http", bind_host="0.0.0.0",
            host_authentication_verified=False,
            tls_termination_verified=False, verified_provider_scope=False)
        self.assertTrue(r["blocked"])
        self.assertIn("PUBLIC_BIND_FORBIDDEN", r["blockers"])
        self.assertIn("AUTH_HOST_NOT_VERIFIED", r["blockers"])
        self.assertFalse(r["public_listener_started"])

    def test_positive_report_does_not_certify_remote(self):
        r = runtime_exposure_preflight(
            transport="streamable-http", bind_host="127.0.0.1",
            host_authentication_verified=True, tls_termination_verified=True,
            verified_provider_scope=True)
        self.assertFalse(r["blocked"])
        self.assertEqual(r["authority"], "CONFIG_REVIEW_ONLY")
        self.assertFalse(r["connected_to_chatgpt"])
        self.assertFalse(r["remote_authentication_certified"])

    def test_stdio_never_authorizes_network_listener(self):
        r = runtime_exposure_preflight(
            transport="stdio", bind_host="0.0.0.0",
            host_authentication_verified=True, tls_termination_verified=False,
            verified_provider_scope=True)
        self.assertTrue(r["blocked"])
        self.assertIn("STDIO_NETWORK_BIND_NOT_ALLOWED", r["blockers"])


if __name__ == "__main__":
    unittest.main()
