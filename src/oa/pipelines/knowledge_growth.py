"""Knowledge Growth pipeline — tracks Viking memory and vectordb growth."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline
from .viking_activity import _find_viking_base, _find_queue_db, AGENT_HASH_MAP

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig


class KnowledgeGrowthPipeline(Pipeline):
    """Tracks total memories, daily new memories, and vectordb index size."""

    goal_id = "knowledge_growth"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="knowledge_growth", db_path=config.db_path)

        with tracer.span("Knowledge Growth", {"date": date}) as root:
            viking = _find_viking_base(config.openclaw_home)
            queue_db = _find_queue_db(config.openclaw_home)

            total_memories = 0
            today_new = 0
            per_category = {}

            if viking:
                with tracer.span("Count Memories"):
                    for scope in ("agent", "user"):
                        scope_dir = viking / scope
                        if not scope_dir.exists():
                            continue
                        for mf in scope_dir.rglob("mem_*.md"):
                            total_memories += 1
                            try:
                                mtime = datetime.fromtimestamp(mf.stat().st_mtime)
                                if mtime.strftime("%Y-%m-%d") == date:
                                    today_new += 1
                            except OSError:
                                continue
                            cat = mf.parent.name
                            per_category[cat] = per_category.get(cat, 0) + 1

            queue_messages = 0
            if queue_db:
                with tracer.span("Count Queue Messages"):
                    try:
                        db = sqlite3.connect(str(queue_db))
                        row = db.execute(
                            "SELECT COUNT(*) FROM queue_messages WHERE timestamp >= ? AND timestamp < ?",
                            (self._date_to_ts(date), self._date_to_ts(date, next_day=True)),
                        ).fetchone()
                        queue_messages = row[0] if row else 0
                        db.close()
                    except Exception:
                        pass

            vectordb_docs = self._count_vectordb(config.openclaw_home)

            root.set_attribute("total_memories", total_memories)
            root.set_attribute("today_new", today_new)

        tracer.flush()
        return [
            Metric("total_memories", total_memories, unit="count",
                   breakdown={"per_category": per_category}),
            Metric("daily_new_memories", today_new, unit="count"),
            Metric("queue_throughput", queue_messages, unit="count"),
            Metric("vectordb_documents", vectordb_docs, unit="count"),
        ]

    def _date_to_ts(self, date: str, next_day: bool = False) -> int:
        dt = datetime.strptime(date, "%Y-%m-%d")
        if next_day:
            from datetime import timedelta
            dt += timedelta(days=1)
        return int(dt.timestamp())

    def _count_vectordb(self, openclaw_home: Path) -> int:
        candidates = [
            Path("/mnt/d/project/openclaw/data/vectordb/context"),
            openclaw_home / "data" / "vectordb" / "context",
            openclaw_home.parent / "data" / "vectordb" / "context",
        ]
        for vdb in candidates:
            meta = vdb / "collection_meta.json"
            if meta.exists():
                try:
                    data = json.loads(meta.read_text(encoding="utf-8"))
                    return data.get("total_documents", data.get("count", 0))
                except (json.JSONDecodeError, OSError):
                    pass
            if vdb.exists():
                store = vdb / "store"
                if store.exists():
                    return sum(1 for f in store.iterdir() if f.suffix == ".log")
        return 0
