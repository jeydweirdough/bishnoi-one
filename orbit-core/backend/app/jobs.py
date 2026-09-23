"""Bulk work, queued.

A bulk action (mark 80 follow-ups done, raise 300 prices) is accepted at once
with 202 and a job, then worked through in the background by one worker per
process, in batches. A job that fits in one batch is simply done within the
request. Each batch is one round trip to the store, and the worker
pauses between batches, so a big job never floods the records store's own rate
limits (Sanity's API) or starves everyone else's requests. The page asks for
the job's progress until it's done.

Each item is checked on its own against the person's access; the ones they
can't touch, or that someone changed meanwhile, are reported back by id with a
reason, never dropped silently.

Jobs live in memory, per process, for an hour after they finish. With several
API processes, a job is only visible to the one that took it; move the queue to
Redis (or a proper task queue) then.
"""

import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger("crm.jobs")

# (item id, None when done, or why it wasn't)
Outcome = tuple[str, str | None]
Work = Callable[[list[str]], list[Outcome]]
KEEP_SECONDS = 3600


@dataclass
class Job:
    id: str
    owner_id: str
    label: str
    items: list[str]
    work: Work
    batch_size: int
    status: str = "queued"  # queued | running | done
    processed: int = 0
    failures: list[dict] = field(default_factory=list)
    finished_at: float | None = None

    def out(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "total": len(self.items),
            "processed": self.processed,
            "succeeded": self.processed - len(self.failures),
            "failed": len(self.failures),
            "failures": self.failures[:50],
        }


class JobQueue:
    def __init__(self, batch_size: int = 50, pause_seconds: float = 0.2, inline: bool = False) -> None:
        self.batch_size = batch_size
        self.pause_seconds = pause_seconds
        # Inline runs each job inside submit(): for tests, where waiting on a thread is noise.
        self.inline = inline
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[Job] = queue.Queue()
        self._worker: threading.Thread | None = None

    def submit(self, owner_id: str, label: str, items: list[str], work: Work, batch_size: int | None = None) -> Job:
        """Queues the work, or does it right away when it fits in one batch:
        then the answer already says "done" and the page needn't wait on it."""
        job = Job(uuid.uuid4().hex, owner_id, label, list(dict.fromkeys(items)), work, batch_size or self.batch_size)
        with self._lock:
            self._forget_old()
            self._jobs[job.id] = job
        log.info("job %s for %s: %s (%d items)", job.id, owner_id, label, len(job.items))
        if self.inline or len(job.items) <= job.batch_size:
            self._run(job)
        else:
            self._queue.put(job)
            self._start_worker()
        return job

    def get(self, job_id: str, owner_id: str) -> Job | None:
        """Only the person who started a job can read it."""
        job = self._jobs.get(job_id)
        return job if job and job.owner_id == owner_id else None

    def _start_worker(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._loop, name="bulk-jobs", daemon=True)
                self._worker.start()

    def _loop(self) -> None:
        while True:
            self._run(self._queue.get())

    def _run(self, job: Job) -> None:
        job.status = "running"
        for start in range(0, len(job.items), job.batch_size):
            batch = job.items[start : start + job.batch_size]
            try:
                outcomes = job.work(batch)
            except Exception:  # one bad batch mustn't take the worker down
                log.exception("job %s: a batch failed", job.id)
                outcomes = [(item, "Something went wrong with this one; try it again.") for item in batch]
            for item, error in outcomes:
                if error:
                    job.failures.append({"id": item, "error": error})
            job.processed += len(batch)
            if not self.inline and self.pause_seconds and job.processed < len(job.items):
                time.sleep(self.pause_seconds)
        job.status = "done"
        job.finished_at = time.time()
        log.info("job %s done: %d of %d succeeded", job.id, job.processed - len(job.failures), len(job.items))

    def _forget_old(self) -> None:
        now = time.time()
        for key in [k for k, j in self._jobs.items() if j.finished_at and now - j.finished_at > KEEP_SECONDS]:
            del self._jobs[key]
