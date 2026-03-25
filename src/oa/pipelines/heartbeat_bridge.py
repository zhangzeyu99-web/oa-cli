"""Heartbeat bridge — reads OpenClaw's HEARTBEAT.md, todo tracking, active sessions, and cron state."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

DATA_FLOW_EDGES = [
    {"from": "agents/*/sessions", "to": "check_alive.py", "type": "data"},
    {"from": "heartbeat-todo.md", "to": "parse_todos.py", "type": "data"},
    {"from": "HEARTBEAT.md", "to": "parse_todos.py", "type": "config"},
    {"from": "cron/jobs.json", "to": "check_cron.py", "type": "data"},
    {"from": "check_alive.py", "to": "Aggregate", "type": "process"},
    {"from": "parse_todos.py", "to": "Aggregate", "type": "process"},
    {"from": "check_cron.py", "to": "Aggregate", "type": "process"},
    {"from": "Aggregate", "to": "goal_metrics", "type": "write"},
]
NODE_TYPES = {
    "agents/*/sessions": "agent",
    "heartbeat-todo.md": "source",
    "HEARTBEAT.md": "source",
    "cron/jobs.json": "cron",
    "check_alive.py": "script",
    "parse_todos.py": "script",
    "check_cron.py": "script",
    "Aggregate": "script",
    "goal_metrics": "db",
}


class HeartbeatBridgePipeline(Pipeline):
    """Reads OpenClaw's native heartbeat system: HEARTBEAT.md + sessions + cron state."""

    goal_id = "heartbeat_status"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="heartbeat_bridge", db_path=config.db_path)
        oc_home = config.openclaw_home

        with tracer.span("Heartbeat Bridge", {
            "date": date,
            "data_flow_edges": DATA_FLOW_EDGES,
            "node_types": NODE_TYPES,
        }) as root:
            alive_agents = 0
            alive_names: list[str] = []
            total_agents = len(config.agents)
            todo_total = 0
            todo_done = 0
            todo_items: list[str] = []
            cron_ok = 0
            cron_total = 0
            cron_details: list[dict] = []

            with tracer.span("Check Agent Sessions", {
                "step": "scan", "source": str(oc_home / "agents"),
            }) as s1:
                agents_dir = oc_home / "agents"
                if agents_dir.exists():
                    for agent_cfg in config.agents:
                        sessions_dir = agents_dir / agent_cfg.id / "sessions"
                        if not sessions_dir.exists():
                            continue
                        found = False
                        session_count = 0
                        for sf in sessions_dir.iterdir():
                            if not sf.is_file() or sf.suffix != ".jsonl":
                                continue
                            try:
                                mtime = datetime.fromtimestamp(sf.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") == date:
                                    found = True
                                    session_count += 1
                            except OSError:
                                continue
                        if found:
                            alive_agents += 1
                            alive_names.append(agent_cfg.id)
                s1.set_attribute("alive_agents", alive_agents)
                s1.set_attribute("alive_names", alive_names)
                s1.set_attribute("total_agents", total_agents)

            with tracer.span("Read Todo Tracking", {
                "step": "read", "source": "heartbeat-todo-tracking.md",
            }) as s2:
                todo_paths = [
                    oc_home / "workspace" / "memory" / "heartbeat-todo-tracking.md",
                    oc_home / "workspace" / "HEARTBEAT.md",
                    oc_home / "xiaoxia-memory-repo" / "memory" / "heartbeat-todo-tracking.md",
                ]
                source_used = None
                for tp in todo_paths:
                    if tp.exists():
                        source_used = tp.name
                        try:
                            text = tp.read_text(encoding="utf-8")
                            for line in text.splitlines():
                                stripped = line.strip()
                                if re.match(r"^\|.*\|.*\|.*\|.*已完成.*\|", stripped) or "✅" in stripped:
                                    todo_total += 1
                                    todo_done += 1
                                    todo_items.append(f"[done] {stripped[:60]}")
                                elif re.match(r"^\|.*\|.*\|.*\|.*(待启动|进行中|待定).*\|", stripped) or "⏳" in stripped:
                                    todo_total += 1
                                    todo_items.append(f"[pending] {stripped[:60]}")
                                elif stripped.startswith("- [x]") or stripped.startswith("- [X]"):
                                    todo_total += 1
                                    todo_done += 1
                                elif stripped.startswith("- [ ]"):
                                    todo_total += 1
                        except OSError:
                            pass
                        break
                s2.set_attribute("source", source_used or "not found")
                s2.set_attribute("todo_total", todo_total)
                s2.set_attribute("todo_done", todo_done)
                s2.set_attribute("items_preview", todo_items[:5])

            with tracer.span("Check Cron Health", {
                "step": "read", "source": "cron/jobs.json",
                "db.operation": "read", "db.table": "jobs.json",
            }) as s3:
                jobs_file = oc_home / "cron" / "jobs.json"
                if jobs_file.exists():
                    try:
                        data = json.loads(jobs_file.read_text(encoding="utf-8"))
                        for job in data.get("jobs", []):
                            if not job.get("enabled", True):
                                continue
                            cron_total += 1
                            state = job.get("state", {})
                            last_status = state.get("lastStatus", state.get("lastRunStatus", ""))
                            is_ok = last_status == "ok"
                            if is_ok:
                                cron_ok += 1
                            cron_details.append({
                                "name": job.get("name", job.get("id")),
                                "status": last_status,
                                "last_run": state.get("lastRunAtMs"),
                            })
                    except (json.JSONDecodeError, OSError):
                        pass
                s3.set_attribute("cron_total", cron_total)
                s3.set_attribute("cron_ok", cron_ok)
                s3.set_attribute("cron_jobs", cron_details)

            heartbeat_rate = round(alive_agents / total_agents * 100, 1) if total_agents else 0
            todo_completion = round(todo_done / todo_total * 100, 1) if todo_total else 0
            cron_health = round(cron_ok / cron_total * 100, 1) if cron_total else 0

            root.set_attribute("alive_agents", alive_agents)
            root.set_attribute("todo_completion", f"{todo_done}/{todo_total}")
            root.set_attribute("cron_health", f"{cron_ok}/{cron_total}")

        tracer.flush()
        return [
            Metric("heartbeat_alive_rate", heartbeat_rate, unit="%",
                   breakdown={"alive": alive_names, "total": total_agents}),
            Metric("todo_completion", todo_completion, unit="%",
                   breakdown={"done": todo_done, "total": todo_total}),
            Metric("reports_generated", cron_health, unit="%",
                   breakdown={"ok": cron_ok, "total": cron_total, "jobs": cron_details}),
        ]
