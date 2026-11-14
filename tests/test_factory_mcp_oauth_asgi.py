"""ASGI HTTP request-binding checks using synthetic RSA access tokens, no sockets."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from scripts.factory_mcp_oauth_asgi import FactoryOAuthAsgiBoundary
from scripts.factory_mcp_oauth_resource import FactoryOAuthError
from scripts.factory_mcp_runtime_gate import FactoryRuntimeGate
from scripts.factory_mcp_readonly import ReadOnlyFactoryTools, FactoryMcpAccessError

NOW = datetime.now(timezone.utc).replace(microsecond=0)
ISSUER = "https://auth.example.test"
RESOURCE = "https://factory.example.test/mcp"
CLIENT = "https://client.example.test/metadata"
OWNER = "owner-subject"


class Gateway:
    def __init__(self): self.calls = 0
    def repository_status(self, repo):
        self.calls += 1
        return {"ok": True}
    def pull_request_evidence(self, *args, **kwargs): return {}
    def operation_checkpoint(self, *args, **kwargs): return {}


class AsgiAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private.public_key()))
        cls.jwks = {"keys": [{**pub, "kid": "one", "alg": "RS256", "use": "sig"}]}

    def setUp(self):
        self.claims = {
            "iss": ISSUER, "aud": RESOURCE, "sub": OWNER,
            "client_id": CLIENT, "scope": "factory:read",
            "iat": int(NOW.timestamp()), "nbf": int(NOW.timestamp()),
            "exp": int((NOW + timedelta(minutes=5)).timestamp()),
        }
        self.jwt = jwt.encode(self.claims, self.private, algorithm="RS256",
                              headers={"kid": "one", "typ": "at+jwt"})
        self.called = 0
        self.gateway = Gateway()
        self.saved_task = None

        async def downstream(scope, receive, send):
            self.called += 1
            service = ReadOnlyFactoryTools(gateway=self.gateway,
                                          trusted_owner_authorizer=self.gate.authorize)
            self.assertTrue(service.repository_status("riccardopinato/AppLab")["ok"])
            async def late_work():
                try:
                    service.repository_status("riccardopinato/AppLab")
                except FactoryMcpAccessError:
                    return "DENIED"
                return "UNSAFE"
            self.saved_task = asyncio.create_task(late_work())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        self.host = FactoryOAuthAsgiBoundary(
            downstream_app=downstream, issuer=ISSUER, resource_uri=RESOURCE,
            owner_subject=OWNER, allowed_client_id=CLIENT,
            trusted_jwks_provider=lambda: self.jwks,
            allowed_origins=frozenset({"https://client.example.test"}),
        )
        self.gate = FactoryRuntimeGate(trusted_identity_provider=self.host.current_identity,
                                       utc_now=lambda: NOW, max_calls_per_minute=5)

    def call(self, *, path="/mcp", method="POST", headers=()):
        sent = []
        async def do():
            scope = {
                "type": "http", "method": method, "path": path,
                "headers": [(b"host", b"factory.example.test"), *headers],
            }
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            async def send(message):
                sent.append(message)
            await self.host(scope, receive, send)
            late = await self.saved_task if self.saved_task else None
            return late
        late = asyncio.run(do())
        return sent, late

    def test_metadata_is_public_only_on_expected_host(self):
        sent, _ = self.call(path="/.well-known/oauth-protected-resource/mcp", method="GET")
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(json.loads(sent[1]["body"])["authorization_servers"], [ISSUER])
        self.assertEqual(self.called, 0)

    def test_valid_bearer_is_request_bound_and_late_task_denied(self):
        sent, late = self.call(headers=((b"authorization", ("Bearer " + self.jwt).encode()),))
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(self.called, 1)
        self.assertEqual(self.gateway.calls, 1)
        self.assertEqual(late, "DENIED")
        with self.assertRaises(FactoryOAuthError):
            self.host.current_identity()

    def test_missing_bad_and_duplicate_authorization_deny_without_downstream(self):
        for headers in (
            (), ((b"authorization", b"Bearer a.b.c"),),
            ((b"authorization", ("Bearer " + self.jwt).encode()),
             (b"authorization", ("Bearer " + self.jwt).encode())),
        ):
            with self.subTest(headers=len(headers)):
                sent, _ = self.call(headers=headers)
                self.assertEqual(sent[0]["status"], 401 if len(headers) < 2 else 403)
                if len(headers) < 2:
                    challenge = dict(sent[0]["headers"])[b"www-authenticate"].decode()
                    self.assertIn('resource_metadata=', challenge)
        self.assertEqual(self.called, 0)

    def test_wrong_host_origin_or_path_never_enters_mcp(self):
        cases = [
            ("/mcp", ((b"host", b"evil.example.test"),), 403),
            ("/mcp", ((b"origin", b"https://evil.example.test"),), 403),
            ("/elsewhere", (), 404),
        ]
        for path, headers, expected in cases:
            with self.subTest(path=path, status=expected):
                sent, _ = self.call(path=path, headers=headers)
                self.assertEqual(sent[0]["status"], expected)
        self.assertEqual(self.called, 0)

    def test_allowed_origin_requires_valid_bearer(self):
        sent, _ = self.call(headers=((b"origin", b"https://client.example.test"),))
        self.assertEqual(sent[0]["status"], 401)


if __name__ == "__main__":
    unittest.main()
