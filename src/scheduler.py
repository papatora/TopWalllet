"""Cron scheduler — re-runs the full pipeline on PIPELINE_CRON (UTC) and lets
the export stage auto-push results to GitHub after each run."""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from src.utils.logger import jlog, setup_logging

log = logging.getLogger(__name__)


async def _run_pipeline_job() -> None:
    from src.pipeline import Pipeline

    jlog(log, logging.INFO, "scheduled pipeline starting")
    pipe = Pipeline()
    counts = await pipe.run()
    jlog(log, logging.INFO, "scheduled pipeline finished", **counts)


async def run_scheduler() -> None:
    setup_logging()
    trigger = CronTrigger.from_crontab(settings.pipeline_cron, timezone="UTC")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_pipeline_job, trigger, id="full_pipeline",
                      max_instances=1, coalesce=True)
    scheduler.start()
    jlog(log, logging.INFO, "scheduler up", cron=settings.pipeline_cron)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
