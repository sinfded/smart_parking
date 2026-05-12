"""Publishes gateway heartbeat to MQTT and updates device health in Supabase."""

import asyncio
from datetime import datetime, timezone

import structlog

from .config import Settings

log = structlog.get_logger()

HEARTBEAT_INTERVAL = 30  # seconds


class HealthReporter:
    def __init__(self, settings: Settings, writer: "SupabaseWriter") -> None:  # noqa: F821
        self._s      = settings
        self._writer = writer

    async def run(self) -> None:
        while True:
            await self._heartbeat()
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _heartbeat(self) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        log.debug("gateway.heartbeat", ts=ts)
        # Update gateway last_seen_at in Supabase
        try:
            assert self._writer._client
            await (
                self._writer._client
                .table("gateways")
                .update({"last_seen_at": ts})
                .eq("lot_id", self._s.lot_id)
                .execute()
            )
        except Exception as exc:
            log.warning("heartbeat.failed", error=str(exc))

    async def handle_device(self, mac: str, payload: dict) -> None:
        """Update health + last_seen_at for an ESP32 or camera device."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            assert self._writer._client
            await (
                self._writer._client
                .table("devices")
                .update({"health": "online", "last_seen_at": ts, "metadata": payload})
                .eq("lot_id", self._s.lot_id)
                .eq("mac_or_serial", mac)
                .execute()
            )
        except Exception as exc:
            log.warning("device.health_update_failed", mac=mac, error=str(exc))
