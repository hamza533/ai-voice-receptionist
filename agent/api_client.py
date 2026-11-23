"""Tiny HTTPS client for the receptionist API. The agent holds no business logic."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any

import httpx

log = logging.getLogger("agent.api")


class ApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("API_URL", "http://localhost:8010")).rstrip("/")
        self.token = token or os.environ.get("AGENT_SERVICE_TOKEN", "")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, json: dict[str, Any], *, attempts: int = 2) -> dict[str, Any]:
        """POST with one retry on network errors / 5xx (tools are idempotent server-side)."""
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                r = await self._client.post(path, json=json)
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=r.request, response=r)
                r.raise_for_status()
                return r.json()  # type: ignore[no-any-return]
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise
                if attempt < attempts - 1:
                    await asyncio.sleep(0.3 + random.random() * 0.4)
        assert last is not None
        raise last

    async def start_call(self, channel: str, room: str, caller_number: str) -> dict[str, Any]:
        return await self._post(
            "/api/agent/calls/start",
            {"channel": channel, "room_name": room, "caller_number": caller_number},
        )

    async def end_call(self, call_id: str, payload: dict[str, Any]) -> None:
        await self._post(f"/api/agent/calls/{call_id}/end", payload, attempts=4)

    async def tool(self, call_id: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._post(f"/api/agent/tools/{name}", {"call_id": call_id, "args": args})
        except Exception:
            log.exception("tool call failed", extra={"tool": name})
            return {
                "status": "error",
                "message": "The system is not responding. Apologise, and offer to take a "
                "message so the team can call back. Do not say anything was booked.",
                "data": {},
            }
