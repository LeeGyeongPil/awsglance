"""스케줄러 — 스레드 1개가 작업(인벤토리·CloudTrail·보존 정리)을 주기마다 차례로 실행한다.

- 스레드가 하나라 같은 작업이 겹쳐 돌 수 없다(동시 실행 방지). run_now() 로 수동 실행을 요청해도
  같은 스레드가 처리한다.
- 모든 실행은 runs 표에 시작·끝·결과·오류·호출 수를 남긴다. 기동 시 지난 프로세스의 '실행 중' 고아 기록은 '중단됨'으로 닫는다.
- stop() 은 대기 중인 스레드를 깨워 끝내고 join 한다(종료 경로에서 자원 해제).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .store import Store, now_utc

log = logging.getLogger("awsglance.scheduler")


@dataclass
class Job:
    name: str
    every_seconds: float
    fn: Callable[[], dict]        # 요약 dict 를 돌려준다(오류 목록은 "errors" 키)
    next_at: float = 0.0          # time.monotonic() 기준. 0 이면 바로 실행


class Scheduler:
    def __init__(self, store: Store, jobs: list[Job], tick: float = 1.0) -> None:
        self.store = store
        self.jobs = {j.name: j for j in jobs}
        self.tick = tick
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.running: str | None = None

    def start(self) -> None:
        self.store.abort_orphan_runs(now_utc())
        self._thread = threading.Thread(target=self._loop, name="awsglance-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def run_now(self, name: str) -> None:
        self.jobs[name].next_at = 0.0
        self._wake.set()

    def run_job(self, job: Job) -> None:
        run_id = self.store.start_run(job.name, now_utc())
        self.running = job.name
        try:
            summary = job.fn() or {}
            errors = summary.get("errors") or []
            status = "partial" if errors else "ok"
            error = "; ".join(f"{e.get('collector', '')}@{e.get('region', '')}: {e.get('error')}" for e in errors)[:2000]
            self.store.finish_run(run_id, status, now_utc(), calls=int(summary.get("calls", 0)),
                                  error=error or None, summary=summary)
        except Exception as exc:  # 한 작업이 실패해도 스케줄러는 계속 돈다
            log.exception("job %s failed", job.name)
            self.store.finish_run(run_id, "error", now_utc(), error=f"{type(exc).__name__}: {exc}"[:2000])
        finally:
            self.running = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            for job in list(self.jobs.values()):
                if self._stop.is_set():
                    break
                if time.monotonic() >= job.next_at:
                    self.run_job(job)
                    job.next_at = time.monotonic() + job.every_seconds
            self._wake.wait(self.tick)
            self._wake.clear()
