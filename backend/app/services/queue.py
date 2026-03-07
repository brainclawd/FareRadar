from __future__ import annotations

from dataclasses import dataclass

from ..celery_app import celery_app
from ..tasks.alert_tasks import send_deal_alert_task
from ..tasks.scan_tasks import scan_job_task
from ..tasks.validation_tasks import validate_candidate_deal_task


@dataclass
class QueuePublishSummary:
    queued_jobs: int = 0
    queued_alerts: int = 0


class QueuePublisher:
    def publish_scan_job(self, job_id: int) -> None:
        scan_job_task.delay(job_id)

    def publish_alert(self, deal_alert_id: int) -> None:
        send_deal_alert_task.delay(deal_alert_id)

    def publish_validation(self, candidate_deal_id: int) -> None:
        validate_candidate_deal_task.delay(candidate_deal_id)


publisher = QueuePublisher()
