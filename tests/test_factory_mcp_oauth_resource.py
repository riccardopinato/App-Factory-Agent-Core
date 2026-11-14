"""Cryptographic offline OAuth rejection matrix; no listener or live secrets."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from scripts.factory_mcp_oauth_resource import FactoryJwtOwnerIdentity, FactoryOAuthError
from scripts.factory_mcp_runtime_gate import FactoryRuntimeGate
from scripts.factory_mcp_readonly import ReadOnlyFactoryTools, FactoryMcpAccessError

ISSUER = "https://auth.example.test"
RESOURCE = "https://gateway.example.test/mcp"
CLIENT = "https://chat-client.example.test/id"
OWNER = "owner-subject-01"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


class FakeGateway:
    def __init__(self): self.calls = 0
    def repository_status(self, repository):
        self.calls += 1
        return {"read_only": True, "repository": repository}
    def pull_request_evidence(self, *args, **kwargs):
        self.calls += 1
        return {"read_only": True}
    def operation_checkpoint(self, *args, **kwargs):
        self.calls += 1
        return {"read_only": True}


class OAuthResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private.public_key()))
        cls.good_key = {**public, "kid": "rsa-one", "use": "sig", "alg": "RS256"}

    def setUp(self):
        self.jwks = {"keys": [self.good_key]}
        self.claims = {
            "iss": ISSUER, "aud": RESOURCE, "sub": OWNER,
            "client_id": CLIENT, "scope": "factory:read",
            "iat": int(NOW.timestamp()), "nbf": int(NOW.timestamp()),
            "exp": int((NOW + timedelta(minutes=10)).timestamp()),
        }
        self.raw = ""
        self.auth = FactoryJwtOwnerIdentity(
            issuer=ISSUER, resource_uri=RESOURCE, owner_subject=OWNER,
            allowed_client_id=CLIENT,
            trusted_authorization_header=lambda: self.raw,
            trusted_jwks_provider=lambda: self.jwks,
        )
        self.sign()

    def sign(self, *, claims=None, headers=None, key=None, algorithm="RS256"):
        claims = self.claims if claims is None else claims
        hdr = {"kid": "rsa-one", "typ": "at+jwt"}
        if headers:
            hdr.update(headers)
        token = jwt.encode(claims, self.private if key is None else key,
                           algorithm=algorithm, headers=hdr)
        self.raw = "Bearer " + token

    def test_valid_jwt_is_tied_to_one_owner_and_scope(self):
        ident = self.auth.read_owner_identity()
        self.assertEqual(ident["principal_id"], "owner:factory")
        self.assertTrue(ident["host_verified"])
        self.assertEqual(ident["scopes"], frozenset({"factory:read"}))
        self.assertEqual(ident["expires_at"], NOW + timedelta(minutes=10))

    def test_metadata_and_challenge_are_discovery_only(self):
        self.assertEqual(self.auth.protected_resource_metadata(), {
            "resource": RESOURCE, "authorization_servers": [ISSUER],
            "scopes_supported": ["factory:read"]})
        self.assertEqual(self.auth.unauthorized_challenge(),
            'Bearer resource_metadata="https://gateway.example.test/.well-known/oauth-protected-resource/mcp", scope="factory:read"')

    def test_configuration_rejects_insecure_resource(self):
        with self.assertRaisesRegex(FactoryOAuthError, "OAUTH_CONFIGURATION_INVALID"):
            FactoryJwtOwnerIdentity(
                issuer=ISSUER, resource_uri="http://gateway.example.test/mcp",
                owner_subject=OWNER, allowed_client_id=CLIENT,
                trusted_authorization_header=lambda: self.raw,
                trusted_jwks_provider=lambda: self.jwks)

    def test_reject_invalid_claims(self):
        mutations = [
            {"iss": "https://evil.example.test"},
            {"aud": "https://other.example.test/mcp"},
            {"aud": [RESOURCE]},
            {"sub": "another-owner"},
            {"client_id": "different-client"},
            {"scope": "factory:write"},
            {"scope": "factory:read factory:write"},
            {"scope": ""},
            {"exp": int((NOW - timedelta(minutes=1)).timestamp())},
            {"exp": int((NOW + timedelta(hours=2)).timestamp())},
            {"nbf": int((NOW + timedelta(minutes=1)).timestamp())},
            {"iat": int((NOW + timedelta(minutes=2)).timestamp())},
            {"nbf": True},
            {"client_id": CLIENT, "azp": "different-client"},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.sign(claims={**self.claims, **mutation})
                with self.assertRaisesRegex(FactoryOAuthError, "^OAUTH_ACCESS_DENIED$"):
                    self.auth.read_owner_identity()

    def test_reject_missing_required_claims(self):
        for claim in ("iss", "aud", "sub", "iat", "nbf", "exp", "scope", "client_id"):
            with self.subTest(claim=claim):
                c = dict(self.claims)
                del c[claim]
                self.sign(claims=c)
                with self.assertRaises(FactoryOAuthError):
                    self.auth.read_owner_identity()

    def test_reject_untrusted_headers(self):
        for headers in ({"typ": "JWT"}, {"alg": "none"},
                        {"kid": "unknown"}, {"jku": "https://evil.example.test/keys"},
                        {"x5u": "https://evil.example.test/cert"},
                        {"crit": ["unexpected"]}):
            with self.subTest(headers=headers):
                if headers.get("alg") == "none":
                    self.sign(headers=headers, key="", algorithm="none")
                else:
                    self.sign(headers=headers)
                with self.assertRaisesRegex(FactoryOAuthError, "^OAUTH_ACCESS_DENIED$"):
                    self.auth.read_owner_identity()

    def test_reject_jwks_provider_malformation_or_ambiguous_kids(self):
        for jwks in (None, {}, {"keys": []},
                     {"keys": [self.good_key] * 9},
                     {"keys": [self.good_key, self.good_key]},
                     {"keys": [{**self.good_key, "use": "enc"}]},
                     {"keys": [{**self.good_key, "d": "not-allowed"}]},
                     {"keys": [{**self.good_key, "alg": "HS256"}]}):
            with self.subTest(jwks=str(jwks)[:60]):
                self.jwks = jwks
                with self.assertRaisesRegex(FactoryOAuthError, "^OAUTH_ACCESS_DENIED$"):
                    self.auth.read_owner_identity()

    def test_reject_missing_duplicate_or_corrupt_bearer(self):
        good = self.raw
        for bad in ("", "Basic " + good[7:], "Bearer " + good,
                    good + "\nX-Evil: yes", good + " ", "Bearer a.b.c",
                    "Bearer " + ("a" * 8200)):
            with self.subTest(header=bad[:24]):
                self.raw = bad
                with self.assertRaisesRegex(FactoryOAuthError, "^OAUTH_ACCESS_DENIED$"):
                    self.auth.read_owner_identity()

    def test_runtime_tool_gate_never_calls_provider_on_denied_access(self):
        now = NOW
        gate = FactoryRuntimeGate(
            trusted_identity_provider=self.auth.read_owner_identity,
            max_calls_per_minute=1, clock=lambda: 10.0, utc_now=lambda: now)
        gateway = FakeGateway()
        service = ReadOnlyFactoryTools(
            gateway=gateway, trusted_owner_authorizer=gate.authorize)
        self.assertTrue(service.repository_status("riccardopinato/AppLab")["read_only"])
        with self.assertRaisesRegex(FactoryMcpAccessError, "^ACCESS_DENIED$"):
            service.repository_status("riccardopinato/AppLab")
        self.assertEqual(gateway.calls, 1)
        self.raw = "Bearer not-a-jwt"
        with self.assertRaisesRegex(FactoryMcpAccessError, "^ACCESS_DENIED$"):
            service.repository_status("riccardopinato/AppLab")
        self.assertEqual(gateway.calls, 1)


if __name__ == "__main__":
    unittest.main()
