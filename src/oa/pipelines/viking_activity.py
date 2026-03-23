"""Viking-native pipeline — reads OpenClaw Viking data store directly.

Replaces the file-based scanner with direct Viking/queue.db access.
Produces team_health metrics from real Viking data.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

AGENT_HASH_MAP = {
    "c0e41d081e77": "main",
    "811b7a5b4a7e": "xiaopin",
    "db99a4b37326": "xiaoyi",
    "dd1d28656a26": "system",
}


def _find_viking_base(openclaw_home: Path) -> Path | None:
    """Locate the Viking data directory."""
    candidates = [
        Path("/mnt/d/project/openclaw/data/viking/openclaw-workspace"),
        openclaw_home / "data" / "viking" / "openclaw-workspace",
        openclaw_home.parent / "data" / "viking" / "openclaw-workspace",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _find_queue_db(openclaw_home: Path) -> Path | None:
    candidates = [
        Path("/mnt/d/project/openclaw/data/_system/queue/queue.db"),
        openclaw_home / "data" / "_system" / "queue" / "queue.db",
        openclaw_home.parent / "data" / "_system" / "queue" / "queue.db",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


class VikingActivityPipeline(Pipeline):
    """Reads Viking agent memories + queue.db for real activity data."""

    goal_id = "team_health"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="viking_activity", db_path=config.db_path)

        with tracer.span("Viking Activity", {"date": date}) as root:
            viking = _find_viking_base(config.openclaw_home)
            queue_db = _find_queue_db(config.openclaw_home)

            agent_ids = {a.id for a in config.agents}
            active_agents = set()
            memory_logged_agents = set()

            if viking:
                with tracer.span("Scan Agent Memories"):
                    agent_dir = viking / "agent"
                    if agent_dir.exists():
                        for d in agent_dir.iterdir():
                            if not d.is_dir() or d.name.startswith("."):
                                continue
                            aid = AGENT_HASH_MAP.get(d.name, d.name[:8])
                            if aid not in agent_ids:
                                continue
                            for mf in d.rglob("mem_*.md"):
                                try:
                                    mtime = datetime.fromtimestamp(mf.stat().st_mtime)
                                    if mtime.strftime("%Y-%m-%d") == date:
                                        active_agents.add(aid)
                                        memory_logged_agents.add(aid)
                                        break
                                except OSError:
                                    continue

                with tracer.span("Scan User Memories"):
                    user_mem = viking / "user" / "openclaw-agent" / "memories"
                    if user_mem.exists():
                        for mf in user_mem.rglob("mem_*.md"):
                            try:
                                mtime = datetime.fromtimestamp(mf.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") == date:
                                    active_agents.add("main")
                                    memory_logged_agents.add("main")
                                    break
                            except OSError:
                                continue

            if queue_db:
                with tracer.span("Scan Queue DB"):
                    try:
                        db = sqlite3.connect(str(queue_db))
                        rows = db.execute(
                            "SELECT data, timestamp FROM queue_messages"
                        ).fetchall()
                        for data_json, ts in rows:
                            dt = datetime.fromtimestamp(ts)
                            if dt.strftime("%Y-%m-%d") != date:
                                continue
                            active_agents.add("main")
                            try:
                                parsed = json.loads(data_json)
                                inner = json.loads(parsed.get("data", "{}"))
                                uri = inner.get("uri", "")
                                for h, name in AGENT_HASH_MAP.items():
                                    if h in uri and name in agent_ids:
                                        active_agents.add(name)
                            except (json.JSONDecodeError, KeyError):
                                pass
                        db.close()
                    except Exception:
                        pass

            # Write per-agent activity
            for agent_id in agent_ids:
                is_active = agent_id in active_agents
                has_mem = agent_id in memory_logged_agents
                self._write_agent_activity(config.db_path, date, agent_id, is_active, has_mem)

            active_count = len(active_agents & agent_ids)
            mem_count = len(memory_logged_agents & agent_ids)
            total = len(agent_ids)
            discipline = round(mem_count / total * 100, 1) if total else 0

            root.set_attribute("active", active_count)
            root.set_attribute("memory_logged", mem_count)

        tracer.flush()
        return [
            Metric("active_agent_count", active_count, unit="count",
                   breakdown={"active": list(active_agents & agent_ids), "total": total}),
            Metric("memory_discipline", discipline, unit="%",
                   breakdown={"logged": list(memory_logged_agents & agent_ids), "total": total}),
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
