"""Infrastructure Health — monitors OpenViking vectordb, Gateway, and session storage."""
from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

DATA_FLOW_EDGES = [
    {"from": ".openclaw/data/vectordb/", "to": "measure_vectordb.py", "type": "scan"},
    {"from": "Gateway :18789", "to": "probe_gateway.py", "type": "probe"},
    {"from": "agents/*/sessions/", "to": "measure_sessions.py", "type": "scan"},
    {"from": "measure_vectordb.py", "to": "Aggregate", "type": "data"},
    {"from": "probe_gateway.py", "to": "Aggregate", "type": "data"},
    {"from": "measure_sessions.py", "to": "Aggregate", "type": "data"},
    {"from": "Aggregate", "to": "goal_metrics", "type": "write"},
]
NODE_TYPES = {
    ".openclaw/data/vectordb/": "db",
    "Gateway :18789": "cron",
    "agents/*/sessions/": "agent",
    "measure_vectordb.py": "script",
    "probe_gateway.py": "script",
    "measure_sessions.py": "script",
    "Aggregate": "script",
    "goal_metrics": "db",
}


class InfraHealthPipeline(Pipeline):
    """Monitors vectordb size, gateway liveness, session storage volume."""

    goal_id = "infra_health"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="infra_health", db_path=config.db_path)
        oc = config.openclaw_home

        with tracer.span("Infrastructure Health", {
            "date": date,
            "data_flow_edges": DATA_FLOW_EDGES,
            "node_types": NODE_TYPES,
        }) as root:

            vectordb_kb = 0
            with tracer.span("Measure VectorDB", {
                "step": "scan", "source": str(oc / "data" / "vectordb"),
            }) as s1:
                vdb = oc / "data" / "vectordb"
                if vdb.exists():
                    vectordb_kb = sum(
                        f.stat().st_size for f in vdb.rglob("*") if f.is_file()
                    ) // 1024
                s1.set_attribute("vectordb_kb", vectordb_kb)
                s1.set_attribute("path_exists", vdb.exists())

            gateway_alive = 0
            with tracer.span("Probe Gateway", {
                "step": "probe", "target": "127.0.0.1:18789",
            }) as s2:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex(("127.0.0.1", 18789))
                    gateway_alive = 1 if result == 0 else 0
                    sock.close()
                except Exception:
                    gateway_alive = 0
                s2.set_attribute("alive", gateway_alive)

            session_mb = 0.0
            session_details: dict[str, float] = {}
            with tracer.span("Measure Session Storage", {
                "step": "scan", "source": str(oc / "agents"),
            }) as s3:
                agents_dir = oc / "agents"
                if agents_dir.exists():
                    for ad in agents_dir.iterdir():
                        if not ad.is_dir():
                            continue
                        sd = ad / "sessions"
                        if not sd.exists():
                            continue
                        agent_bytes = sum(f.stat().st_size for f in sd.iterdir() if f.is_file())
                        agent_mb = round(agent_bytes / (1024 * 1024), 2)
                        session_details[ad.name] = agent_mb
                        session_mb += agent_mb
                session_mb = round(session_mb, 2)
                s3.set_attribute("total_mb", session_mb)
                s3.set_attribute("per_agent", session_details)

            root.set_attribute("vectordb_kb", vectordb_kb)
            root.set_attribute("gateway", gateway_alive)
            root.set_attribute("storage_mb", session_mb)

        tracer.flush()
        return [
            Metric("vectordb_size_kb", vectordb_kb, unit="count",
                   breakdown={"path": str(oc / "data" / "vectordb")}),
            Metric("gateway_alive", gateway_alive, unit="count"),
            Metric("session_storage_mb", session_mb, unit="count",
                   breakdown={"per_agent": session_details}),
        ]
