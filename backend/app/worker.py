"""Celery worker configuration for background task processing."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "pr_guardian",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    # Beat schedule - used by celery beat process (separate from worker on Windows)
    # Automatically detects and recovers stuck PRs at any layer
    # Polls for new PRs every 5 seconds
    beat_schedule={
        'poll-new-prs': {
            'task': 'poll_new_prs',
            'schedule': 5.0,  # Run every 5 seconds
        },
        'retry-failed-prs': {
            'task': 'retry_failed_prs',
            'schedule': 5.0,  # Run every 5 seconds
        },
    },
)

# Import tasks to register them with Celery
from app import tasks  # noqa: F401
