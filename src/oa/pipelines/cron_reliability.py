"""G1: Cron Reliability Pipeline — tracks cron job success rates."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

DATA_FLOW_EDGES = [
    {"from": "jobs.json", "to": "collect_cron.py", "type": "config"},
    {"from": "runs/*.jsonl", "to": "collect_cron.py", "type": "data"},
    {"from": "collect_cron.py", "to": "Compute Rate", "type": "process"},
    {"from": "Compute Rate", "to": "goal_metrics", "type": "write"},
    {"from": "Compute Rate", "to": "cron_runs", "type": "write"},
]
NODE_TYPES = {
    "jobs.json": "source",
    "runs/*.jsonl": "source",
    "collect_cron.py": "script",
    "Compute Rate": "script",
    "goal_metrics": "db",
    "cron_runs": "db",
}


class CronReliabilityPipeline(Pipeline):
    """Built-in pipeline: reads OpenClaw cron JSONL logs and computes success rates."""

    goal_id = "cron_reliability"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer

        cron_dir = config.openclaw_home / "cron"
        jobs_file = cron_dir / "jobs.json"
        runs_dir = cron_dir / "runs"
        tracer = Tracer(service="g1_cron_reliability", db_path=config.db_path)

        with tracer.span("G1: Cron Reliability", {
            "goal": "G1", "date": date,
            "data_flow_edges": DATA_FLOW_EDGES,
            "node_types": NODE_TYPES,
        }) as root:

            with tracer.span("Read jobs.json", {
                "step": "read_config", "source": str(jobs_file),
                "db.operation": "read", "db.table": "jobs.json",
            }) as s1:
                if not jobs_file.exists():
                    s1.set_status("error", "jobs.json not found")
                    root.set_status("error", "jobs.json not found")
                    tracer.flush()
                    return [Metric("success_rate", 0, "%")]

                with open(jobs_file, encoding="utf-8") as f:
                    jobs_data = json.load(f)
                jobs = jobs_data.get("jobs", [])
                enabled_jobs = [
                    j for j in jobs
                    if j.get("enabled", True) and j.get("schedule", {}).get("kind") == "cron"
                ]
                s1.set_attribute("total_jobs", len(jobs))
                s1.set_attribute("enabled_jobs", len(enabled_jobs))
                s1.set_attribute("job_names", [j.get("name", j.get("id")) for j in enabled_jobs])

            with tracer.span("Scan JSONL Runs", {
                "step": "read_runs", "source": str(runs_dir),
            }) as s2:
                per_job: dict[str, dict] = {}
                total_lines_scanned = 0

                for job in enabled_jobs:
                    job_id = job.get("id", "unknown")
                    job_name = job.get("name", job_id)

                    with tracer.span(f"Read {job_name}", {"job_id": job_id}) as sj:
                        runs = self._read_runs_jsonl(runs_dir, job_id, date)
                        total_lines_scanned += len(runs)

                        success = sum(1 for r in runs if r.get("status") in ("ok", "completed", "success"))
                        failed = sum(1 for r in runs if r.get("status") in ("failed", "error"))
                        total = len(runs)

                        per_job[job_name] = {
                            "job_id": job_id, "total": total,
                            "success": success, "failed": failed,
                            "rate": round(success / total * 100, 1) if total > 0 else 0,
                        }
                        sj.set_attribute("runs_found", total)
                        sj.set_attribute("success", success)
                        sj.set_attribute("failed", failed)

                s2.set_attribute("jobs_scanned", len(enabled_jobs))
                s2.set_attribute("total_lines", total_lines_scanned)

            with tracer.span("Compute Rate", {"step": "compute"}) as s3:
                total_runs = sum(d["total"] for d in per_job.values())
                total_success = sum(d["success"] for d in per_job.values())
                success_rate = round(total_success / total_runs * 100, 1) if total_runs > 0 else 100.0
                s3.set_attribute("success_rate", success_rate)
                s3.set_attribute("total_runs", total_runs)
                s3.set_attribute("total_success", total_success)

            with tracer.span("Write cron_runs DB", {
                "step": "store", "db.operation": "write", "db.table": "cron_runs",
            }) as s4:
                self._write_cron_runs(config.db_path, date, per_job)
                s4.set_attribute("rows_written", len(per_job))

            root.set_attribute("success_rate", success_rate)
            root.set_attribute("jobs_processed", len(per_job))

        tracer.flush()
        return [Metric(
            "success_rate", success_rate, unit="%",
            breakdown={"per_job": per_job, "total_runs": total_runs},
        )]

    def _read_runs_jsonl(self, runs_dir: Path, job_id: str, date: str) -> list[dict]:
        jsonl_file = runs_dir / f"{job_id}.jsonl"
        if not jsonl_file.exists():
            return []
        runs = []
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts") or entry.get("runAtMs")
                        if ts:
                            dt = datetime.fromtimestamp(ts / 1000)
                            if dt.strftime("%Y-%m-%d") == date:
                                runs.append(entry)
                        else:
                            started = entry.get("startedAt", "")
                            if started.startswith(date):
                                runs.append(entry)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return runs

    def _write_cron_runs(self, db_path: Path, date: str, per_job: dict) -> None:
        db = sqlite3.connect(str(db_path))
        db.execute("PRAGMA journal_mode=WAL")
        for job_name, data in per_job.items():
            db.execute(
                "INSERT INTO cron_runs (date, cron_name, status, job_id, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (date, job_name, "success" if data["rate"] >= 80 else "failed", data.get("job_id", "")),
            )
        db.commit()
        db.close()
