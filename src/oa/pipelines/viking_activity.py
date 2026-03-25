"""Team Health pipeline — reads .openclaw/agents sessions and memory for activity."""
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
    {"from": "agents/*/sessions", "to": "scan_activity.py", "type": "data"},
    {"from": "memory/*.sqlite", "to": "scan_activity.py", "type": "data"},
    {"from": "workspace/memory/", "to": "scan_memory.py", "type": "data"},
    {"from": "scan_activity.py", "to": "Compute Health", "type": "process"},
    {"from": "scan_memory.py", "to": "Compute Health", "type": "process"},
    {"from": "Compute Health", "to": "goal_metrics", "type": "write"},
    {"from": "Compute Health", "to": "daily_agent_activity", "type": "write"},
]
NODE_TYPES = {
    "agents/*/sessions": "agent",
    "memory/*.sqlite": "db",
    "workspace/memory/": "source",
    "scan_activity.py": "script",
    "scan_memory.py": "script",
    "Compute Health": "script",
    "goal_metrics": "db",
    "daily_agent_activity": "db",
}


class VikingActivityPipeline(Pipeline):
    """Reads .openclaw/agents/*/sessions for real agent activity."""

    goal_id = "team_health"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="team_health", db_path=config.db_path)
        oc = config.openclaw_home
        agent_ids = {a.id for a in config.agents}

        with tracer.span("Team Health", {
            "date": date,
            "data_flow_edges": DATA_FLOW_EDGES,
            "node_types": NODE_TYPES,
        }) as root:
            active_agents: list[str] = []
            memory_agents: list[str] = []
            per_agent: dict[str, dict] = {}

            with tracer.span("Scan Agent Sessions", {
                "step": "scan", "source": str(oc / "agents"),
            }) as s1:
                agents_dir = oc / "agents"
                if agents_dir.exists():
                    for agent_dir in agents_dir.iterdir():
                        if not agent_dir.is_dir():
                            continue
                        aid = agent_dir.name
                        if aid not in agent_ids:
                            continue
                        sess_dir = agent_dir / "sessions"
                        if not sess_dir.exists():
                            continue

                        session_count = 0
                        for sf in sess_dir.glob("*.jsonl"):
                            try:
                                mtime = datetime.fromtimestamp(sf.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") == date:
                                    session_count += 1
                            except OSError:
                                continue

                        if session_count > 0:
                            active_agents.append(aid)
                        per_agent[aid] = {"sessions": session_count}

                s1.set_attribute("active_agents", active_agents)
                s1.set_attribute("per_agent_sessions", {a: d["sessions"] for a, d in per_agent.items() if d["sessions"] > 0})

            with tracer.span("Check Memory Files", {
                "step": "scan",
            }) as s2:
                mem_dirs = [
                    oc / "xiaoxia-memory-repo",
                    oc / "workspace" / "memory",
                ]
                for md in mem_dirs:
                    if not md.exists():
                        continue
                    for mf in md.rglob("*.md"):
                        try:
                            mtime = datetime.fromtimestamp(mf.stat().st_mtime)
                            if mtime.strftime("%Y-%m-%d") == date:
                                memory_agents.append("main")
                                break
                        except OSError:
                            continue
                    else:
                        continue
                    break
                s2.set_attribute("memory_logged_agents", list(set(memory_agents)))

            with tracer.span("Write Agent Activity", {
                "step": "store", "db.operation": "write", "db.table": "daily_agent_activity",
            }) as s3:
                for aid in agent_ids:
                    is_active = aid in active_agents
                    has_mem = aid in memory_agents or (is_active and aid == "main")
                    if has_mem and aid not in memory_agents:
                        memory_agents.append(aid)
                    self._write_agent_activity(config.db_path, date, aid, is_active, has_mem)
                s3.set_attribute("rows_written", len(agent_ids))

            active_count = len(active_agents)
            mem_count = len(set(memory_agents))
            total = len(agent_ids)
            discipline = round(mem_count / total * 100, 1) if total else 0

            root.set_attribute("active", active_count)
            root.set_attribute("memory_logged", mem_count)
            root.set_attribute("total_agents", total)

        tracer.flush()
        return [
            Metric("active_agent_count", active_count, unit="count",
                   breakdown={"active": active_agents, "total": total}),
            Metric("memory_discipline", discipline, unit="%",
                   breakdown={"logged": list(set(memory_agents)), "total": total}),
        ]

    def _write_agent_activity(self, db_path: Path, date: str, agent_id: str,
                              is_active: bool, has_mem: bool) -> None:
        db = sqlite3.connect(str(db_path))
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """INSERT INTO daily_agent_activity
               (date, agent_id, session_count, memory_logged)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(date, agent_id) DO UPDATE SET
                   session_count = excluded.session_count,
                   memory_logged = excluded.memory_logged""",
            (date, agent_id, 1 if is_active else 0, 1 if has_mem else 0),
        )
        db.commit()
        db.close()
