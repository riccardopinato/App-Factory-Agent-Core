#!/usr/bin/env python3
"""Factory MCP runtime policy boundary: no listener, network or job dispatch.

Use with ReadOnlyFactoryTools(trusted_owner_authorizer=gate.authorize).
This gates in-process tool calls on a host-authenticated principal with expiry,
bounded per-process rate and explicit revocation. It does not IMPLEMENT OAuth
or provide a public transport. The host is solely responsible for verifying
signature, issuer, audience and exact authenticated user identity.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Any, Callable
import re

ID_RE = re.compile(r"^[A-Za-z0-9_.:@/-]{1,128}$")
LIMIT_MAX_CALLS = 60
LIMIT_WINDOW = 60
ALLOWED_SCOPES = frozenset({"factory:read"})


class RuntimeGateError(ValueError):
    pass


class FactoryRuntimeGate:
    def __init__(
        self, *,
        trusted_identity_provider: Callable[[], dict[str, Any]],
        max_calls_per_minute: int = 30,
        clock: Callable[[], float] = monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if not callable(trusted_identity_provider) or not callable(clock) or not callable(utc_now):
            raise RuntimeGateError("HOST_AUTHENTICATION_REQUIRED")
        if type(max_calls_per_minute) is not int or not 1 <= max_calls_per_minute <= LIMIT_MAX_CALLS:
            raise RuntimeGateError("INVALID_CALL_BUDGET")
        self._identity_provider = trusted_identity_provider
        self._clock = clock
        self._utc_now = utc_now
        self._limit = max_calls_per_minute
        self._calls: dict[str, deque[float]] = {}
        self._revoked: set[str] = set()
        self._lock = RLock()

    def revoke(self, principal_id: str) -> None:
        if not isinstance(principal_id, str) or ID_RE.fullmatch(principal_id) is None:
            raise RuntimeGateError("INVALID_IDENTITY")
        with self._lock:
            self._revoked.add(principal_id)
            self._calls.pop(principal_id, None)

    def authorize(self) -> bool:
        """Return False (never a token or private message) on any error."""
        try:
            identity = self._identity_provider()
            if not isinstance(identity, dict) or set(identity) != {
                "principal_id", "host_verified", "scopes", "expires_at"
            }:
                return False
            pid, scopes = identity["principal_id"], identity["scopes"]
            if (not isinstance(pid, str) or ID_RE.fullmatch(pid) is None
                    or identity["host_verified"] is not True
                    or not isinstance(scopes, (frozenset, set))
                    or scopes != ALLOWED_SCOPES):
                return False
            expiry = identity["expires_at"]
            if not isinstance(expiry, datetime) or expiry.tzinfo is None:
                return False
            now = self._utc_now()
            if not isinstance(now, datetime) or now.tzinfo is None:
                return False
            now = now.astimezone(timezone.utc)
            expiry = expiry.astimezone(timezone.utc)
            # Limit acceptance to a short host-verified session lifetime.
            seconds_left = (expiry - now).total_seconds()
            if not 0 < seconds_left <= 3600:
                return False
            tick = self._clock()
            if type(tick) not in (float, int) or not 0 <= tick < float("inf"):
                return False
            with self._lock:
                if pid in self._revoked:
                    return False
                queue = self._calls.setdefault(pid, deque())
                while queue and tick - queue[0] >= LIMIT_WINDOW:
                    queue.popleft()
                if len(queue) >= self._limit:
                    return False
                queue.append(tick)
            return True
        except Exception:
            return False


def runtime_exposure_preflight(
    *, transport: str, bind_host: str, host_authentication_verified: bool,
    tls_termination_verified: bool, verified_provider_scope: bool,
) -> dict[str, Any]:
    """Never certifies a deployment from booleans supplied by a caller.

    Even a fully positive static config is only a reported candidate.
    No external port or public ChatGPT registration is created by this call.
    """
    blocked = []
    if transport not in ("stdio", "streamable-http"):
        blocked.append("TRANSPORT_UNSUPPORTED")
    if transport == "streamable-http":
        if bind_host not in ("127.0.0.1", "::1"):
            blocked.append("PUBLIC_BIND_FORBIDDEN")
        if host_authentication_verified is not True:
            blocked.append("AUTH_HOST_NOT_VERIFIED")
        if tls_termination_verified is not True:
            blocked.append("TLS_PROXY_NOT_VERIFIED")
        if verified_provider_scope is not True:
            blocked.append("GITHUB_APPLAB_SCOPE_NOT_VERIFIED")
    elif transport == "stdio":
        if bind_host not in ("", "127.0.0.1"):
            blocked.append("STDIO_NETWORK_BIND_NOT_ALLOWED")
        if host_authentication_verified is not True:
            blocked.append("AUTH_HOST_NOT_VERIFIED")
        if verified_provider_scope is not True:
            blocked.append("GITHUB_APPLAB_SCOPE_NOT_VERIFIED")
    return {
        "schema_version": 1, "record_type": "FACTORY_MCP_RUNTIME_PREFLIGHT",
        "authority": "CONFIG_REVIEW_ONLY",
        "blocked": bool(blocked),
        "blockers": blocked,
        "transport": transport if transport in ("stdio", "streamable-http") else "INVALID",
        "public_listener_started": False, "connected_to_chatgpt": False,
        "remote_authentication_certified": False, "runtime_verified": False,
        "read_only": True, "certification_granted": False,
    }
