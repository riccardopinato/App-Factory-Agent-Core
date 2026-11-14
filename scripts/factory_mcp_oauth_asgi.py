#!/usr/bin/env python3
"""Request-local ASGI OAuth boundary; inert until an owner-approved host mounts it.

Does not open sockets, authorize users, fetch JWKS, register OAuth clients,
change DNS, deploy MCP or write to AppLab. The downstream ASGI application
MUST be the approved read-only MCP app, never a generic administrative API.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.parse import urlsplit

try:
    from scripts.factory_mcp_oauth_resource import (
        FactoryJwtOwnerIdentity, FactoryOAuthError, MAX_AUTH_HEADER
    )
except ModuleNotFoundError:
    from factory_mcp_oauth_resource import (
        FactoryJwtOwnerIdentity, FactoryOAuthError, MAX_AUTH_HEADER
    )


@dataclass
class _Lease:
    identity: dict[str, Any]
    active: bool = True


class FactoryOAuthAsgiBoundary:
    """Wrap a trusted MCP ASGI app; its identity is live only during a request.

    The host wires FactoryRuntimeGate(trusted_identity_provider=host.current_identity)
    into ReadOnlyFactoryTools. The verifier is synchronous: inject a bounded,
    issuer-pinned *cached* JWKS reader, never unbounded network fetch on event loop.
    """
    def __init__(self, *, downstream_app: Callable,
                 issuer: str, resource_uri: str, owner_subject: str,
                 allowed_client_id: str,
                 trusted_jwks_provider: Callable[[], dict[str, Any]],
                 allowed_origins: frozenset[str] = frozenset()):
        if not callable(downstream_app) or not isinstance(allowed_origins, frozenset):
            raise FactoryOAuthError("OAUTH_CONFIGURATION_INVALID")
        for origin in allowed_origins:
            try:
                parsed = urlsplit(origin)
                valid = (isinstance(origin, str) and parsed.scheme == "https"
                         and bool(parsed.hostname) and parsed.username is None
                         and parsed.password is None and parsed.path in ("", "/")
                         and not parsed.query and not parsed.fragment
                         and "*" not in parsed.netloc)
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise FactoryOAuthError("OAUTH_CONFIGURATION_INVALID")
        self._bearer = ContextVar("factory_asgi_auth_header", default="")
        self._identity = ContextVar("factory_asgi_owner_lease", default=None)
        self._verifier = FactoryJwtOwnerIdentity(
            issuer=issuer, resource_uri=resource_uri, owner_subject=owner_subject,
            allowed_client_id=allowed_client_id,
            trusted_authorization_header=self._bearer.get,
            trusted_jwks_provider=trusted_jwks_provider,
        )
        self._downstream = downstream_app
        self._host = urlsplit(resource_uri).netloc.lower()
        self._origins = allowed_origins

    def current_identity(self) -> dict[str, Any]:
        """Host-owned callback; a copied task context cannot revive a finished call."""
        lease = self._identity.get()
        if not isinstance(lease, _Lease) or not lease.active:
            raise FactoryOAuthError("OAUTH_ACCESS_DENIED")
        return lease.identity.copy()

    async def _reply(self, send, status: int, payload: dict,
                     extra_headers: tuple[tuple[bytes, bytes], ...] = ()):
        headers = [(b"content-type", b"application/json; charset=utf-8"),
                   (b"cache-control", b"no-store"), *extra_headers]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body",
                    "body": json.dumps(payload, separators=(",", ":")).encode("utf-8")})

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "lifespan":
            return await self._downstream(scope, receive, send)
        if scope.get("type") != "http":
            if scope.get("type") == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        try:
            headers = scope.get("headers")
            if not isinstance(headers, (list, tuple)) or len(headers) > 64:
                raise ValueError()
            values: dict[bytes, list[bytes]] = {}
            for pair in headers:
                if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                        or not isinstance(pair[0], bytes) or not isinstance(pair[1], bytes)
                        or len(pair[0]) > 128 or len(pair[1]) > MAX_AUTH_HEADER):
                    raise ValueError()
                values.setdefault(pair[0].lower(), []).append(pair[1])
            if any(len(values.get(h, [])) > 1 for h in
                   (b"host", b"origin", b"authorization")):
                raise ValueError()
            host_values = values.get(b"host", [])
            host = host_values[0].decode("ascii").lower() if host_values else ""
            if host != self._host:
                raise ValueError()
            origins = values.get(b"origin", [])
            if origins and origins[0].decode("ascii") not in self._origins:
                raise ValueError()
        except (ValueError, UnicodeError, TypeError):
            await self._reply(send, 403, {"error": "forbidden"})
            return

        method, path = scope.get("method"), scope.get("path")
        if path == "/.well-known/oauth-protected-resource/mcp" and method == "GET":
            await self._reply(send, 200, self._verifier.protected_resource_metadata())
            return
        if path != "/mcp":
            await self._reply(send, 404, {"error": "not_found"})
            return
        if method not in ("GET", "POST", "DELETE"):
            await self._reply(send, 405, {"error": "method_not_allowed"})
            return

        try:
            auth = values.get(b"authorization", [])
            if len(auth) != 1:
                raise ValueError()
            token = self._bearer.set(auth[0].decode("ascii"))
            try:
                identity = self._verifier.read_owner_identity()
            finally:
                self._bearer.reset(token)
        except Exception:
            await self._reply(send, 401, {"error": "unauthorized"}, (
                (b"www-authenticate",
                 self._verifier.unauthorized_challenge().encode("ascii")),))
            return

        lease = _Lease(identity)
        ctx = self._identity.set(lease)
        try:
            await self._downstream(scope, receive, send)
        finally:
            lease.active = False
            self._identity.reset(ctx)
