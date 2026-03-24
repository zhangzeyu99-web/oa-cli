"""Knowledge Growth — tracks skills, memories, and autoskill sessions from .openclaw."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig

DATA_FLOW_EDGES = [
    {"from": "workspace/skills/", "to": "count_skills.py", "type": "scan"},
    {"from": "xiaoxia-memory-repo/", "to": "count_memories.py", "type": "scan"},
    {"from": "workspace/memory/", "to": "count_memories.py", "type": "scan"},
    {"from": "autoskill/sessions/", "to": "count_autoskill.py", "type": "scan"},
    {"from": "count_skills.py", "to": "Aggregate", "type": "data"},
    {"from": "count_memories.py", "to": "Aggregate", "type": "data"},
    {"from": "count_autoskill.py", "to": "Aggregate", "type": "data"},
    {"from": "Aggregate", "to": "goal_metrics", "type": "write"},
]
NODE_TYPES = {
    "workspace/skills/": "source",
    "xiaoxia-memory-repo/": "source",
    "workspace/memory/": "source",
    "autoskill/sessions/": "source",
    "count_skills.py": "script",
    "count_memories.py": "script",
    "count_autoskill.py": "script",
    "Aggregate": "script",
    "goal_metrics": "db",
}


class KnowledgeGrowthPipeline(Pipeline):
    """Reads .openclaw/workspace/skills, xiaoxia-memory-repo, autoskill."""

    goal_id = "knowledge_growth"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="knowledge_growth", db_path=config.db_path)
        oc = config.openclaw_home

        with tracer.span("Knowledge Growth", {
            "date": date,
            "data_flow_edges": DATA_FLOW_EDGES,
            "node_types": NODE_TYPES,
        }) as root:
            total_skills = 0
            new_skills_today = 0
            skill_names: list[str] = []
            total_memories = 0
            new_memories_today = 0
            mem_by_dir: dict[str, int] = {}
            autoskill_sessions = 0

            with tracer.span("Count Skills", {
                "step": "scan", "source": str(oc / "workspace" / "skills"),
            }) as s1:
                skills_dir = oc / "workspace" / "skills"
                if skills_dir.exists():
                    for sd in skills_dir.iterdir():
                        if sd.is_dir() and (sd / "SKILL.md").exists():
                            total_skills += 1
                            skill_names.append(sd.name)
                            try:
                                mtime = datetime.fromtimestamp(sd.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") == date:
                                    new_skills_today += 1
                            except OSError:
                                pass
                s1.set_attribute("total_skills", total_skills)
                s1.set_attribute("new_today", new_skills_today)
                s1.set_attribute("recent_skills", skill_names[-10:])

            with tracer.span("Count Memories", {
                "step": "scan",
            }) as s2:
                mem_dirs = [
                    oc / "xiaoxia-memory-repo",
                    oc / "workspace" / "memory",
                ]
                for md in mem_dirs:
                    if not md.exists():
                        continue
                    dir_count = 0
                    for mf in md.rglob("*.md"):
                        total_memories += 1
                        dir_count += 1
                        try:
                            mtime = datetime.fromtimestamp(mf.stat().st_mtime)
                            if mtime.strftime("%Y-%m-%d") == date:
                                new_memories_today += 1
                        except OSError:
                            pass
                    mem_by_dir[md.name] = dir_count
                s2.set_attribute("total_memories", total_memories)
                s2.set_attribute("new_today", new_memories_today)
                s2.set_attribute("by_directory", mem_by_dir)

            with tracer.span("Count AutoSkill", {
                "step": "scan", "source": str(oc / "autoskill"),
            }) as s3:
                as_dir = oc / "autoskill" / "embedded_sessions"
                if as_dir.exists():
                    autoskill_sessions = sum(1 for _ in as_dir.iterdir() if _.is_dir())
                sb_dir = oc / "autoskill" / "SkillBank"
                sb_count = 0
                if sb_dir.exists():
                    sb_count = sum(1 for _ in sb_dir.iterdir())
                s3.set_attribute("embedded_sessions", autoskill_sessions)
                s3.set_attribute("skill_bank_entries", sb_count)

            root.set_attribute("skills", total_skills)
            root.set_attribute("memories", total_memories)
            root.set_attribute("autoskill", autoskill_sessions)

        tracer.flush()
        return [
            Metric("total_memories", total_memories, unit="count",
                   breakdown={"by_dir": mem_by_dir}),
            Metric("daily_new_memories", new_memories_today, unit="count"),
            Metric("queue_throughput", total_skills, unit="count",
                   breakdown={"new_today": new_skills_today}),
            Metric("vectordb_documents", autoskill_sessions, unit="count"),
        ]
