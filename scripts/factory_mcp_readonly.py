#!/usr/bin/env python3
"""Factory read-only MCP tool adapter for official Python MCP SDK >=2.3.

An authenticated host MUST inject owner authorizer and real providers.
Importing this module neither connects to GBrain nor starts a server.
No public HTTP, OAuth, shell, filesystem, GitHub write or AppLab queue access
is created here. For stdio, OS-user access is not an OAuth security boundary.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class FactoryMcpAccessError(ValueError):
    """Generic denial, never exposes credential/provider details."""


class ReadOnlyFactoryTools:
    """Caller-bound, no user-supplied auth flags or provider configuration."""

    def __init__(self, *, gateway: Any, trusted_owner_authorizer: Callable[[], bool]):
        required = ("repository_status", "pull_request_evidence", "operation_checkpoint")
        if not all(callable(getattr(gateway, field, None)) for field in required):
            raise FactoryMcpAccessError("READONLY_GATEWAY_NOT_BOUND")
        if not callable(trusted_owner_authorizer):
            raise FactoryMcpAccessError("TRUSTED_OWNER_AUTHORIZER_REQUIRED")
        self._gateway = gateway
        self._authorize = trusted_owner_authorizer

    def _gate(self):
        try:
            allowed = self._authorize()
        except Exception:
            raise FactoryMcpAccessError("ACCESS_DENIED") from None
        if allowed is not True:
            raise FactoryMcpAccessError("ACCESS_DENIED")

    def repository_status(self, repository: str) -> dict[str, Any]:
        self._gate()
        return self._gateway.repository_status(repository)

    def pr_evidence(self, repository: str, pr_number: int,
                    expected_head_sha: str) -> dict[str, Any]:
        self._gate()
        return self._gateway.pull_request_evidence(
            repository, pr_number, expected_head_sha=expected_head_sha
        )

    def operation_checkpoint(self, repository: str,
                             operation_id: str, source_sha: str) -> dict[str, Any]:
        self._gate()
        return self._gateway.operation_checkpoint(
            operation_id, repository=repository, source_sha=source_sha
        )


def build_mcp_server(service: ReadOnlyFactoryTools, *, memory_context=None):
    """Register three read-only tools using official 2026-era MCP SDK v2.

    Intentionally does not call `run()` or supply public HTTP bind/Auth server.
    Host must install MCP SDK and connect trusted providers and the guard.
    """
    if not isinstance(service, ReadOnlyFactoryTools):
        raise FactoryMcpAccessError("TRUSTED_SERVICE_REQUIRED")
    try:
        from mcp.server import MCPServer
    except ImportError:
        raise FactoryMcpAccessError("MCP_SDK_V2_NOT_INSTALLED") from None

    mcp = MCPServer(
        "AppFactory ReadOnly",
        version="0.1.0",
        instructions=(
            "Read-only project status. GitHub/AppLab evidence is source-reported; "
            "never interpret results as merge, release or device certification. "
            "GBrain memory is a separate untrusted context source."
        ),
    )

    @mcp.tool(
        name="factory_repository_status",
        description="Read allowlisted GitHub HEAD metadata. Never certifies CI or device.",
    )
    async def factory_repository_status(repository: str) -> dict[str, Any]:
        return service.repository_status(repository)

    @mcp.tool(
        name="factory_pr_evidence",
        description="Read PR-triggered CI evidence for an exact PR HEAD, not review authorization.",
    )
    async def factory_pr_evidence(repository: str, pr_number: int,
                            expected_head_sha: str) -> dict[str, Any]:
        return service.pr_evidence(repository, pr_number, expected_head_sha)

    @mcp.tool(
        name="factory_operation_checkpoint",
        description="Read one already-persisted AppLab operation state, never enqueue or run it.",
    )
    async def factory_operation_checkpoint(repository: str, operation_id: str,
                                     source_sha: str) -> dict[str, Any]:
        return service.operation_checkpoint(repository, operation_id, source_sha)

    # GBrain remains optional: no memory tool unless owner-approved host
    # explicitly injects a separate, source-pinned context projection.
    if memory_context is not None:
        try:
            from scripts.factory_mcp_memory_context import FactoryMemoryContext
        except ModuleNotFoundError:
            from factory_mcp_memory_context import FactoryMemoryContext
        if not isinstance(memory_context, FactoryMemoryContext):
            raise FactoryMcpAccessError("TRUSTED_MEMORY_CONTEXT_REQUIRED")

        @mcp.tool(
            name="factory_memory_context",
            description="Read bounded, untrusted GBrain context; never grants work or repository authority.",
        )
        async def factory_memory_context(query: str) -> dict[str, Any]:
            return memory_context.recall_context(query)

    return mcp
