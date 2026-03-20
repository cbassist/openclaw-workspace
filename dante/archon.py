"""Async Archon MCP client for Donna."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_ARCHON_MCP_URL = "http://localhost:8051/mcp"
CONNECT_TIMEOUT_SECONDS = 30.0
READ_TIMEOUT_SECONDS = 60.0


class ArchonClient:
    """Small per-call MCP client for the Archon server."""

    def __init__(self, url: str | None = None):
        self.url = url or os.environ.get("ARCHON_MCP_URL", DEFAULT_ARCHON_MCP_URL)

    async def health(self) -> dict:
        try:
            data = await self._call_tool_json("health_check")
        except RuntimeError as exc:
            return {
                "ok": False,
                "reachable": False,
                "url": self.url,
                "error": str(exc),
            }

        if isinstance(data, dict):
            data.setdefault("ok", True)
            data.setdefault("reachable", True)
            data.setdefault("url", self.url)
            return data

        return {
            "ok": True,
            "reachable": True,
            "url": self.url,
            "data": data,
        }

    async def list_tasks(self, status: str = "todo", project_id: str | None = None) -> list[dict]:
        arguments: dict[str, Any] = {
            "filter_by": "status",
            "filter_value": status,
            "include_closed": True,
        }
        if project_id:
            arguments["project_id"] = project_id

        try:
            data = await self._call_tool_json("find_tasks", arguments=arguments)
        except RuntimeError:
            return []

        return self._coerce_list_of_dicts(data)

    async def get_task(self, task_id: str) -> dict | None:
        try:
            data = await self._call_tool_json("find_tasks", arguments={"task_id": task_id})
        except RuntimeError:
            return None

        if isinstance(data, dict):
            # Unwrap {"success": true, "tasks": [...]}
            for key in ("tasks", "task"):
                if key in data and isinstance(data[key], list):
                    return data[key][0] if data[key] else None
                if key in data and isinstance(data[key], dict):
                    return data[key]
            return data

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item

        return None

    async def update_task(self, task_id: str, **kwargs) -> dict:
        arguments = {"action": "update", "task_id": task_id, **kwargs}

        try:
            data = await self._call_tool_json("manage_task", arguments=arguments)
        except RuntimeError as exc:
            return {
                "success": False,
                "task_id": task_id,
                "error": str(exc),
            }

        if isinstance(data, dict):
            return data

        return {
            "success": True,
            "task_id": task_id,
            "data": data,
        }

    async def list_projects(self) -> list[dict]:
        try:
            data = await self._call_tool_json("find_projects")
        except RuntimeError:
            return []

        return self._coerce_list_of_dicts(data)

    async def _call_tool_json(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        timeout = httpx.Timeout(
            connect=CONNECT_TIMEOUT_SECONDS,
            read=READ_TIMEOUT_SECONDS,
            write=READ_TIMEOUT_SECONDS,
            pool=CONNECT_TIMEOUT_SECONDS,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as http_client:
                async with streamable_http_client(
                    url=self.url,
                    http_client=http_client,
                    terminate_on_close=True,
                ) as (read_stream, write_stream, _get_session_id):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=timedelta(seconds=READ_TIMEOUT_SECONDS),
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=arguments or {})
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Unable to reach Archon MCP at {self.url}: {exc}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"Archon MCP request timed out for {tool_name}") from exc
        except Exception as exc:
            raise RuntimeError(f"Archon MCP call failed for {tool_name}: {exc}") from exc

        if getattr(result, "isError", False):
            message = self._extract_text(result) or f"Archon MCP tool error: {tool_name}"
            raise RuntimeError(message)

        payload = self._extract_text(result)
        if not payload:
            return None

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Archon MCP returned invalid JSON for {tool_name}: {exc}") from exc

    @staticmethod
    def _extract_text(result: Any) -> str:
        content = getattr(result, "content", None) or []
        if not content:
            return ""

        first_item = content[0]
        return getattr(first_item, "text", "") or ""

    @staticmethod
    def _coerce_list_of_dicts(data: Any) -> list[dict]:
        # Unwrap MCP responses like {"success": true, "tasks": [...], ...}
        if isinstance(data, dict):
            for key in ("tasks", "projects", "results", "items"):
                if key in data and isinstance(data[key], list):
                    return [item for item in data[key] if isinstance(item, dict)]
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []
