#!/usr/bin/env python3
"""Offline OAuth JWT access-token verifier for the read-only Factory MCP resource.

No HTTP listener, discovery fetch, authorization server, token minting or key
download is implemented here. The host MUST supply request-bound headers and
JWKS from a pinned issuer HTTPS endpoint. Never trust MCP tool arguments as auth.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import re

try:
    import jwt
except ImportError:  # Fail closed until the pinned cryptographic dependency exists.
    jwt = None

BEARER_RE = re.compile(r"^Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$", re.I)
KID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
MAX_AUTH_HEADER = 8192
MAX_TOKEN_SECONDS = 3600
MAX_JWKS_KEYS = 8
EXPECTED_SCOPE = "factory:read"
EXPECTED_TOKEN_TYPE = "at+jwt"
PRINCIPAL_ID = "owner:factory"


class FactoryOAuthError(ValueError):
    """Uniform denial; no raw token, JWT parser error or host secret leaks."""


def _https_url(value: str) -> bool:
    if not isinstance(value, str) or not 9 <= len(value) <= 512:
        return False
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and bool(u.hostname)
                and u.username is None and u.password is None
                and not u.query and not u.fragment and not u.path.startswith("//"))
    except ValueError:
        return False


class FactoryJwtOwnerIdentity:
    """Verify one JWT access token before the existing FactoryRuntimeGate.

    This is NOT a standalone OAuth host. The trusted Authorization-header
    source must be request-local and set only by the HTTP transport, while the
    trusted JWKS provider must use a fixed HTTPS JWKS URI discovered from the
    configured issuer (never token-supplied jku/x5u). A host also needs OAuth
    protected-resource metadata, verified routing, TLS, JWKS cache/rotation,
    revocation strategy and distributed rate limiting before remote launch.

    Provider contract: RS256, typ=at+jwt, singleton aud=resource URI,
    client_id (or azp) bound to the approved client, exact sub=owner.
    """
    def __init__(
        self, *, issuer: str, resource_uri: str, owner_subject: str,
        allowed_client_id: str,
        trusted_authorization_header: Callable[[], str],
        trusted_jwks_provider: Callable[[], dict[str, Any]],
    ):
        if (not _https_url(issuer) or not _https_url(resource_uri)
                or urlsplit(resource_uri).path != "/mcp"
                or not isinstance(owner_subject, str) or not 1 <= len(owner_subject) <= 256
                or any(ord(c) < 33 for c in owner_subject)
                or not isinstance(allowed_client_id, str)
                or not 1 <= len(allowed_client_id) <= 256
                or any(ord(c) < 33 for c in allowed_client_id)
                or not callable(trusted_authorization_header)
                or not callable(trusted_jwks_provider)):
            raise FactoryOAuthError("OAUTH_CONFIGURATION_INVALID")
        self._issuer = issuer
        self._resource = resource_uri
        self._owner = owner_subject
        self._client = allowed_client_id
        self._header = trusted_authorization_header
        self._jwks = trusted_jwks_provider

    def protected_resource_metadata(self) -> dict[str, Any]:
        """Host serves at /.well-known/oauth-protected-resource/mcp."""
        return {
            "resource": self._resource,
            "authorization_servers": [self._issuer],
            "scopes_supported": [EXPECTED_SCOPE],
        }

    def unauthorized_challenge(self) -> str:
        parsed = urlsplit(self._resource)
        meta = urlunsplit((parsed.scheme, parsed.netloc,
                           "/.well-known/oauth-protected-resource/mcp", "", ""))
        return f'Bearer resource_metadata="{meta}", scope="{EXPECTED_SCOPE}"'

    def read_owner_identity(self) -> dict[str, Any]:
        """Trusted identity provider for FactoryRuntimeGate; fail closed."""
        try:
            if jwt is None:
                raise ValueError("crypto unavailable")
            auth = self._header()
            if not isinstance(auth, str) or len(auth) > MAX_AUTH_HEADER:
                raise ValueError("bad authorization header")
            m = BEARER_RE.fullmatch(auth)
            if not m:
                raise ValueError("bearer required")
            token = m.group(1)
            header = jwt.get_unverified_header(token)
            if (not isinstance(header, dict)
                    or header.get("alg") != "RS256"
                    or header.get("typ") != EXPECTED_TOKEN_TYPE
                    or "crit" in header or "jku" in header or "x5u" in header
                    or not isinstance(header.get("kid"), str)
                    or KID_RE.fullmatch(header["kid"]) is None):
                raise ValueError("unsafe JOSE header")

            # The token's kid only selects among already trusted issuer keys.
            jwks = self._jwks()
            keys = jwks.get("keys") if isinstance(jwks, dict) else None
            if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_JWKS_KEYS:
                raise ValueError("bad trusted JWKS")
            matching = [k for k in keys if isinstance(k, dict)
                        and k.get("kid") == header["kid"]]
            if len(matching) != 1:
                raise ValueError("unknown or ambiguous kid")
            key = matching[0]
            if (key.get("kty") != "RSA" or key.get("alg") != "RS256"
                    or key.get("use") != "sig"
                    or not isinstance(key.get("n"), str)
                    or not isinstance(key.get("e"), str)
                    or any(f in key for f in ("d", "p", "q", "dp", "dq", "qi", "oth"))):
                raise ValueError("wrong JWK kind")
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            claims = jwt.decode(
                token, public_key, algorithms=["RS256"],
                issuer=self._issuer, audience=self._resource, leeway=0,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "nbf"],
                         "strict_aud": True},
            )
            if (claims.get("sub") != self._owner
                    or type(claims.get("exp")) is not int
                    or type(claims.get("iat")) is not int
                    or type(claims.get("nbf")) is not int
                    or not 0 < claims["exp"] - claims["iat"] <= MAX_TOKEN_SECONDS
                    or claims["nbf"] > claims["exp"]
                    or claims.get("scope") != EXPECTED_SCOPE
                    or not (claims.get("client_id") == self._client
                            or claims.get("azp") == self._client)
                    or any(c in claims and claims[c] != self._client
                           for c in ("client_id", "azp"))):
                raise ValueError("wrong owner, client, lifetime or scope")
            return {
                "principal_id": PRINCIPAL_ID,
                "host_verified": True,
                "scopes": frozenset({EXPECTED_SCOPE}),
                "expires_at": datetime.fromtimestamp(claims["exp"], timezone.utc),
            }
        except Exception:
            raise FactoryOAuthError("OAUTH_ACCESS_DENIED") from None
