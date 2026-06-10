"""Structured English pipeline logs for AI Daily agents (Agent1–Agent5).

Human-readable Markdown is the committed format; a gitignored ``*.pipeline.json``
state file supports resume within the same CI run.
"""

from __future__ import annotations

import json
import os
import re
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

EXPECTED_MIN_PUBLISHED_ITEMS = 15

WORKFLOW_FILE = ".github/workflows/daily-pipeline.yml"
WORKFLOW_NAME = "AI Daily Pipeline"
WORKFLOW_JOB = "pipeline"
WORKFLOW_CRON_UTC = "0 1 * * *"
WORKFLOW_CRON_BEIJING = "~09:00 Asia/Shanghai (UTC+8)"
WORKFLOW_BRIEF_DATE_RULE = "Scheduled: yesterday in Asia/Shanghai; manual: `date` input or same default"
DEPLOY_WORKFLOW_FILE = ".github/workflows/deploy-pages.yml"
DEPLOY_WORKFLOW_NAME = "Deploy AI Daily to GitHub Pages"
DEPLOY_TRIGGER = "after AI Daily Pipeline completes, push to `main` (site paths), or workflow_dispatch (no cron)"

# Per-component metadata: GitHub step, script, I/O paths, tools/secrets.
STEP_CATALOG: dict[str, dict[str, Any]] = {
    "techmeme_fetcher": {
        "agent": "agent1",
        "action": "Fetch Techmeme RSS newsletter and extract structured sections",
        "github_step": "Fetch Techmeme",
        "script": "Daily_Parser/techmeme_fetcher.py",
        "command": "python3 Daily_Parser/techmeme_fetcher.py --date {date}",
        "input_files": [
            "Techmeme Mailchimp RSS (external feed)",
        ],
        "output_files": [
            "Daily_Parser/Techmeme/techmeme_{date}.json",
        ],
        "tools": "feedparser, beautifulsoup4; GitHub Actions: checkout@v4, setup-python@v5",
        "secrets": "none",
    },
    "tldr_fetcher": {
        "agent": "agent1",
        "action": "Fetch TLDR AI RSS feed and extract news items",
        "github_step": "Fetch TLDR AI",
        "script": "Daily_Parser/tldr_fetcher.py",
        "command": "python3 Daily_Parser/tldr_fetcher.py --date {date}",
        "input_files": [
            "TLDR AI RSS feed (external)",
        ],
        "output_files": [
            "Daily_Parser/TLDR/tldr_ai_{date}.json",
        ],
        "tools": "feedparser, beautifulsoup4; GitHub Actions: checkout@v4, setup-python@v5",
        "secrets": "none",
    },
    "merge_cleaner": {
        "agent": "agent2",
        "action": "Merge Techmeme and TLDR sources, dedupe, and write blocks/mapping/prompt",
        "github_step": "Merge & clean (Agent2)",
        "script": "Daily_Parser/merge_cleaner.py",
        "command": "python3 Daily_Parser/merge_cleaner.py --date {date}",
        "input_files": [
            "Daily_Parser/Techmeme/techmeme_{date}.json",
            "Daily_Parser/TLDR/tldr_ai_{date}.json",
        ],
        "output_files": [
            "Daily_Parser/Processed/{month}/blocks_{date}.json",
            "Daily_Parser/Processed/{month}/mapping_{date}.json",
            "Daily_Parser/Processed/{month}/prompt_{date}.txt",
        ],
        "tools": "stdlib json; GitHub Actions: checkout@v4, setup-python@v5",
        "secrets": "none",
    },
    "filter_scorer": {
        "agent": "agent3",
        "action": "Score and filter merged blocks with LLM (keep by threshold)",
        "github_step": "Filter score (Agent3)",
        "script": "Daily_Parser/filter_scorer.py",
        "command": "python3 Daily_Parser/filter_scorer.py --date {date}",
        "input_files": [
            "Daily_Parser/Processed/{month}/blocks_{date}.json",
        ],
        "output_files": [
            "Daily_Parser/Processed/{month}/filter_{date}.json",
        ],
        "tools": "GitHub Models API via common/llm.py (model: mini)",
        "secrets": "GH_MODELS_TOKEN, GITHUB_TOKEN",
    },
    "enrich": {
        "agent": "agent4",
        "action": "Translate, categorize, and tag filtered items via LLM",
        "github_step": "Enrich translate (Agent4)",
        "script": "Daily_Parser/enrich.py",
        "command": "python3 Daily_Parser/enrich.py --date {date}",
        "input_files": [
            "Daily_Parser/Processed/{month}/blocks_{date}.json",
            "Daily_Parser/Processed/{month}/mapping_{date}.json",
            "Daily_Parser/Processed/{month}/filter_{date}.json",
        ],
        "output_files": [
            "Daily_Parser/Processed/{month}/processed_{date}.json",
        ],
        "tools": "GitHub Models API via common/llm.py (model: default)",
        "secrets": "GH_MODELS_TOKEN, GITHUB_TOKEN",
    },
    "build_site_data": {
        "agent": "agent5",
        "action": "Sync processed brief to site/data and rebuild monthly aggregates + manifest",
        "github_step": "Build site data (Agent5)",
        "script": "Daily_Parser/build_site_data.py",
        "command": "python3 Daily_Parser/build_site_data.py --date {date}",
        "input_files": [
            "Daily_Parser/Processed/{month}/processed_{date}.json",
            "Daily_Parser/Processed/{month}/filter_{date}.json (optional copy)",
        ],
        "output_files": [
            "Daily_Parser/site/data/daily/{date}.json",
            "Daily_Parser/site/data/filter-report/{date}.json",
            "Daily_Parser/site/data/monthly/{month}.json",
            "Daily_Parser/site/data/manifest.json",
        ],
        "tools": "stdlib json/shutil; GitHub Actions: checkout@v4, setup-python@v5",
        "secrets": "none",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_run_id() -> str:
    gh_run = os.environ.get("GITHUB_RUN_ID")
    if gh_run:
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        return f"gh-{gh_run}-{attempt}"
    return f"local-{utc_now_iso()}"


def _fmt_paths(paths: list[str], brief_date: str) -> list[str]:
    month = brief_date[:7]
    return [p.format(date=brief_date, month=month) for p in paths]


def _catalog_for(component: str, brief_date: str) -> dict[str, Any]:
    base = STEP_CATALOG.get(component, {})
    if not base:
        return {}
    out = dict(base)
    out["input_files"] = _fmt_paths(list(base.get("input_files") or []), brief_date)
    out["output_files"] = _fmt_paths(list(base.get("output_files") or []), brief_date)
    out["command"] = (base.get("command") or "").format(date=brief_date, month=brief_date[:7])
    return out


def _status_badge(status: str) -> str:
    return f"**{status}**"


def _escape_cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text


def _metrics_volume(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "—"
    parts = [f"{k}={v}" for k, v in metrics.items()]
    return ", ".join(parts)


_PIPELINE_COMPONENT_ORDER = [
    "techmeme_fetcher",
    "tldr_fetcher",
    "merge_cleaner",
    "filter_scorer",
    "enrich",
    "build_site_data",
]


def _workflow_plan_rows(brief_date: str) -> list[list[str]]:
    """Canonical GitHub Actions step order (pipeline workflow only)."""
    prep = [
        ["—", "Resolve target date", "(workflow shell)", "—", f"Sets brief date (this run: `{brief_date}`)"],
        ["—", "Install dependencies", "`pip install -r Daily_Parser/requirements.txt`", "—", "Once per job"],
    ]
    agent_rows = []
    for comp in _PIPELINE_COMPONENT_ORDER:
        meta = STEP_CATALOG[comp]
        agent_rows.append(
            [
                str(meta.get("agent", "")),
                str(meta.get("github_step", "")),
                f"`{meta.get('script', '')}`",
                str(meta.get("secrets", "none")),
                str(meta.get("action", "")),
            ]
        )
    tail = [
        ["—", "Finalize pipeline log", "`Daily_Parser/finalize_pipeline_log.py`", "—", "Writes this Markdown log + index"],
        ["—", "Commit pipeline outputs", "`git add` + commit + push", "—", "Techmeme, TLDR, Processed, site/data, logs"],
    ]
    return prep + agent_rows + tail


def render_pipeline_markdown(data: dict[str, Any]) -> str:
    brief_date = data.get("brief_date", "")
    steps = data.get("steps") or []
    anomalies = _collect_anomalies(data)

    lines: list[str] = [
        f"# AI Daily Pipeline Log — {brief_date}",
        "",
        "## Run overview",
        "",
        "| Key | Value |",
        "|-----|-------|",
        f"| Brief date | `{brief_date}` |",
        f"| Run ID | `{data.get('run_id', '')}` |",
        f"| Overall status | {_status_badge(data.get('overall_status', 'running'))} |",
        f"| Pipeline started | {data.get('pipeline_started_at') or '—'} |",
        f"| Pipeline finished | {data.get('pipeline_finished_at') or '—'} |",
        f"| Expected min published items | {EXPECTED_MIN_PUBLISHED_ITEMS} |",
        "",
        "## GitHub automation",
        "",
        "### Schedules (what runs automatically)",
        "",
        "| Workflow | File | Trigger | Purpose |",
        "|----------|------|---------|---------|",
        f"| `{WORKFLOW_NAME}` | `{WORKFLOW_FILE}` | **Cron** `{WORKFLOW_CRON_UTC}` UTC ({WORKFLOW_CRON_BEIJING}) **or** `workflow_dispatch` | Fetch → process → commit one brief date |",
        f"| `{DEPLOY_WORKFLOW_NAME}` | `{DEPLOY_WORKFLOW_FILE}` | {DEPLOY_TRIGGER} | Publish `Daily_Parser/site` to GitHub Pages (`/cursor/ai_daily/`) |",
        "",
        f"**Brief date rule**: {WORKFLOW_BRIEF_DATE_RULE}.",
        "",
        "Only **one** cron exists (`daily-pipeline.yml`). Agent steps below are **sequential steps inside that single job**, not separate timers.",
        "",
        "### Pipeline workflow — step order",
        "",
        "| Agent | GitHub Actions step | Script | Secrets | Action |",
        "|-------|---------------------|--------|---------|--------|",
    ]
    for row in _workflow_plan_rows(brief_date):
        lines.append("| " + " | ".join(_escape_cell(c) for c in row) + " |")

    lines.extend(["", "## Anomalies", ""])
    if anomalies:
        for item in anomalies:
            lines.append(f"- {item}")
    else:
        lines.append("_None detected._")
    lines.extend(
        [
            "",
            "## Step summary",
            "",
            "| # | GitHub step | Agent | Status | Duration | Volume | Result |",
            "|---|-------------|-------|--------|----------|--------|--------|",
        ]
    )
    for step in steps:
        ctx = step.get("context") or {}
        metrics = step.get("metrics") or {}
        result = step.get("result") or "—"
        if step.get("error"):
            result = f"{result} — ERROR: {step['error']}"
        lines.append(
            "| {order} | {gh_step} | {agent} | {status} | {dur} | {vol} | {result} |".format(
                order=step.get("step_order"),
                gh_step=ctx.get("github_step") or step.get("component"),
                agent=step.get("agent"),
                status=step.get("status"),
                dur=f"{step.get('duration_ms')} ms" if step.get("duration_ms") is not None else "—",
                vol=_escape_cell(_metrics_volume(metrics)),
                result=_escape_cell(result),
            )
        )

    return "\n".join(lines).rstrip() + "\n"


def render_index_markdown(index: dict[str, Any]) -> str:
    dated_keys = sorted(k for k in index.keys() if not str(k).startswith("_"))
    lines = [
        "# AI Daily Pipeline Index",
        "",
        "Roll-up of completed pipeline runs. Open a date link for the full step-by-step log.",
        "",
        "| Brief date | Status | Published | Steps | Anomalies | Log |",
        "|------------|--------|-----------|-------|-----------|-----|",
    ]
    for key in reversed(dated_keys):
        entry = index[key]
        anomalies = entry.get("anomalies") or []
        anomaly_cell = _escape_cell("; ".join(anomalies)) if anomalies else "—"
        rel = entry.get("log_path", "")
        link = f"[{key}]({rel})" if rel else key
        published = entry.get("published_items")
        pub_cell = str(published) if published is not None else "—"
        lines.append(
            f"| `{key}` | {entry.get('overall_status', '—')} | {pub_cell} | "
            f"{entry.get('step_count', '—')} | {anomaly_cell} | {link} |"
        )
    latest = index.get("_latest")
    if latest:
        lines.extend(["", f"_Latest brief date: `{latest}`_"])
    lines.append("")
    return "\n".join(lines)


def _collect_anomalies(data: dict[str, Any]) -> list[str]:
    steps = data.get("steps") or []
    anomalies: list[str] = []
    for step in steps:
        if step.get("status") == STATUS_FAILED and step.get("error"):
            anomalies.append(f"{step.get('component')}: {step['error']}")
        elif step.get("status") == STATUS_WARNING:
            anomalies.append(f"{step.get('component')}: {step.get('result')}")
        elif step.get("status") == STATUS_SKIPPED:
            anomalies.append(f"{step.get('component')}: skipped — {step.get('result')}")
    published = 0
    for step in reversed(steps):
        if step.get("agent") == "agent5" and step.get("metrics"):
            published = int(step["metrics"].get("published_items") or 0)
            break
    if published and published < EXPECTED_MIN_PUBLISHED_ITEMS:
        anomalies.append(
            f"Low published volume: {published} items (expected >= {EXPECTED_MIN_PUBLISHED_ITEMS})"
        )
    return anomalies


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
    """Pipeline run log for one brief date (YYYY-MM-DD). Commits Markdown; uses JSON state locally."""

    def __init__(self, brief_date: str) -> None:
        self.brief_date = brief_date
        self.month = brief_date[:7]
        self.log_dir = LOG_ROOT / self.month
        self.log_path = self.log_dir / f"{brief_date}.md"
        self.state_path = self.log_dir / f"{brief_date}.pipeline.json"
        self.index_path = LOG_ROOT / "index.md"
        self.run_id = current_run_id()
        self.data = self._load_or_create()

    def _load_or_create(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
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
        comp = component or agent
        catalog = _catalog_for(comp, self.brief_date)
        order = self._next_step_order()
        record: dict[str, Any] = {
            "step_order": order,
            "agent": catalog.get("agent") or agent,
            "component": comp,
            "action": catalog.get("action") or action,
            "context": catalog,
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
        self.state_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.log_path.write_text(render_pipeline_markdown(self.data), encoding="utf-8")
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
        anomalies = _collect_anomalies(self.data)
        rel_log = f"{self.month}/{self.brief_date}.md"
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
            "log_path": rel_log,
        }
        index: dict[str, Any] = {}
        if self.index_path.exists():
            index = _parse_index_md(self.index_path)
        index[self.brief_date] = entry
        dated_keys = sorted(k for k in index.keys() if not str(k).startswith("_"))
        index["_latest"] = dated_keys[-1] if dated_keys else None
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(render_index_markdown(index), encoding="utf-8")

    @staticmethod
    def print_summary(log_path: Path) -> int:
        """Print human-readable summary from Markdown log; return exit code."""
        if not log_path.exists():
            print(f"Pipeline log not found: {log_path}", file=sys.stderr)
            return 1
        text = log_path.read_text(encoding="utf-8")
        print(text)
        match = re.search(r"\| Overall status \| \*\*(\w+)\*\* \|", text)
        status = match.group(1) if match else ""
        return 0 if status == STATUS_SUCCESS else 1


def _parse_index_md(path: Path) -> dict[str, Any]:
    """Best-effort parse of index.md back to dict (for incremental updates)."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    index: dict[str, Any] = {}
    row_re = re.compile(
        r"^\| `(?P<date>\d{4}-\d{2}-\d{2})` \| (?P<status>\w+) \| (?P<published>[^|]+) \| "
        r"(?P<steps>\d+) \| (?P<anomalies>[^|]+) \| \[(?P=date)\]\((?P<log_path>[^)]+)\) \|"
    )
    for line in text.splitlines():
        m = row_re.match(line.strip())
        if not m:
            continue
        pub = m.group("published").strip()
        anomalies_raw = m.group("anomalies").strip()
        anomalies = [] if anomalies_raw == "—" else [a.strip() for a in anomalies_raw.split(";")]
        index[m.group("date")] = {
            "brief_date": m.group("date"),
            "overall_status": m.group("status"),
            "published_items": None if pub == "—" else int(pub),
            "step_count": int(m.group("steps")),
            "anomalies": anomalies,
            "log_path": m.group("log_path"),
        }
    latest_m = re.search(r"_Latest brief date: `(?P<date>\d{4}-\d{2}-\d{2})`_", text)
    if latest_m:
        index["_latest"] = latest_m.group("date")
    return index


def load_log_data(brief_date: str) -> dict[str, Any] | None:
    """Load pipeline data from state JSON, legacy JSON, or regenerate from MD is not supported."""
    month = brief_date[:7]
    state = LOG_ROOT / month / f"{brief_date}.pipeline.json"
    legacy = LOG_ROOT / month / f"{brief_date}.json"
    for path in (state, legacy):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return None


def write_log_from_data(data: dict[str, Any], *, update_index: bool = True) -> Path:
    """Render and write Markdown (+ state JSON) from structured data."""
    brief_date = data["brief_date"]
    month = brief_date[:7]
    log_dir = LOG_ROOT / month
    log_dir.mkdir(parents=True, exist_ok=True)
    state_path = log_dir / f"{brief_date}.pipeline.json"
    log_path = log_dir / f"{brief_date}.md"
    for step in data.get("steps") or []:
        comp = step.get("component") or ""
        if not step.get("context"):
            step["context"] = _catalog_for(comp, brief_date)
        if comp in STEP_CATALOG and not step.get("action"):
            step["action"] = STEP_CATALOG[comp]["action"]
    if not data.get("overall_status") or data.get("overall_status") == "running":
        steps = data.get("steps") or []
        if any(s.get("status") == STATUS_FAILED for s in steps):
            data["overall_status"] = STATUS_FAILED
        elif any(s.get("status") in (STATUS_WARNING, STATUS_SKIPPED) for s in steps):
            data["overall_status"] = STATUS_WARNING
        elif steps:
            data["overall_status"] = STATUS_SUCCESS
    state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_path.write_text(render_pipeline_markdown(data), encoding="utf-8")
    if update_index:
        logger = PipelineLogger(brief_date)
        logger.data = data
        logger._update_index()
    return log_path


def finalize_pipeline_log(brief_date: str) -> int:
    data = load_log_data(brief_date)
    if data:
        if not data.get("pipeline_finished_at"):
            data["pipeline_finished_at"] = utc_now_iso()
        if not data.get("overall_status") or data.get("overall_status") == "running":
            steps = data.get("steps") or []
            if any(s.get("status") == STATUS_FAILED for s in steps):
                data["overall_status"] = STATUS_FAILED
            elif any(s.get("status") in (STATUS_WARNING, STATUS_SKIPPED) for s in steps):
                data["overall_status"] = STATUS_WARNING
            elif steps:
                data["overall_status"] = STATUS_SUCCESS
        write_log_from_data(data)
        log_path = LOG_ROOT / brief_date[:7] / f"{brief_date}.md"
    else:
        logger = PipelineLogger(brief_date)
        logger.finish()
        log_path = logger.log_path
    return PipelineLogger.print_summary(log_path)
