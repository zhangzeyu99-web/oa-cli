"""Conversation Quality — tracks message volume, session activity, unanswered and failed sessions."""
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
    {"from": "agents/xiaoxia/sessions", "to": "scan_sessions.py", "type": "data"},
    {"from": "scan_sessions.py", "to": "Compute Stats", "type": "process"},
    {"from": "Compute Stats", "to": "goal_metrics", "type": "write"},
]
NODE_TYPES = {
    "agents/main/sessions": "agent",
    "agents/xiaopin/sessions": "agent",
    "agents/xiaoyi/sessions": "agent",
    "agents/xiaoxun/sessions": "agent",
    "agents/xiaoxia/sessions": "agent",
    "scan_sessions.py": "script",
    "Compute Stats": "script",
    "goal_metrics": "db",
}


class ConversationQualityPipeline(Pipeline):
    """Reads all agent session JSONL files for messages, unanswered, and errors."""

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
            unanswered_total = 0
            failed_total = 0
            per_agent: dict[str, dict] = {}
            failed_reasons: list[str] = []

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
                    }) as sa:
                        agent_msgs = 0
                        agent_sessions = 0
                        agent_unanswered = 0
                        agent_failed = 0
                        agent_errors: list[str] = []

                        for sf in sess_dir.iterdir():
                            if not sf.is_file():
                                continue
                            # Include active sessions only
                            if sf.suffix != ".jsonl" or ".reset." in sf.name or ".deleted." in sf.name or ".bak" in sf.name:
                                continue
                            try:
                                mtime = datetime.fromtimestamp(sf.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") != date:
                                    continue
                            except OSError:
                                continue

                            agent_sessions += 1
                            total_sessions_today += 1

                            last_role = None
                            session_has_error = False

                            try:
                                with open(sf, encoding="utf-8") as f:
                                    for line in f:
                                        try:
                                            d = json.loads(line)
                                            if d.get("type") != "message":
                                                continue
                                            msg = d.get("message", {})
                                            if not isinstance(msg, dict):
                                                continue

                                            role = msg.get("role", "")
                                            agent_msgs += 1
                                            if role in ("user", "assistant"):
                                                last_role = role

                                            status = msg.get("status", "")
                                            error = msg.get("error", "")
                                            if status == "error" or error:
                                                session_has_error = True
                                                reason = f"{agent_id}: {str(error)[:60]}" if error else f"{agent_id}: status={status}"
                                                agent_errors.append(reason)
                                        except json.JSONDecodeError:
                                            continue
                            except (OSError, UnicodeDecodeError):
                                continue

                            if last_role == "user":
                                agent_unanswered += 1
                            if session_has_error:
                                agent_failed += 1

                        if agent_sessions > 0:
                            active_agents += 1
                        total_messages += agent_msgs
                        unanswered_total += agent_unanswered
                        failed_total += agent_failed
                        failed_reasons.extend(agent_errors[:5])

                        if agent_sessions > 0:
                            per_agent[agent_id] = {
                                "sessions": agent_sessions,
                                "messages": agent_msgs,
                                "unanswered": agent_unanswered,
                                "failed": agent_failed,
                            }

                        sa.set_attribute("sessions", agent_sessions)
                        sa.set_attribute("messages", agent_msgs)
                        sa.set_attribute("unanswered", agent_unanswered)
                        sa.set_attribute("failed", agent_failed)

            with tracer.span("Compute Stats", {"step": "compute"}) as sc:
                avg_per_session = (
                    round(total_messages / total_sessions_today, 1)
                    if total_sessions_today > 0 else 0
                )
                sc.set_attribute("total_messages", total_messages)
                sc.set_attribute("active_agents", active_agents)
                sc.set_attribute("sessions", total_sessions_today)
                sc.set_attribute("unanswered", unanswered_total)
                sc.set_attribute("failed", failed_total)
                if failed_reasons:
                    sc.set_attribute("error_reasons", failed_reasons[:10])

            root.set_attribute("messages", total_messages)
            root.set_attribute("unanswered", unanswered_total)
            root.set_attribute("failed", failed_total)

        tracer.flush()
        return [
            Metric("message_throughput", total_messages, unit="count",
                   breakdown={"per_agent": per_agent, "sessions": total_sessions_today}),
            Metric("processing_success_rate", avg_per_session, unit="count",
                   breakdown={"label": "avg_msgs_per_session"}),
            Metric("pending_ratio", active_agents, unit="count",
                   breakdown={"label": "active_agents_with_conversations"}),
            Metric("unanswered_sessions", unanswered_total, unit="count",
                   breakdown={"per_agent": {a: d["unanswered"] for a, d in per_agent.items() if d.get("unanswered")}}),
            Metric("failed_sessions", failed_total, unit="count",
                   breakdown={"reasons": failed_reasons[:10]} if failed_reasons else None),
        ]
