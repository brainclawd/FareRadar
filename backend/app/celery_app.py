from __future__ import annotations

from celery import Celery

from .config import settings


broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery(
    "fareradar",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.tasks.scan_tasks",
        "app.tasks.validation_tasks",
        "app.tasks.alert_tasks",
    ],
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {
    "app.tasks.scan_tasks.scan_job_task": {"queue": "scanner"},
    "app.tasks.scan_tasks.plan_and_dispatch_scans_task": {"queue": "scheduler"},
    "app.tasks.validation_tasks.validate_candidate_deal_task": {"queue": "validator"},
    "app.tasks.alert_tasks.send_deal_alert_task": {"queue": "alerts"},
}
celery_app.conf.beat_schedule = {
    "plan-scan-jobs-every-15-minutes": {
        "task": "app.tasks.scan_tasks.plan_and_dispatch_scans_task",
        "schedule": 15 * 60,
    },
}
celery_app.conf.task_always_eager = settings.celery_task_always_eager
celery_app.conf.task_eager_propagates = settings.celery_task_eager_propagates
