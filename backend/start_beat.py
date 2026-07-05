"""Celery beat startup script.

Run this separately from the FastAPI app and worker to handle scheduled tasks:
    python start_beat.py

This handles the retry_failed_prs task that runs every 5 seconds.
"""
from app.worker import celery_app

if __name__ == "__main__":
    celery_app.start([
        "beat",
        "--loglevel=info",
    ])
