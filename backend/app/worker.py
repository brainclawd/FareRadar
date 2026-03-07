from __future__ import annotations

from time import sleep

from .tasks.scan_tasks import plan_and_dispatch_scans_task


def main() -> None:
    print("FareRadar scheduler loop started...")
    while True:
        result = plan_and_dispatch_scans_task.delay()
        print(f"queued scan planning task id={result.id}")
        sleep(60 * 15)


if __name__ == "__main__":
    main()
