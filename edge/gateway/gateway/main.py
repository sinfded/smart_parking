"""Gateway entry point — wires MQTT listener → debouncer → Supabase writer."""

import asyncio
import structlog

from .config import settings
from .mqtt_listener import MQTTListener
from .debouncer import Debouncer
from .supabase_writer import SupabaseWriter
from .health_reporter import HealthReporter

log = structlog.get_logger()


async def run() -> None:
    log.info("gateway.starting", lot_id=settings.lot_id)

    writer   = SupabaseWriter(settings)
    await writer.authenticate()

    debouncer = Debouncer(settings, on_state_change=writer.report_slot_state)
    health    = HealthReporter(settings, writer)
    listener  = MQTTListener(settings, debouncer, health)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(listener.run())
        tg.create_task(health.run())


def main() -> None:
    import logging
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
    asyncio.run(run())


if __name__ == "__main__":
    main()
