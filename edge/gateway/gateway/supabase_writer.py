"""Calls the report_slot_state RPC and manages the gateway's Supabase auth session."""

import structlog
from supabase import AsyncClient, acreate_client

from .config import Settings

log = structlog.get_logger()


class SupabaseWriter:
    def __init__(self, settings: Settings) -> None:
        self._s:      Settings     = settings
        self._client: AsyncClient | None = None
        # slot_label → slot UUID cache so we don't query on every reading
        self._slot_cache: dict[str, str] = {}

    async def authenticate(self) -> None:
        self._client = await acreate_client(self._s.supabase_url, self._s.supabase_key)
        await self._client.auth.sign_in_with_password({
            "email":    self._s.gateway_email,
            "password": self._s.gateway_password,
        })
        log.info("supabase.authenticated", lot_id=self._s.lot_id)

    async def _resolve_slot(self, slot_label: str) -> str | None:
        """Return the UUID for a slot label, with a simple in-process cache."""
        if slot_label in self._slot_cache:
            return self._slot_cache[slot_label]
        assert self._client
        resp = (
            await self._client.table("slots")
            .select("id")
            .eq("lot_id", self._s.lot_id)
            .eq("label", slot_label)
            .is_("deleted_at", "null")
            .single()
            .execute()
        )
        if resp.data:
            self._slot_cache[slot_label] = resp.data["id"]
            return resp.data["id"]
        log.warning("slot.not_found", label=slot_label)
        return None

    async def report_slot_state(self, slot_label: str, new_state: str) -> None:
        slot_id = await self._resolve_slot(slot_label)
        if slot_id is None:
            return
        assert self._client
        try:
            await self._client.rpc("report_slot_state", {
                "p_slot_id":   slot_id,
                "p_new_state": new_state,
                "p_source":    "ultrasonic",
            }).execute()
            log.info("supabase.reported", label=slot_label, state=new_state)
        except Exception as exc:
            log.error("supabase.report_failed", label=slot_label, error=str(exc))
