"""Subscribes to the lot's MQTT topics and routes messages to the debouncer."""

import json
import structlog
import aiomqtt

from .config import Settings

log = structlog.get_logger()


class MQTTListener:
    def __init__(self, settings: Settings, debouncer: "Debouncer", health: "HealthReporter") -> None:  # noqa: F821
        self._s        = settings
        self._debouncer = debouncer
        self._health   = health

    async def run(self) -> None:
        topic_state  = f"parking/{self._s.lot_id}/slot/+/state"
        topic_health = f"parking/{self._s.lot_id}/device/+/health"

        async with aiomqtt.Client(self._s.mqtt_broker_host, self._s.mqtt_broker_port) as client:
            await client.subscribe(topic_state)
            await client.subscribe(topic_health)
            log.info("mqtt.subscribed", lot_id=self._s.lot_id)

            async for message in client.messages:
                topic = str(message.topic)
                try:
                    payload = json.loads(message.payload)
                except Exception:
                    continue

                parts = topic.split("/")
                if len(parts) == 5 and parts[2] == "slot" and parts[4] == "state":
                    slot_label = parts[3]
                    await self._debouncer.handle(slot_label, payload)
                elif len(parts) == 5 and parts[2] == "device" and parts[4] == "health":
                    mac = parts[3]
                    await self._health.handle_device(mac, payload)
