"""Heartbeat Manager bridge — reads heartbeat-manager data into OA metrics."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

HBM_CANDIDATES = [
    Path("/mnt/d/project/openclaw/skills/heartbeat-manager"),
    Path("D:/project/openclaw/skills/heartbeat-manager"),
]


def _find_hbm_root() -> Path | None:
    for c in HBM_CANDIDATES:
        if c.exists() and (c / "SKILL.md").exists():
            return c
    return None


class HeartbeatBridgePipeline(Pipeline):
    """Reads heartbeat-manager state files for system health metrics."""

    goal_id = "heartbeat_status"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="heartbeat_bridge", db_path=config.db_path)

        with tracer.span("Heartbeat Bridge", {"date": date}) as root:
            hbm = _find_hbm_root()

            registered = 0
            alive = 0
            stale = 0
            todo_total = 0
            todo_done = 0
            reports_count = 0

            if hbm:
                # Heartbeat state
                with tracer.span("Read Heartbeat State"):
                    state_file = hbm / "status" / "heartbeat.json"
                    if not state_file.exists():
                        state_file = hbm / "heartbeat.json"
                    if state_file.exists():
                        try:
                            data = json.loads(state_file.read_text(encoding="utf-8"))
                            tasks = data if isinstance(data, list) else data.get("tasks", [])
                            registered = len(tasks)
                            for t in tasks:
                                status = t.get("status", "")
                                if status == "alive" or status == "active":
                                    alive += 1
                                elif status == "stale" or status == "expired":
                                    stale += 1
                        except (json.JSONDecodeError, OSError):
                            pass

                # Todo state
                with tracer.span("Read Todo State"):
                    todo_file = hbm / "todos.md"
                    if not todo_file.exists():
                        todo_file = hbm / "data" / "todos.md"
                    if todo_file.exists():
                        try:
                            text = todo_file.read_text(encoding="utf-8")
                            for line in text.splitlines():
                                stripped = line.strip()
                                if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
                                    todo_total += 1
                                    todo_done += 1
                                elif stripped.startswith("- [ ]"):
                                    todo_total += 1
                        except OSError:
                            pass

                # Reports count
                with tracer.span("Count Reports"):
                    reports_dir = hbm / "reports"
                    if reports_dir.exists():
                        reports_count = sum(
                            1 for f in reports_dir.iterdir()
                            if f.suffix == ".md" and date in f.name
                        )
                        if reports_count == 0:
                            reports_count = sum(1 for f in reports_dir.iterdir() if f.suffix == ".md")

            heartbeat_rate = round(alive / registered * 100, 1) if registered > 0 else 0
            todo_completion = round(todo_done / todo_total * 100, 1) if todo_total > 0 else 0

            root.set_attribute("registered", registered)
            root.set_attribute("alive", alive)

        tracer.flush()
        return [
            Metric("heartbeat_alive_rate", heartbeat_rate, unit="%",
                   breakdown={"registered": registered, "alive": alive, "stale": stale}),
            Metric("todo_completion", todo_completion, unit="%",
                   breakdown={"total": todo_total, "done": todo_done}),
            Metric("reports_generated", reports_count, unit="count"),
        ]
