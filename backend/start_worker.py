"""Celery worker startup script.

Run this separately from the FastAPI app to handle background tasks:
    python start_worker.py

This keeps the FastAPI app lightweight and fast.
"""
import sys
import platform
from app.worker import celery_app

if __name__ == "__main__":
    # Use solo pool on Windows to avoid permission errors
    # Windows doesn't support prefork multiprocessing properly
    if platform.system() == "Windows":
        celery_app.worker_main([
            "worker",
            "--loglevel=info",
            "--pool=solo",
        ])
    else:
        celery_app.worker_main([
            "worker",
            "--loglevel=info",
            "--concurrency=2",
        ])
