"""Structured English pipeline logs for AI Daily agents (Agent1–Agent5)."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

LOG_ROOT = Path(__file__).resolve().parent.parent / "logs" / "pipeline"

STATUS_SUCCESS = "success"
STATUS_WARNING = "warning"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

# Heuristic for daily brief volume monitoring
EXPECTED_MIN_PUBLISHED_ITEMS = 15


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_run_id() -> str:
    gh_run = os.environ.get("GITHUB_RUN_ID")
    if gh_run:
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        return f"gh-{gh_run}-{attempt}"
    return f"local-{utc_now_iso()}"


class StepRecorder:
    """Mutable step record exposed inside `PipelineLogger.step()`."""

    def __init__(self, record: dict[str, Any]) -> None:
        self._record = record
        self.metrics: dict[str, Any] = {}

    def set_metrics(self, **kwargs: Any) -> None:
        self.metrics.update(kwargs)

    def success(self, message: str) -> None:
        self._record["result"] = message
        self._record["status"] = STATUS_SUCCESS

    def warn(self, message: str) -> None:
        self._record["result"] = message
        self._record["status"] = STATUS_WARNING

    def skip(self, message: str) -> None:
        self._record["result"] = message
        self._record["status"] = STATUS_SKIPPED


class PipelineLogger:
    """Append-only pipeline run log for one brief date (YYYY-MM-DD)."""

    def __init__(self, brief_date: str) -> None:
        self.brief_date = brief_date
        self.month = brief_date[:7]
        self.log_dir = LOG_ROOT / self.month
        self.log_path = self.log_dir / f"{brief_date}.json"
        self.index_path = LOG_ROOT / "index.json"
        self.run_id = current_run_id()
        self.data = self._load_or_create()

    def _load_or_create(self) -> dict[str, Any]:
        if self.log_path.exists():
            try:
                data = json.loads(self.log_path.read_text(encoding="utf-8"))
                if data.get("run_id") == self.run_id and data.get("brief_date") == self.brief_date:
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "brief_date": self.brief_date,
            "run_id": self.run_id,
            "pipeline_started_at": utc_now_iso(),
            "pipeline_finished_at": None,
            "overall_status": "running",
            "steps": [],
        }

    def _next_step_order(self) -> int:
        return len(self.data["steps"]) + 1

    @contextmanager
    def step(self, agent: str, action: str, component: str = "") -> Iterator[StepRecorder]:
        order = self._next_step_order()
        record: dict[str, Any] = {
            "step_order": order,
            "agent": agent,
            "component": component or agent,
            "action": action,
            "started_at": utc_now_iso(),
            "finished_at": None,
            "duration_ms": None,
            "metrics": {},
            "status": STATUS_SUCCESS,
            "result": "",
            "error": None,
        }
        recorder = StepRecorder(record)
        started = datetime.now(timezone.utc)
        failed = False
        try:
            yield recorder
        except Exception as exc:
            failed = True
            record["status"] = STATUS_FAILED
            record["error"] = f"{type(exc).__name__}: {exc}"
            if not record["result"]:
                record["result"] = "Step failed with exception"
            raise
        finally:
            finished = datetime.now(timezone.utc)
            record["finished_at"] = utc_now_iso()
            record["duration_ms"] = int((finished - started).total_seconds() * 1000)
            record["metrics"] = recorder.metrics
            if not record["result"]:
                record["result"] = "Completed"
            if not failed and recorder.metrics and record["status"] == STATUS_SUCCESS:
                pass
            self.data["steps"].append(record)
            self._save(partial=True)

    def finish(self, status: str | None = None) -> None:
        self.data["overall_status"] = status or self._derive_overall()
        self.data["pipeline_finished_at"] = utc_now_iso()
        self._save(partial=False)

    def _derive_overall(self) -> str:
        steps = self.data.get("steps") or []
        if not steps:
            return "running"
        if any(s.get("status") == STATUS_FAILED for s in steps):
            return STATUS_FAILED
        if any(s.get("status") in (STATUS_WARNING, STATUS_SKIPPED) for s in steps):
            return STATUS_WARNING
        return STATUS_SUCCESS

    def _save(self, partial: bool) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if not partial:
            self._update_index()

    def _update_index(self) -> None:
        steps = self.data.get("steps") or []
        last = steps[-1] if steps else {}
        published = 0
        for step in reversed(steps):
            if step.get("agent") == "agent5" and step.get("metrics"):
                published = int(step["metrics"].get("published_items") or 0)
                break
        anomalies: list[str] = []
        for step in steps:
            if step.get("status") == STATUS_FAILED and step.get("error"):
                anomalies.append(f"{step.get('component')}: {step['error']}")
            elif step.get("status") == STATUS_WARNING:
                anomalies.append(f"{step.get('component')}: {step.get('result')}")
        if published and published < EXPECTED_MIN_PUBLISHED_ITEMS:
            anomalies.append(
                f"Low published volume: {published} items (expected >= {EXPECTED_MIN_PUBLISHED_ITEMS})"
            )
        entry = {
            "brief_date": self.brief_date,
            "run_id": self.run_id,
            "overall_status": self.data.get("overall_status"),
            "pipeline_started_at": self.data.get("pipeline_started_at"),
            "pipeline_finished_at": self.data.get("pipeline_finished_at"),
            "step_count": len(steps),
            "last_component": last.get("component"),
            "published_items": published or None,
            "anomalies": anomalies,
            "log_path": str(self.log_path.relative_to(LOG_ROOT.parent.parent)),
        }
        index: dict[str, Any] = {}
        if self.index_path.exists():
            try:
                index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                index = {}
        index[self.brief_date] = entry
        dated_keys = sorted(k for k in index.keys() if not str(k).startswith("_"))
        index["_latest"] = dated_keys[-1] if dated_keys else None
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def print_summary(log_path: Path) -> int:
        """Print human-readable summary; return exit code (0 ok, 1 warning/fail)."""
        if not log_path.exists():
            print(f"Pipeline log not found: {log_path}", file=sys.stderr)
            return 1
        data = json.loads(log_path.read_text(encoding="utf-8"))
        print(f"Pipeline log — brief_date={data.get('brief_date')} run_id={data.get('run_id')}")
        print(f"Overall status: {data.get('overall_status')}  finished_at={data.get('pipeline_finished_at')}")
        print("Steps:")
        for step in data.get("steps") or []:
            line = (
                f"  [{step.get('step_order')}] {step.get('agent')} / {step.get('component')} — "
                f"{step.get('status')} ({step.get('duration_ms')} ms)"
            )
            print(line)
            print(f"      action: {step.get('action')}")
            if step.get("metrics"):
                print(f"      metrics: {json.dumps(step.get('metrics'), ensure_ascii=False)}")
            print(f"      result: {step.get('result')}")
            if step.get("error"):
                print(f"      error: {step.get('error')}")
        status = data.get("overall_status")
        return 0 if status == STATUS_SUCCESS else 1


def finalize_pipeline_log(brief_date: str) -> int:
    logger = PipelineLogger(brief_date)
    logger.finish()
    return PipelineLogger.print_summary(logger.log_path)
