from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

from app.settings import settings
from app.scheduler import daily_job
from app.datasource.sqlite_meta import upsert_job_status


def _on_event_update_status(event) -> None:  # type: ignore
    job_id = getattr(event, "job_id", None) or "daily_job"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = "ok" if not getattr(event, "exception", None) else "error"
    upsert_job_status(job_id, last_run=now_str, state=state, next_run=None)


async def main() -> None:
    scheduler = AsyncIOScheduler(jobstores={
        "default": SQLAlchemyJobStore(url=settings.database_url)
    }, timezone=settings.tz)

    # Daily job at 19:00 Asia/Shanghai
    scheduler.add_job(
        daily_job,
        id="daily_job",
        trigger=CronTrigger(hour=19, minute=0),
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Listeners update status table
    scheduler.add_listener(_on_event_update_status)

    scheduler.start()

    # seed next_run into status
    jobs = scheduler.get_jobs()
    for j in jobs:
        next_run = j.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if j.next_run_time else None
        upsert_job_status(j.id, last_run=None, state="scheduled", next_run=next_run)

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())


