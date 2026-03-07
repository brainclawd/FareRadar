from __future__ import annotations

from .tasks.scan_tasks import plan_and_dispatch_scans_task


def main() -> None:
    result = plan_and_dispatch_scans_task.delay()
    print(f"scheduled scan planning task id={result.id}")


if __name__ == "__main__":
    main()
