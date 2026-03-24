"""Conversation Quality — tracks message volume and session activity from .openclaw/agents."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

DATA_FLOW_EDGES = [
    {"from": "agents/main/sessions", "to": "scan_sessions.py", "type": "data"},
    {"from": "agents/xiaopin/sessions", "to": "scan_sessions.py", "type": "data"},
    {"from": "agents/xiaoyi/sessions", "to": "scan_sessions.py", "type": "data"},
    {"from": "agents/xiaoxun/sessions", "to": "scan_sessions.py", "type": "data"},
    {"from": "scan_sessions.py", "to": "Compute Stats", "type": "process"},
    {"from": "Compute Stats", "to": "goal_metrics", "type": "write"},
]
NODE_TYPES = {
    "agents/main/sessions": "agent",
    "agents/xiaopin/sessions": "agent",
    "agents/xiaoyi/sessions": "agent",
    "agents/xiaoxun/sessions": "agent",
    "scan_sessions.py": "script",
    "Compute Stats": "script",
    "goal_metrics": "db",
}


class ConversationQualityPipeline(Pipeline):
    """Reads agent session JSONL files for message counts and activity."""

    goal_id = "conversation_quality"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="conversation_quality", db_path=config.db_path)
        oc = config.openclaw_home

        with tracer.span("Conversation Quality", {
            "date": date,
            "data_flow_edges": DATA_FLOW_EDGES,
            "node_types": NODE_TYPES,
        }) as root:
            total_messages = 0
            active_agents = 0
            total_sessions_today = 0
            per_agent: dict[str, dict] = {}

            agents_dir = oc / "agents"
            if agents_dir.exists():
                for agent_dir in agents_dir.iterdir():
                    if not agent_dir.is_dir():
                        continue
                    agent_id = agent_dir.name
                    sess_dir = agent_dir / "sessions"
                    if not sess_dir.exists():
                        continue

                    with tracer.span(f"Scan {agent_id}", {
                        "step": "scan", "agent": agent_id,
                        "source": str(sess_dir),
                    }) as sa:
                        agent_msgs = 0
                        agent_sessions = 0
                        files_scanned = 0

                        for sf in sess_dir.glob("*.jsonl"):
                            try:
                                mtime = datetime.fromtimestamp(sf.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") != date:
                                    continue
                            except OSError:
                                continue

                            agent_sessions += 1
                            total_sessions_today += 1
                            files_scanned += 1

                            try:
                                with open(sf, encoding="utf-8") as f:
                                    for line in f:
                                        try:
                                            d = json.loads(line)
                                            if d.get("type") == "message":
                                                agent_msgs += 1
                                        except json.JSONDecodeError:
                                            continue
                            except OSError:
                                continue

                        if agent_sessions > 0:
                            active_agents += 1
                        total_messages += agent_msgs
                        if agent_msgs > 0:
                            per_agent[agent_id] = {
                                "sessions": agent_sessions,
                                "messages": agent_msgs,
                            }

                        sa.set_attribute("sessions_today", agent_sessions)
                        sa.set_attribute("messages", agent_msgs)
                        sa.set_attribute("files_scanned", files_scanned)

            with tracer.span("Compute Stats", {"step": "compute"}) as sc:
                avg_per_session = (
                    round(total_messages / total_sessions_today, 1)
                    if total_sessions_today > 0 else 0
                )
                sc.set_attribute("total_messages", total_messages)
                sc.set_attribute("active_agents", active_agents)
                sc.set_attribute("sessions", total_sessions_today)
                sc.set_attribute("avg_per_session", avg_per_session)
                sc.set_attribute("per_agent", per_agent)

            root.set_attribute("messages", total_messages)
            root.set_attribute("sessions", total_sessions_today)
            root.set_attribute("agents", active_agents)

        tracer.flush()
        return [
            Metric("message_throughput", total_messages, unit="count",
                   breakdown={"per_agent": per_agent, "sessions": total_sessions_today}),
            Metric("processing_success_rate", avg_per_session, unit="count",
                   breakdown={"label": "avg_msgs_per_session"}),
            Metric("pending_ratio", active_agents, unit="count",
                   breakdown={"label": "active_agents_with_conversations"}),
        ]
